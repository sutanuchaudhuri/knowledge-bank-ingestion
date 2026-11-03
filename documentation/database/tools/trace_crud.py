"""Static trace: FastAPI route -> handler -> service call graph -> SQL strings -> (table, C/R/U/D).
Run with mathbank-rest/.venv/bin/python from mathbank-rest/. Writes generated/endpoints.json and
generated/other_writers.json. Misses dynamic SQL (f"schema.{table}"); the schema docs are manually verified."""
import ast, json, os, re, glob, sys, warnings
warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__))
ROOT=os.path.abspath(os.path.join(HERE,"../../.."))
OUT=os.path.join(HERE,"../generated")
PKG=f"{ROOT}/mathbank-rest/src/mathbank_rest"
cat=json.load(open(os.path.join(OUT,"catalog.json")))
SCHEMAS=sorted({v["schema"] for v in cat.values()})
TBL=set(cat)
ident=r"([a-z_]+)\.\"?([a-z_0-9]+)\"?"
PAT=[("C",re.compile(r"insert\s+into\s+"+ident,re.I)),("U",re.compile(r"\bupdate\s+(?:only\s+)?"+ident+r"\s+(?:as\s+\w+\s+)?set\b",re.I)),
     ("D",re.compile(r"delete\s+from\s+(?:only\s+)?"+ident,re.I)),("R",re.compile(r"\b(?:from|join)\s+(?:only\s+|lateral\s+)?"+ident,re.I)),
     ("U",re.compile(r"on\s+conflict[^;]*?do\s+update",re.I))]
def sql_ops(text):
    out=set()
    for op,p in PAT[:4]:
        for m in p.finditer(text):
            k=f"{m.group(1).lower()}.{m.group(2).lower()}"
            if k in TBL: out.add((k,op))
    # upsert: mark inserted table also as U
    if PAT[4][1].search(text):
        for m in PAT[0][1].finditer(text):
            k=f"{m.group(1).lower()}.{m.group(2).lower()}"
            if k in TBL: out.add((k,"U"))
    return out
def strings(node):
    s=[]
    for n in ast.walk(node):
        if isinstance(n,ast.Constant) and isinstance(n.value,str): s.append(n.value)
        elif isinstance(n,ast.JoinedStr):
            s.append("".join(v.value if isinstance(v,ast.Constant) else " X " for v in n.values))
    return s
def modname(path, base, pkgname):
    rel=os.path.relpath(path,base)[:-3].replace(os.sep,".")
    if rel.endswith(".__init__"): rel=rel[:-9]
    return pkgname+"."+rel if rel!="__init__" else pkgname
mods={}
for path in glob.glob(f"{PKG}/**/*.py",recursive=True):
    if "_vendor" in path or "__pycache__" in path: continue
    mods[modname(path,PKG,"mathbank_rest")]=ast.parse(open(path).read())
funcs={}   # (mod,name) -> dict(ops,calls)
imports={} # mod -> alias -> ("mod",m) | ("obj",m,name)
def resolve_rel(mod, level, target, is_pkg):
    parts=mod.split(".")
    base=parts if is_pkg else parts[:-1]
    if level>1: base=base[:-(level-1)]
    return ".".join(base+([target] if target else []))
for mod,tree in mods.items():
    is_pkg=os.path.basename(mod)=="" 
    imp={}; consts={}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            for a in n.names: imp[a.asname or a.name.split(".")[0]]=("mod",a.name)
        elif isinstance(n,ast.ImportFrom):
            src=resolve_rel(mod,n.level,n.module,mod.endswith("__init__")) if n.level else n.module
            for a in n.names:
                full=f"{src}.{a.name}"
                imp[a.asname or a.name]=("mod",full) if full in mods else ("obj",src,a.name)
    for n in tree.body:
        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            tg=n.targets if isinstance(n,ast.Assign) else [n.target]
            ops=set().union(*[sql_ops(s) for s in strings(n)]) if n.value else set()
            for t in tg:
                if isinstance(t,ast.Name) and ops: consts[t.id]=ops
    imports[mod]=imp
    def visit(n, prefix=""):
        for c in ast.iter_child_nodes(n):
            if isinstance(c,(ast.FunctionDef,ast.AsyncFunctionDef)):
                ops=set().union(*[sql_ops(s) for s in strings(c)]) if strings(c) else set()
                calls=set()
                for x in ast.walk(c):
                    if isinstance(x,ast.Name) and x.id in consts: ops|=consts[x.id]
                    if isinstance(x,ast.Call):
                        f=x.func
                        if isinstance(f,ast.Name): calls.add(("name",f.id))
                        elif isinstance(f,ast.Attribute):
                            if isinstance(f.value,ast.Name): calls.add(("attr",f.value.id,f.attr))
                            else: calls.add(("meth",f.attr))
                    # functions passed as callbacks e.g. run_in_threadpool(svc.fn, ...)
                    if isinstance(x,ast.Attribute) and isinstance(x.value,ast.Name): calls.add(("attr",x.value.id,x.attr))
                    if isinstance(x,ast.Name): calls.add(("name",x.id))
                funcs.setdefault((mod,c.name),dict(ops=set(),calls=set()))
                funcs[(mod,c.name)]["ops"]|=ops; funcs[(mod,c.name)]["calls"]|=calls
            if isinstance(c,ast.ClassDef): visit(c)
    visit(tree)
GENERIC={"get","execute","run","fetchall","fetchone","first","scalar","one","all","append","items","keys","values","update","join","format","close","commit","begin","connect","model_dump","model_validate","dict","copy","strip","split","lower","upper","replace","encode","decode","add","pop","setdefault","mappings","scalars","scalar_one","scalar_one_or_none","one_or_none","info","warning","error","exception","debug","dumps","loads","read","write","send","post","put","delete","patch","sort","extend","search","match","sub","group"}
def resolve(mod, call):
    r=_resolve(mod, call)
    if r or call[0]=="name": return r
    n=call[-1]
    if n in GENERIC or n.startswith("__"): return []
    imp=imports.get(mod,{})
    cands=set()
    for v in imp.values():
        cands.add(v[1] if v[0]=="mod" else v[1])
    return [(m,n) for m in cands if (m,n) in funcs]
def _resolve(mod, call):
    imp=imports.get(mod,{})
    if call[0]=="name":
        n=call[1]
        if (mod,n) in funcs: return [(mod,n)]
        if n in imp and imp[n][0]=="obj":
            _,m,o=imp[n]
            if (m,o) in funcs: return [(m,o)]
            # re-export through package __init__
            for k in funcs:
                if k[1]==o and k[0].startswith(m): return [k]
        return []
    if call[0]=="attr":
        a,n=call[1],call[2]
        if a in ("self","cls"): return [(mod,n)] if (mod,n) in funcs else []
        if a in imp and imp[a][0]=="mod": return [(imp[a][1],n)] if (imp[a][1],n) in funcs else []
        if a in imp and imp[a][0]=="obj":   # module imported via from pkg import mod (not in mods map)  or class
            m=f"{imp[a][1]}.{imp[a][2]}"
            if (m,n) in funcs: return [(m,n)]
            if (imp[a][1],n) in funcs: return [(imp[a][1],n)]
        return []
    if call[0]=="meth":
        return [(mod,call[1])] if (mod,call[1]) in funcs else []
    return []
memo={}
def closure(key, depth=0, seen=None):
    seen=seen or set()
    if key in seen or depth>12: return set(), set()
    seen.add(key)
    f=funcs.get(key); 
    if not f: return set(), set()
    ops=set(f["ops"]); path={key}
    for c in f["calls"]:
        for k in resolve(key[0],c):
            o,p=closure(k,depth+1,seen); ops|=o; path|=p
    return ops, path
sys.path.insert(0,f"{ROOT}/mathbank-rest/src")
import io, contextlib
with contextlib.redirect_stderr(io.StringIO()):
    from mathbank_rest.main import app
    from mathbank_rest.socratic_app import app as socratic_app
def walk(routes, prefix=''):
    for r in routes:
        n=type(r).__name__
        if n=='_IncludedRouter': yield from walk(r.original_router.routes, prefix+(r.include_context.prefix or ''))
        elif hasattr(r,'endpoint') and hasattr(r,'methods') and hasattr(r,'dependant'): yield prefix+r.path, r
eps=[]
allroutes=[("mathbank-rest",p,r) for p,r in walk(app.routes)]+[("mathbank-socratic (socratic_app)",p,r) for p,r in walk(socratic_app.routes)]
for svc,path,r in allroutes:
    key=(r.endpoint.__module__, r.endpoint.__name__)
    ops,_=closure(key)
    deps=[d.call for d in r.dependant.dependencies if hasattr(d,"call") and d.call]
    auth=[getattr(d,"__name__",str(d)) for d in deps]
    for m in sorted(r.methods):
        eps.append(dict(service=svc,method=m,path=path,module=key[0],function=key[1],tags=list(r.tags or []),summary=r.summary or (r.endpoint.__doc__ or "").strip().split("\n")[0],
                        auth=auth, ops=sorted([list(x) for x in ops])))
json.dump(eps, open(os.path.join(OUT,"endpoints.json"),"w"), indent=1)
# also non-endpoint writers: scripts & workers & ETL
other={}
for path in glob.glob(f"{ROOT}/mathbank-db/etl/*.py")+glob.glob(f"{ROOT}/mathbank-rest/scripts/*.py")+glob.glob(f"{ROOT}/mathbank-graph/etl/*.py")+[f"{PKG}/outbox_worker.py",f"{PKG}/route_batch.py",f"{PKG}/interactions_cli.py"]+glob.glob(f"{ROOT}/mathbank-data-ingestion/**/*.py",recursive=True)+glob.glob(f"{ROOT}/mathbank-infra-aws/*.py")+glob.glob(f"{ROOT}/mathbank-manim-studio/src/**/*.py",recursive=True)+glob.glob(f"{ROOT}/mathbank-manim-studio/scripts/*.py")+glob.glob(f"{ROOT}/mathbank-ml-*/src/**/*.py",recursive=True):
    if ".venv" in path or "/tests/" in path: continue
    try: t=ast.parse(open(path).read())
    except Exception: continue
    ops=set().union(*[sql_ops(s) for s in strings(t)] or [set()])
    if ops: other[os.path.relpath(path,ROOT)]=sorted([list(x) for x in ops])
json.dump(other, open(os.path.join(OUT,"other_writers.json"),"w"), indent=1)
from collections import Counter
print(len(eps),"ops;", sum(1 for e in eps if e["ops"]),"touch tables")
touched={o[0] for e in eps for o in e["ops"]}
print("tables touched by REST:",len(touched),"/",len(TBL))
print("untouched:",sorted(TBL-touched-{o[0] for v in other.values() for o in v}))
