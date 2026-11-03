"""Answer raw-DDL questions from generated/catalog.json (built from mathbank-db/sql migrations).

    python3 documentation/database/tools/db_lookup.py table quiz.question      # columns, constraints, indexes, triggers
    python3 documentation/database/tools/db_lookup.py column student_id         # every table having a column (substring ok)
    python3 documentation/database/tools/db_lookup.py refs core.problem         # FKs pointing at a table
    python3 documentation/database/tools/db_lookup.py search mastery            # tables/columns/comments matching text
    python3 documentation/database/tools/db_lookup.py schema learner            # tables in a schema with column counts

If generated/catalog.json is missing (it is git-ignored), rebuild it: see documentation/database/README.md §8.
Tables created outside mathbank-db/sql (geometry_scene.*) are not in the catalog; read schemas/geometry_scene.md.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAT = os.path.join(HERE, "../generated/catalog.json")


def load():
    if not os.path.exists(CAT):
        sys.exit("generated/catalog.json missing - rebuild it (documentation/database/README.md section 8) "
                 "or use .github/skills/mathbank-db/references/TABLE_INDEX.md and the schemas/*.md docs.")
    return json.load(open(CAT))


def show_table(c, key):
    if key not in c:
        close = [k for k in c if key in k]
        sys.exit(f"{key}: not in catalog. Close matches: {close[:15]}")
    t = c[key]
    print(f"{key} ({t['kind']}) created in {t.get('migration')}" + (f" — {t['comment']}" if t.get("comment") else ""))
    added = t.get("columns_added_by") or {}
    for col in t["columns"]:
        extra = f" [added {added[col['name']]}]" if col["name"] in added else ""
        print(f"  {col['name']:32} {col['type']:28} {'NOT NULL' if col['not_null'] else 'null':8} "
              f"{('default ' + col['default']) if col['default'] else ''}{extra}")
    for kind in ("constraints", "indexes", "triggers"):
        rows = [x for x in t.get(kind, []) if not (kind == "constraints" and x.get("type") == "NOTNULL")]
        if rows:
            print(f" {kind}:")
            for x in rows:
                print(f"  - {x.get('name', '')}: {x.get('definition', x)}")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, arg = sys.argv[1], sys.argv[2].lower()
    c = load()
    if cmd == "table":
        show_table(c, arg)
    elif cmd == "column":
        for k, t in sorted(c.items()):
            for col in t["columns"]:
                if arg in col["name"]:
                    print(f"{k}.{col['name']}  {col['type']}{'  NOT NULL' if col['not_null'] else ''}")
    elif cmd == "refs":
        pat = re.compile(r"REFERENCES\s+" + re.escape(arg) + r"\s*\(", re.I)
        for k, t in sorted(c.items()):
            for x in t.get("constraints", []):
                if pat.search(x.get("definition", "")):
                    print(f"{k}: {x['definition']}")
    elif cmd == "search":
        for k, t in sorted(c.items()):
            blob = [k, t.get("comment") or "", t.get("sql_leading_comment") or ""]
            hits = [col["name"] for col in t["columns"] if arg in col["name"] or arg in (col.get("comment") or "").lower()]
            if any(arg in b.lower() for b in blob) or hits:
                print(f"{k}" + (f"  columns: {', '.join(hits)}" if hits else ""))
    elif cmd == "schema":
        for k, t in sorted(c.items()):
            if t["schema"] == arg:
                print(f"{k:55} {t['kind']:5} {len(t['columns']):3} cols  {t.get('migration')}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
