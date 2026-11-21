#!/usr/bin/env python3
"""Fetch each doctor's most recent IACR ePrint papers into data/papers.json.

Run from anywhere:  python3 tools/fetch_papers.py
Options:
  --cache PATH   where the harvested ePrint metadata is kept between runs
                 (default: ~/.cache/isogeny-forest/eprint.json)
  --full         ignore the cache and harvest the whole archive again
  --keep N       papers to keep per person (default 5)

Data comes from ePrint's OAI-PMH interface (https://eprint.iacr.org/oai), which
the archive offers for metadata under CC0. The first run harvests the whole
archive year by year (a few minutes, with a pause between requests); later runs
only fetch what changed since the last run.

Matching a person to papers goes by name, so namesakes are a risk. Settings
per person live in tools/papers-config.json:
  "aliases": other spellings of the name as ePrint shows it,
  "strict":  keep only papers on the forest's topics or with a co-author in
             the forest (for common names),
  "exclude": ePrint ids that belong to a namesake,
  "skip":    true to show no papers for this person.
Each run writes tools/papers-review.txt listing papers that look off-topic,
so a namesake can be spotted and excluded.
"""
import argparse, datetime as dt, json, re, sys, time, unicodedata
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "data" / "graph.json"
OUT = ROOT / "data" / "papers.json"
CONFIG = ROOT / "tools" / "papers-config.json"
REVIEW = ROOT / "tools" / "papers-review.txt"
OAI = "https://eprint.iacr.org/oai"
UA = "isogeny-forest-papers/1.0 (static site; OAI-PMH metadata harvest)"
NS = {"o": "http://www.openarchives.org/OAI/2.0/", "dc": "http://purl.org/dc/elements/1.1/"}
TOPIC = re.compile(r"isogen|elliptic|supersingular|abelian|curve|quaternion|sidh|sike|csidh|sqisign|"
                   r"post-quantum|group action|endomorphism|modular|class group|pairing|genus|"
                   r"kummer|jacobian|theta|montgomery|discrete log", re.I)


def fold(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[-‐.,']", " ", s)
    return " ".join(s.split())


def get(params, tries=4):
    url = OAI + "?" + urllib.parse.urlencode(params)
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            if k == tries - 1:
                raise
            print(f"  retry after {e}", file=sys.stderr)
            time.sleep(5 * (k + 1))


def harvest(since, until):
    """Yield records with datestamp in [since, until]."""
    params = {"verb": "ListRecords", "metadataPrefix": "oai_dc", "from": since, "until": until}
    while True:
        root = ET.fromstring(get(params))
        err = root.find("o:error", NS)
        if err is not None:
            if err.get("code") == "noRecordsMatch":
                return
            raise RuntimeError(err.get("code") + ": " + (err.text or ""))
        lr = root.find("o:ListRecords", NS)
        for rec in lr.findall("o:record", NS):
            md = rec.find("o:metadata", NS)
            if md is None:
                continue
            ident = (md.findtext(".//dc:identifier", "", NS) or "").strip()
            m = re.search(r"(\d{4}/\d+)$", ident)
            if not m:
                continue
            yield {
                "id": m.group(1),
                "title": " ".join((md.findtext(".//dc:title", "", NS) or "").split()),
                "authors": [" ".join((c.text or "").split()) for c in md.findall(".//dc:creator", NS)],
                "abstract": " ".join((md.findtext(".//dc:description", "", NS) or "").split())[:600],
            }
        tok = lr.findtext("o:resumptionToken", "", NS).strip() if lr is not None else ""
        if not tok:
            return
        params = {"verb": "ListRecords", "resumptionToken": tok}
        time.sleep(2)


def update_cache(path, full):
    cache = {"last": None, "papers": {}}
    if path.exists() and not full:
        cache = json.loads(path.read_text())
    today = dt.date.today()
    if cache["last"]:
        start = dt.date.fromisoformat(cache["last"]) - dt.timedelta(days=2)
        windows = []
        d = start
        while d <= today:
            e = min(d + dt.timedelta(days=60), today)
            windows.append((d, e)); d = e + dt.timedelta(days=1)
    else:
        windows = [(dt.date(y, 1, 1), min(dt.date(y, 12, 31), today)) for y in range(1996, today.year + 1)]
    for a, b in windows:
        n = 0
        for p in harvest(a.isoformat(), b.isoformat()):
            cache["papers"][p["id"]] = p; n += 1
        print(f"  {a} .. {b}: {n} records", file=sys.stderr)
        time.sleep(2)
    cache["last"] = today.isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False))
    return cache["papers"]


def variants(name, aliases):
    t = fold(name).split()
    v = {" ".join(t)}
    if len(t) > 2:
        v.add(t[0] + " " + t[-1])
        v.add(t[0] + " " + " ".join(t[-2:]))
    v |= {fold(a) for a in aliases}
    return v


def sort_key(pid):
    y, n = pid.split("/")
    return (int(y), int(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "isogeny-forest" / "eprint.json")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--keep", type=int, default=5)
    args = ap.parse_args()

    graph = json.loads(GRAPH.read_text())
    conf = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    people = [n for n in graph["nodes"] if not n.get("external")]
    print("Harvesting ePrint metadata…", file=sys.stderr)
    papers = update_cache(args.cache, args.full)

    by_name = {}
    for p in papers.values():
        for a in p["authors"]:
            by_name.setdefault(fold(a), []).append(p)
    names = {n["id"]: variants(n["name"], conf.get(n["id"], {}).get("aliases", [])) for n in people}
    forest_names = set().union(*names.values())

    out, counts, review = {}, {}, []
    for n in people:
        c = conf.get(n["id"], {})
        if c.get("skip"):
            continue
        mine = {}
        for v in names[n["id"]]:
            for p in by_name.get(v, []):
                mine[p["id"]] = p
        excl = set(c.get("exclude", []))
        keep = []
        for pid in sorted(mine, key=sort_key, reverse=True):
            p = mine[pid]
            if pid in excl:
                continue
            co = [a for a in p["authors"] if fold(a) in forest_names and fold(a) not in names[n["id"]]]
            on_topic = bool(TOPIC.search(p["title"] + " " + p["abstract"]))
            if c.get("strict") and not (on_topic or co):
                review.append(f"{n['id']}\tdropped (strict)\t{pid}\t{p['title']}")
                continue
            if not (on_topic or co):
                review.append(f"{n['id']}\toff-topic?\t{pid}\t{p['title']}\t{'; '.join(p['authors'])}")
            keep.append(p)
        if keep:
            counts[n["id"]] = len(keep)
            out[n["id"]] = [{"id": p["id"], "year": int(p["id"][:4]), "title": p["title"],
                             "with": [a for a in p["authors"] if fold(a) not in names[n["id"]]]}
                            for p in keep[:args.keep]]

    data = {"meta": {"updated": dt.date.today().isoformat(), "source": "IACR ePrint (OAI-PMH, CC0 metadata)"},
            "counts": counts, "papers": out}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    REVIEW.write_text("# Papers that may belong to a namesake. Add their ids to \"exclude\" in papers-config.json.\n"
                      + "\n".join(review) + "\n")
    missing = [n["id"] for n in people if n["id"] not in out]
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(out)} people with papers; none found for: {', '.join(missing) or '—'}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
