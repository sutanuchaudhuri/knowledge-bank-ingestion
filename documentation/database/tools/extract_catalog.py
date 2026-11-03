"""Introspect a scratch database that has ALL mathbank-db/sql migrations applied and write
generated/catalog.json. DSN via MBDOC_DSN (never point this at Neon). See ../README.md section 8."""
import json, re, glob, os, psycopg
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../.."))
SQL_DIR = os.path.join(REPO, "mathbank-db/sql")
OUT = os.path.join(HERE, "../generated")
conn = psycopg.connect(os.environ.get("MBDOC_DSN", "host=/tmp/mbdoc_pg port=55439 user=postgres dbname=mbdoc"))
q = lambda s, *a: conn.execute(s, a or None).fetchall()
SYS = "('pg_catalog','information_schema','pg_toast')"
tables = {}
for s, t, kind, cmt in q(f"""select n.nspname, c.relname, c.relkind, obj_description(c.oid,'pg_class')
  from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where c.relkind in ('r','p','v','m') and n.nspname not in {SYS} and n.nspname not like 'pg\_%%' order by 1,2"""):
    tables[f"{s}.{t}"] = dict(schema=s, table=t, kind={'r':'table','p':'table','v':'view','m':'matview'}[kind], comment=cmt, columns=[], constraints=[], indexes=[], triggers=[])
for s, t, col, typ, nn, dflt, cmt, num in q(f"""select n.nspname,c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,
  pg_get_expr(d.adbin,d.adrelid), col_description(c.oid,a.attnum), a.attnum
  from pg_attribute a join pg_class c on c.oid=a.attrelid join pg_namespace n on n.oid=c.relnamespace
  left join pg_attrdef d on d.adrelid=c.oid and d.adnum=a.attnum
  where a.attnum>0 and not a.attisdropped and c.relkind in ('r','p','v','m') and n.nspname not in {SYS} order by 1,2,8"""):
    k=f"{s}.{t}"
    if k in tables: tables[k]["columns"].append(dict(name=col,type=typ,not_null=nn,default=dflt,comment=cmt))
for s,t,name,ct,defn in q(f"""select n.nspname,c.relname,co.conname,co.contype,pg_get_constraintdef(co.oid)
  from pg_constraint co join pg_class c on c.oid=co.conrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname not in {SYS} order by 1,2,3"""):
    k=f"{s}.{t}"
    if k in tables: tables[k]["constraints"].append(dict(name=name,type={'p':'PK','f':'FK','u':'UNIQUE','c':'CHECK','x':'EXCLUDE','n':'NOTNULL','t':'TRIGGER'}.get(ct,ct),definition=defn))
for s,t,iname,idef in q(f"""select schemaname,tablename,indexname,indexdef from pg_indexes where schemaname not in {SYS} order by 1,2,3"""):
    k=f"{s}.{t}"
    if k in tables: tables[k]["indexes"].append(dict(name=iname,definition=idef))
for s,t,tg,defn in q(f"""select n.nspname,c.relname,tg.tgname,pg_get_triggerdef(tg.oid) from pg_trigger tg join pg_class c on c.oid=tg.tgrelid
  join pg_namespace n on n.oid=c.relnamespace where not tg.tgisinternal and n.nspname not in {SYS}"""):
    k=f"{s}.{t}"
    if k in tables: tables[k]["triggers"].append(dict(name=tg,definition=defn))
for s,v,d in q(f"select schemaname,viewname,definition from pg_views where schemaname not in {SYS}"):
    tables[f"{s}.{v}"]["view_definition"]=d
# source provenance: defining migration, leading comment, inline column comments, added-by migrations
files=sorted(glob.glob(f"{SQL_DIR}/0*.sql"))
for f in files:
    src=open(f).read(); base=os.path.basename(f)
    for m in re.finditer(r"create\s+(?:or\s+replace\s+)?(table|view|materialized\s+view)\s+(?:if\s+not\s+exists\s+)?([a-z_0-9]+)\.([a-z_0-9]+)", src, re.I):
        k=f"{m.group(2).lower()}.{m.group(3).lower()}"
        if k not in tables or tables[k].get("migration"): continue
        tables[k]["migration"]=base
        before=src[:m.start()].rstrip().split("\n")
        lead=[]
        for line in reversed(before):
            if line.strip().startswith("--"): lead.insert(0,line.strip()[2:].strip())
            else: break
        tables[k]["sql_leading_comment"]=" ".join(lead).strip() or None
        # body up to matching paren
        i=src.find("(",m.end()); depth=0; j=i
        while j<len(src) and i!=-1:
            if src[j]=="(": depth+=1
            elif src[j]==")":
                depth-=1
                if depth==0: break
            j+=1
        body=src[i:j] if i!=-1 else ""
        inline={}
        for line in body.split("\n"):
            mm=re.match(r"\s*\(?\s*([a-z_0-9]+)\s+[a-z].*?--\s*(.+)$", line, re.I)
            if mm: inline[mm.group(1).lower()]=mm.group(2).strip()
        tables[k]["inline_column_comments"]=inline
    for m in re.finditer(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?([a-z_0-9]+)\.([a-z_0-9]+)(.*?);", src, re.I|re.S):
        k=f"{m.group(1).lower()}.{m.group(2).lower()}"
        if k not in tables: continue
        for c in re.findall(r"add\s+column\s+(?:if\s+not\s+exists\s+)?([a-z_0-9]+)", m.group(3), re.I):
            tables[k].setdefault("columns_added_by",{}).setdefault(c.lower(),base)
json.dump(tables, open(os.path.join(OUT,"catalog.json"),"w"), indent=1, default=str)
from collections import Counter
print(Counter(v["schema"] for v in tables.values())); print(Counter(v["kind"] for v in tables.values())); print(sum(len(v["columns"]) for v in tables.values()), "columns")
print("no migration:", [k for k,v in tables.items() if not v.get("migration")][:20])
