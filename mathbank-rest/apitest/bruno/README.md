# Bruno collection for the runtime API

A [Bruno](https://www.usebruno.com) collection (one `.bru` file per operation, one folder per OpenAPI tag) generated from the live
OpenAPI document of `apitest.app:app` — the runtime profile plus the WP6 quiz routers, 117 operations — to explore and test the
API on a local uvicorn that talks to **real AWS DynamoDB**.

```
.venv/bin/python apitest/bruno/gen_collection.py          # regenerate apitest/bruno/collection/ (deterministic)
.venv/bin/python apitest/bruno/gen_collection.py --check  # exit 1 if the committed collection is stale
```

Never edit `collection/` by hand; change the generator.

## Install Bruno

Desktop app: <https://www.usebruno.com/downloads> (or `brew install --cask bruno`), then **Open Collection** →
`mathbank-rest/apitest/bruno/collection`. CLI, nothing to install: `npx @usebruno/cli@latest`.

## Start the API

Read-only against dev (every AWS write is refused with `423 AWS_READONLY`):

```
cd mathbank-rest
.venv/bin/python -m apitest.serve --mode dev-readonly        # when apitest/serve.py exists
```

Until then, the equivalent by hand (`AWS_PROFILE` must be logged in, e.g. `aws sso login --profile aws-sutanu-admin`):

```
cd mathbank-rest
.venv/bin/python -c "
import os, sys
from apitest.server import server_env
env = server_env('dev-readonly', 'aws-sutanu-admin')
os.execvpe(sys.executable, [sys.executable, '-m', 'uvicorn', 'apitest.app:app', '--app-dir', '.', '--port', '8000'], env)"
```

For `test-writable` use `server_env('test-writable', ...)`: runtime state goes to the `-test` tables, published content and vectors are
read from `dev`.

## Environments

Pick `local-dev-readonly` or `local-test` (top right in the app, `--env` in the CLI). Variables:

| variable | meaning |
| --- | --- |
| `baseUrl` | `http://127.0.0.1:8000` — change it if you used another port |
| `adminKey` (secret) | leave empty in git; paste `ADMIN_API_KEY` from `mathbank-rest/.env` in the app (CLI: `--env-var adminKey=...`) |
| `learnerToken` (secret) | set by `register`/`login`; in `local-dev-readonly` login is refused (it stamps last-login), so paste a token |
| `learnerEmail`, `learnerPassword` | used by the register/login bodies |
| `studentId`, `attemptId`, `routeAttemptId`, `quizId`, `questionId`, `enrollmentId`, `planId`, `feedbackId`, `notificationId`, ... | path/body ids; the lists in `00-bootstrap` fill the ones they can, fill the others by hand |
| `canonicalCode`, `conceptSlug`, `techniqueSlug`, `microCourseCode` | public reference data, pre-filled with dev values so the public GETs run immediately |

Auth per request: learner routes send `Authorization: Bearer {{learnerToken}}`, admin routes send `X-Admin-Api-Key: {{adminKey}}`
(routes that list both get both), public routes send neither.

## Run

- **Folder**: right-click a folder → *Run* (or CLI `npx @usebruno/cli@latest run 00-bootstrap --env local-dev-readonly`).
  Folders are numbered in run order: `00-bootstrap` first (health, register, login, lists that seed variables — copies of the
  operations that also live in their tag folder), then public tags, then learner/admin tags. Reads come before `[WRITE]` requests
  in every folder.
- **Headless, whole collection, reads only** (from `apitest/bruno/collection`):

  ```
  npx @usebruno/cli@latest run --env local-dev-readonly --exclude-tags=write --reporter-html report.html
  ```

  Requests carry the tags `read`/`write` and `public`/`learner`/`admin`, so `--tags=public` runs only the public GETs.
  Without `--exclude-tags=write` the `[WRITE]` requests run too (in `dev-readonly` they answer 423, which still passes `< 500`).

## Safety model

- `dev-readonly`: real dev data, `MB_AWS_READONLY=1` — the AWS client refuses every mutating call (DynamoDB, S3, S3 Vectors, ...), so
  a `[WRITE]` request cannot change anything; it returns `423`.
- `test-writable`: runtime state lives in `-test` resources, published content and vectors are read from dev; writes are allowed only
  to `-test` resources, so dev cannot be mutated even by a bug.
- Assertions are `res.status: lt 500` everywhere (a 4xx is an answer, a 5xx is a bug) and `eq 200` for public GETs whose ids are
  pre-filled.
