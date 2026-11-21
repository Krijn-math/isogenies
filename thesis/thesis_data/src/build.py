import json,csv,unicodedata,re,sys
sys.path.insert(0,'.')
exec(open('r1.py').read())
C={"United States":["Berkeley","Harvard","Colorado","Florida","Oregon","Brown"],"Netherlands":["Radboud","Eindhoven","Amsterdam","Leiden"],"France":["Polytechnique","Bordeaux","Lorraine","Nancy","Lyon","Aix-Marseille","Paris"],"Belgium":["Leuven","Bruxelles","louvain","Louvain"],"United Kingdom":["Oxford","Birmingham","Royal Holloway","Bristol","University College London"],"New Zealand":["Auckland"],"Canada":["Waterloo","McGill"],"Australia":["Sydney"],"Germany":["Würzburg","Duisburg","Ulm"],"Switzerland":["EPFL"],"Italy":["Trento","Roma Tre"],"Norway":["NTNU"],"Mexico":["CINVESTAV"],"Japan":["Tokyo"],"Hungary":["Central European"],"North Macedonia":["Skopje"]}
FLAG={"United States":"🇺🇸","Netherlands":"🇳🇱","France":"🇫🇷","Belgium":"🇧🇪","United Kingdom":"🇬🇧","New Zealand":"🇳🇿","Canada":"🇨🇦","Australia":"🇦🇺","Germany":"🇩🇪","Switzerland":"🇨🇭","Italy":"🇮🇹","Norway":"🇳🇴","Mexico":"🇲🇽","Japan":"🇯🇵","Hungary":"🇭🇺","North Macedonia":"🇲🇰"}
def countries(u):
    out=[]
    for c,keys in C.items():
        if any(k in u for k in keys): out.append(c)
    return out
for r in R:
    cs=countries(r["university"]); 
    if not cs: print("NO COUNTRY",r["slug"],r["university"])
    # joint degrees: order by appearance in string
    cs.sort(key=lambda c:min(r["university"].find(k) for k in C[c] if k in r["university"]))
    r["country"]=" & ".join(cs); r["flag"]="".join(FLAG[c] for c in cs)
# slugs: lowercase ASCII first name; earliest keeps bare, later get 2,3...
def first(n):
    f=n.split()[0]; f=unicodedata.normalize('NFKD',f).encode('ascii','ignore').decode().lower()
    return re.sub('[^a-z]','',f)
R.sort(key=lambda r:(r["year"],r["name"]))
seen={}
for r in R:
    r["id"]=r["slug"]
    if r["relevance"]=="connector": r["slug"]=""; continue
    f=first(r["name"]); seen[f]=seen.get(f,0)+1
    r["slug"]=f if seen[f]==1 else f"{f}{seen[f]}"
names={r["name"] for r in R}
missing=sorted({s["name"] for r in R for s in r["supervisors"] if s["name"] not in names})
for r in R:
    r["verified"]= "no" if ("verify" in r["notes"] or "unverified" in r["notes"] or "from memory" in r["notes"] or "to fill" in r["notes"]) else "yes"
out=str(__import__("pathlib").Path(__file__).resolve().parent.parent)+"/"   # thesis/thesis_data/
order=["id","slug","name","title","university","country","flag","year","supervisors","pdf_url","source_url","mgp_id","relevance","verified","notes"]
json.dump({"theses":[{k:r[k] for k in order} for r in R],"supervisors_without_entry":missing},open(out+"theses.json","w"),ensure_ascii=False,indent=1)
with open(out+"theses.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(order)
    for r in R: w.writerow([("; ".join(f'{s["name"]} ({s["role"]})' for s in r[k]) if k=="supervisors" else r[k]) for k in order])
print(len(R),"records;",sum(r["relevance"]=="core" for r in R),"core")
print("supervisors without own entry:",missing)
print([ (r["slug"],r["name"]) for r in R if r["slug"] and not r["slug"].isalpha()])
L=["# Open checks for the isogeny tree data","","Generated from theses.json. Tick items off or tell Claude the answer.",""]
L+=["## Mismatches with the Math Genealogy Project",""]
for r in R:
    n=r["notes"]
    if "MGP" in n or "not on Quisquater" in n: L.append(f"- [ ] **{r['name']}** ({r['year']}): {n}")
L+=["","## Entries with unverified or missing data",""]
for r in R:
    if r["verified"]=="no" and not ("MGP" in r["notes"]):
        L.append(f"- [ ] **{r['name']}** ({r['university']}, {r['year']}): {r['notes']}")
L+=["","## Entries without a PDF link (isogeny theses only)",""]
L+=[f"- [ ] {r['name']} ({r['year']})" for r in R if r["relevance"]!="connector" and not r["pdf_url"]]
L+=["","## Supervisors with no thesis entry yet (agent 2 decides whether to add them as nodes)",""]
L.append(", ".join(missing))
# the open checks now live in graph/TO-CHECK.md (kept up to date by graph/to_graph.py)
