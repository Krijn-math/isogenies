#!/usr/bin/env python3
"""Turn thesis/thesis_data/theses.json into thesis/data/graph.json and report consistency problems.
Corrections confirmed by Krijn live in overrides.json next to this script (applied last)."""
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

nodes, edges = {}, []
for r in T:
    if r["id"] in OV.get("drop", []): continue
    cs = [CC[c.strip()] for c in r["country"].split("&") if c.strip()]
    n = {"id": r["id"], "name": r["name"], "year": r["year"], "university": r["university"],
         "country": cs[0] if cs else "", "title": r["title"]}
    if r["pdf_url"]: n["pdf"] = r["pdf_url"]
    if r["relevance"] == "connector": n["external"] = True
    nodes[r["id"]] = n
for r in T:
    if r["id"] not in nodes: continue
    for s in r["supervisors"]:
        sid = byname[s["name"]]["id"] if s["name"] in byname else ext_id(s["name"])
        if sid not in nodes:
            nodes[sid] = {"id": sid, "name": s["name"], "external": True}
        edges.append({"from": sid, "to": r["id"]})
# overrides: node field patches, edge add/remove
for nid, patch in OV.get("nodes", {}).items():
    if nid not in nodes: nodes[nid] = {"id": nid}
    for k, v in patch.items():
        if v is None: nodes[nid].pop(k, None)
        else: nodes[nid][k] = v
for e in OV.get("remove_edges", []):
    edges = [x for x in edges if not (x["from"] == e[0] and x["to"] == e[1])]
for e in OV.get("add_edges", []):
    for i in e[:2]:
        if i not in nodes: sys.exit(f"override edge to unknown node {i}")
    if {"from": e[0], "to": e[1]} not in edges: edges.append({"from": e[0], "to": e[1]})
if "krijn" not in nodes and "reijnders" in nodes:
    nodes["krijn"] = dict(nodes.pop("reijnders"), id="krijn")
    for e in edges:
        for k in ("from", "to"):
            if e[k] == "reijnders": e[k] = "krijn"
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
