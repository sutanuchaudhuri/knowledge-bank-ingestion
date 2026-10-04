# mathbank-graph

Local Neo4j Community server (data stored on the external APFS drive) holding the
graph projection of the mathbank corpus. See the `Makefile` for lifecycle targets
(`install`, `configure`, `set-password`, `start`, `stop`, `status`, `project`).

## Connecting / viewing the graph

- **Neo4j Browser**: http://localhost:7474
- **Bolt URL** (enter this in the Browser's connect field, not the http:// address):
  `bolt://localhost:7687`
- **Username**: `neo4j`
- **Password**: value of `NEO4J_PASSWORD` in this directory's `.env` (gitignored;
  see `.env.example` for the key name)

### Login troubleshooting

- Make sure the connect URL field uses `bolt://localhost:7687`, not
  `http://localhost:7474` — the browser UI is served over HTTP but auth happens
  over the bolt connection.
- Check for trailing whitespace/newline if the password was copied from `.env`.
- If Neo4j Browser previously cached an older password in local storage, clear
  the saved connection and re-enter credentials.
- To verify the credentials work independently of the browser, use cypher-shell:
  ```bash
  echo "RETURN 1;" | $(brew --prefix cypher-shell)/bin/cypher-shell \
    -a bolt://localhost:7687 -u neo4j -p "$(grep NEO4J_PASSWORD .env | cut -d= -f2)"
  ```

### Viewing the full graph

Neo4j Browser caps visual results by default. To see everything:

```cypher
MATCH (n) RETURN n;
MATCH (n)-[r]->(m) RETURN n, r, m;
```

Raise the "Initial Node Display" limit in Browser settings (gear icon) if the
graph is large, or check sizes first:

```cypher
MATCH (n) RETURN labels(n) AS label, count(*) AS n ORDER BY n DESC;
MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS n ORDER BY n DESC;
```
