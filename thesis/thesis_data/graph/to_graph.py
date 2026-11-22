#!/usr/bin/env python3
"""Turn thesis/thesis_data/theses.json into thesis/data/graph.json and report consistency problems.
Corrections confirmed by Krijn live in overrides.json next to this script (applied last):
"nodes" patches a person by id (a new id with a "name" creates one; null removes a field),
"add_edges"/"remove_edges" are [supervisor, student] pairs, and "drop" removes a person, also as a supervisor.
tools/admin.py is a local editor that writes this file."""
import json, re, sys, unicodedata, datetime
from pathlib import Path
from collections import defaultdict
HERE = Path(__file__).resolve().parent
PF = HERE.parent.parent   # the thesis/ folder
SRC = PF / "thesis_data" / "theses.json"
OUT = PF / "data" / "graph.json"
OV = json.loads((HERE / "overrides.json").read_text()) if (HERE / "overrides.json").exists() else {}

CC = {"United States":"us","Netherlands":"nl","France":"fr","Belgium":"be","United Kingdom":"gb","New Zealand":"nz",
      "Canada":"ca","Australia":"au","Germany":"de","Switzerland":"ch","Italy":"it","Norway":"no","Mexico":"mx",
      "Japan":"jp","Hungary":"hu","North Macedonia":"mk"}
def fold(s):
    s = unicodedata.normalize("NFD", s); s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()
def ext_id(name):
    return "x-" + "-".join(fold(name))

data = json.loads(SRC.read_text())
T = data["theses"]
warn = []
# duplicates by id / name / mgp
seen = defaultdict(list)
for r in T:
    seen[("id", r["id"])].append(r["name"]); seen[("name", " ".join(fold(r["name"])))].append(r["id"])
    if r["mgp_id"]: seen[("mgp", r["mgp_id"])].append(r["id"])
for k, v in seen.items():
    if len(v) > 1: warn.append(f"DUPLICATE {k}: {v}")
byname = {r["name"]: r for r in T}
# fuzzy name variants: same surname + same first initial, different strings
allnames = set(byname) | {s["name"] for r in T for s in r["supervisors"]}
key = defaultdict(set)
for n in allnames:
    f = fold(n); f = [w for w in f if w not in ("jr",)]
    key[(f[0][0], f[-1])].add(n)
for k, v in key.items():
    if len(v) > 1: warn.append(f"NAME VARIANT? {sorted(v)}")

# ids in theses.json that the page knows by another id; overrides may use either
RENAME = {"reijnders": "krijn"}
rid = lambda i: RENAME.get(i, i)
drop = {rid(i) for i in OV.get("drop", [])}   # dropped people are gone, also as supervisors
nodes, edges = {}, []
for r in T:
    if rid(r["id"]) in drop: continue
    cs = [CC[c.strip()] for c in r["country"].split("&") if c.strip()]
    n = {"id": rid(r["id"]), "name": r["name"], "year": r["year"], "university": r["university"],
         "country": cs[0] if cs else "", "title": r["title"]}
    if r["pdf_url"]: n["pdf"] = r["pdf_url"]
    if r["relevance"] == "connector": n["external"] = True
    nodes[n["id"]] = n
for r in T:
    if rid(r["id"]) not in nodes: continue
    for s in r["supervisors"]:
        sid = rid(byname[s["name"]]["id"]) if s["name"] in byname else ext_id(s["name"])
        if sid in drop: continue
        if sid not in nodes:
            nodes[sid] = {"id": sid, "name": s["name"], "external": True}
        edges.append({"from": sid, "to": rid(r["id"])})
# overrides: node field patches (a new id with a "name" creates a person), edge add/remove
for nid, patch in OV.get("nodes", {}).items():
    nid = rid(nid)
    if nid in drop: continue
    if nid not in nodes:
        if "name" not in patch:
            warn.append(f"OVERRIDE FOR UNKNOWN PERSON {nid} (no name; skipped)"); continue
        nodes[nid] = {"id": nid}
    for k, v in patch.items():
        if v is None: nodes[nid].pop(k, None)
        else: nodes[nid][k] = v
for e in OV.get("remove_edges", []):
    a, b = rid(e[0]), rid(e[1])
    edges = [x for x in edges if not (x["from"] == a and x["to"] == b)]
for e in OV.get("add_edges", []):
    a, b = rid(e[0]), rid(e[1])
    if a in drop or b in drop: continue
    for i in (a, b):
        if i not in nodes: sys.exit(f"override edge to unknown node {i}")
    if {"from": a, "to": b} not in edges: edges.append({"from": a, "to": b})
# drop externals that no longer supervise anyone
used = {e["from"] for e in edges} | {e["to"] for e in edges}
for nid in [i for i, n in nodes.items() if n.get("external") and i not in used]: del nodes[nid]
# checks: self loops, duplicates, cycles, year order, isolated
for e in edges:
    if e["from"] == e["to"]: warn.append(f"SELF LOOP {e}")
    a, b = nodes[e["from"]], nodes[e["to"]]
    if a.get("year") and b.get("year") and a["year"] >= b["year"]:
        warn.append(f"YEAR ORDER: {a['name']} ({a['year']}) supervises {b['name']} ({b['year']})")
if len({(e['from'], e['to']) for e in edges}) != len(edges): warn.append("DUPLICATE EDGES")
adj = defaultdict(list)
for e in edges: adj[e["from"]].append(e["to"])
state = {}
def dfs(u, path):
    state[u] = 1
    for v in adj[u]:
        if state.get(v) == 1: warn.append(f"CYCLE {path + [v]}")
        elif not state.get(v): dfs(v, path + [v])
    state[u] = 2
for u in list(nodes): 
    if not state.get(u): dfs(u, [u])
for i, n in nodes.items():
    if i not in used: warn.append(f"ISOLATED {n['name']}")
    if not n.get("external") and not n.get("title"): warn.append(f"NO TITLE {n['name']}")
order = sorted(nodes.values(), key=lambda n: (n.get("year") or 0, n["name"]))
g = {"meta": {"updated": datetime.date.today().isoformat()}, "nodes": order, "edges": edges}
OUT.write_text(json.dumps(g, ensure_ascii=False, indent=1) + "\n")
print(f"{len(order)} nodes ({sum(not n.get('external') for n in order)} doctors), {len(edges)} edges -> {OUT}")
print("\n".join(warn))

# Keep the generated half of TO-CHECK.md in step with graph.json; the questions above the marker are hand-kept.
TODO = HERE / "TO-CHECK.md"
MARK = "<!-- Everything below is regenerated by to_graph.py. -->"
head = TODO.read_text().split(MARK)[0].rstrip() + "\n\n" if TODO.exists() else "# Still to check\n\n"
docs = [n for n in order if not n.get("external")]
def items(xs): return "\n".join(f"- [ ] {n['name']} ({n.get('university','')}, {n.get('year','')})" for n in xs) or "- none"
gen = [MARK, "",
       f"## No thesis title ({sum(not n.get('title') for n in docs)})", "", items([n for n in docs if not n.get("title")]), "",
       f"## No supervisor ({sum(n['id'] not in {e['to'] for e in edges} for n in docs)})", "",
       items([n for n in docs if n["id"] not in {e["to"] for e in edges}]), "",
       f"## No link to the thesis PDF ({sum(not n.get('pdf') for n in docs)})", "", items([n for n in docs if not n.get("pdf")]), ""]
TODO.write_text(head + "\n".join(gen))
