---
name: mathbank-infra-aws
description: 'Working in mathbank-infra-aws: the single AWS CDK (Python) project that deploys and operates every MathBank service (Lambda + Fargate). Use when deploying/redeploying a service, starting/stopping/checking a Fargate app (mathbank-web, mathbank-live, mathbank-ml-frontend), seeding SSM secrets, or diagnosing an AWS CLI/colima/CDK deploy failure.'
argument-hint: 'Optional: service/stack name (e.g. mathbank-web, MathBankRestStack) to focus on'
---

# mathbank-infra-aws conventions

Full detail: [mathbank-infra-aws/README.md](../../../mathbank-infra-aws/README.md) and the two
requirements docs this project implements —
[documentation/requirements/62_AWS_SERVERLESS_DEV_HOSTING_COST_RESEARCH.md](../../../documentation/requirements/62_AWS_SERVERLESS_DEV_HOSTING_COST_RESEARCH.md)
(cost/architecture rationale, start/stop commands, §5.1a redeploy flow) and
[documentation/requirements/63_AWS_SERVERLESS_DEPLOYMENT_IMPLEMENTATION.md](../../../documentation/requirements/63_AWS_SERVERLESS_DEPLOYMENT_IMPLEMENTATION.md)
(full build log, URLs, GOTCHAS, redeploy/stop/pause-per-infra `make` commands).

## What this skill does

This is the **operational control plane** for every MathBank service deployed to AWS — not a
code-editing skill. It knows the one CDK project (`mathbank-infra-aws/`) that deploys and operates
**8 services** across two compute shapes:

| Shape | Services | Default state |
|---|---|---|
| Lambda (scale-to-zero, container image) | `mathbank-rest`, `mathbank-agent`, `mathbank-ml-inference`, `mathbank-mcp-competitions`, `mathbank-manim-studio`, `mathbank-exam-agent` | Always warm-on-request, $0 idle |
| Fargate (run-on-demand, no ALB) | `mathbank-web`, `mathbank-live`, `mathbank-ml-frontend` | `desired_count=0` — **stopped**, $0/month, until you start it |

Given a request, it will:
- **Deploy or redeploy** one stack or every stack (`make deploy` / `make deploy STACKS=...`), building
  Docker images via colima and pushing to ECR automatically.
- **Start / stop / check the status** of any of the three Fargate apps, resolving the task's current
  public IP and port so you get a usable URL, not just a "task is running" confirmation.
- **Seed or rotate SSM secrets** for any service from its own `.env` file, without ever printing a
  secret value to the terminal.
- **Diagnose a failed deploy/start** by checking the known gotcha list first (expired AWS CLI
  session, ARM64/x86_64 task mismatch, missing per-app IAM grant, stale `cdk.out`, etc.) before
  treating it as a new, unknown bug.
- **Report cost** — every command here maps to a concrete, known monthly cost (or $0) documented in
  doc 62 §8, not a guess.

It does **not** edit application code inside `mathbank-web`/`mathbank-live`/etc. — use that app's own
skill (e.g. `mathbank-web`, `mathbank-live`) for that; this skill picks up and deploys whatever is
already committed.

## Example prompts

- *"Start mathbank-live so I can test it in a browser"* → `make fargate-live-start`, then hand back
  the printed `http://<ip>:5174` URL.
- *"Stop everything, I'm done for the day"* → `make fargate-web-stop` / `fargate-live-stop` /
  `fargate-ml-frontend-stop` for all three Fargate apps (Lambda services need no action — they're
  already $0 at idle).
- *"Is mathbank-web still running? What's its URL?"* → `make fargate-web-status`.
- *"I changed mathbank-web's login page, deploy it"* → `make deploy STACKS=MathBankFargateWebStack`,
  then explain whether a running task will roll automatically or a stopped one just needs its next
  `fargate-web-start` to pick up the change (doc 62 §5.1a).
- *"I rotated the OPENAI_API_KEY in mathbank-rest's .env, push it to AWS"* →
  `make seed-ssm SERVICE=mathbank-rest` (no redeploy needed — fetched fresh at next cold start).
- *"My deploy failed with 'session has expired'"* → re-auth (`aws login --profile
  aws-sutanu-admin`), not a new infra bug — GOTCHAS.md §53.
- *"The Fargate container is running but login fails with AccessDenied"* → check the
  `needs_cognito`/IAM-grant gotcha (§52) before assuming an application bug.
- *"What's our current AWS bill for this project?"* → walk through doc 62 §8's measured-cost table,
  noting which Fargate apps are currently running vs. stopped.
- *"Tear down mathbank-ml-inference, we're not using it"* → `make destroy-one
  STACK=MathBankMlInferenceStack` (frees its ECR storage + log group; doc 62 §8's cheapest-to-cut
  candidate).

## Prerequisites — auth and the local Docker runtime

- **AWS CLI auth**: this account uses the newer browser-based `login_session` profile shape
  (`~/.aws/config` → `[profile aws-sutanu-admin]` with `login_session = arn:aws:iam::<account>:root`),
  **not** classic IAM Identity Center/SSO. Its session expires silently mid-work and every
  `aws`/`cdk`/`make deploy`/`make fargate-*` command then fails with the *same* generic
  `Your session has expired. Please reauthenticate using 'aws login'` error, no matter which
  underlying API call actually triggered it — [GOTCHAS.md §53](../../../documentation/GOTCHAS.md).
  Before debugging a sudden failure across *several unrelated* commands, check
  `aws sts get-caller-identity --profile aws-sutanu-admin` first; fix with
  `aws login --profile aws-sutanu-admin` (opens a local browser callback; `--remote` over SSH).
- **colima (the Docker-compatible build runtime)**: `make synth`/`deploy`/`diff` all depend on an
  `ensure-colima` prerequisite that starts it automatically if it isn't running — you don't need to
  run `make colima-start` yourself before a deploy. Its VM disk is pinned to the **external drive**
  (`COLIMA_HOME=/Volumes/External/colima-home`), not `~/.colima` — a full internal disk silently
  corrupts containerd's blob store instead of erroring cleanly
  ([GOTCHAS.md §46](../../../documentation/GOTCHAS.md)). `make colima-stop` to shut it down when
  done building; it costs nothing while stopped (it's local, not billed AWS compute).

## Non-negotiables

- **Always clean `cdk.out` before synth/deploy** (`make synth`/`deploy`/`diff` already do this via
  their `clean-cdk-out` prerequisite) — a stale `cdk.out` self-nests into any `REPO_ROOT`-scoped
  Docker build context invoked more than once in one synth, even with `exclude=[...]` set, causing
  an `ENAMETOOLONG` failure that looks like a real code bug but isn't
  ([GOTCHAS.md §44](../../../documentation/GOTCHAS.md)). Each service's Docker build context is
  its **own directory**, reaching sibling packages (`mathbank-widgets`, `mathbank-scripts`) via
  BuildKit's `build_contexts=` additional-context mechanism, never `REPO_ROOT` directly.
- **A Fargate `DockerImageAsset`'s `platform=` and its `FargateTaskDefinition`'s
  `runtime_platform=` must match exactly.** `mathbank-web`/`mathbank-live`/`mathbank-ml-frontend`
  are built `LINUX_ARM64` (cheaper Graviton rate) — if the task definition's `runtime_platform`
  is ever removed or left to default, the container fails instantly with `exec format error`,
  and `aws ecs describe-tasks` can briefly still show `RUNNING` ([GOTCHAS.md §51](../../../documentation/GOTCHAS.md)).
- **Any Fargate app that calls an AWS SDK other than SSM/S3 needs an explicit IAM grant on its own
  task role** — the generic `FargateAppSpec`/`FargateWebStack` construct only wires
  `ssm:GetParameter` by default (for `fetch-secrets.mjs`). `mathbank-web`/`mathbank-live` set
  `needs_cognito=True` to get the Cognito `AdminInitiateAuth`/`AdminCreateUser`/
  `AdminSetUserPassword`/`AdminGetUser` grant; a new app calling a different AWS service needs its
  own equivalent field/grant added to `fargate_web_stack.py`, or it will run and even serve its
  homepage fine, failing only on the first real call to that missing-permission API
  ([GOTCHAS.md §52](../../../documentation/GOTCHAS.md)).
- **Never pass `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_ENDPOINT_URL_S3` bare** into any
  stack's environment — Neon's S3-compatible credentials under those exact names hijack the AWS
  SDK's own default credential chain (confirmed live: it's picked ahead of the task role whenever
  `AWS_PROFILE` isn't set, i.e. on Fargate). Always alias via `fargate_web_stack.py`'s
  `_AWS_RESERVED_LOOKING_KEYS` map (`MATHBANK_S3_*`), never bare.
- **A service's `.env` keys must be UPPERCASE** for a CDK stack's `env_values.get("KEY")` lookup to
  find them — pydantic-settings matches case-insensitively so the app itself is unaffected, but a
  lowercase `.env` silently produces an empty `present_secrets`/`plain_env_vars` result with no
  error ([GOTCHAS.md §49](../../../documentation/GOTCHAS.md)).
- **CloudFormation rejects `{{resolve:ssm-secure:...}}` inside `Environment.Variables`** — every
  secret is fetched at runtime instead (Lambda: cold-start fetch in `lambda_handler.py`; Fargate:
  `fetch-secrets.mjs` at container startup via `MATHBANK_SSM_PREFIX`/`MATHBANK_SECRET_MAP`), never
  as a CDK dynamic reference ([GOTCHAS.md §42](../../../documentation/GOTCHAS.md)).

## Deploy / redeploy

```bash
cd mathbank-infra-aws
make synth                                  # validate without deploying
make diff                                   # see what would change
make deploy                                 # build + deploy every stack (colima auto-starts if needed)
make deploy STACKS=MathBankFargateWebStack  # redeploy just the Fargate apps after a code change
make deploy STACKS=MathBankRestStack        # redeploy just one Lambda service
```

After editing `mathbank-web`/`mathbank-live`/`mathbank-ml-frontend` code, `make deploy
STACKS=MathBankFargateWebStack` only rebuilds/pushes the app(s) whose code actually changed. If
that app's Fargate task is currently **running**, ECS rolls it automatically (new task up, old one
drained) — re-check `make fargate-<app>-status` afterward since the public IP changes. If the task
is **stopped** (`desired_count=0`, the default), nothing needs to happen immediately; the next
`make fargate-<app>-start` picks up the new code automatically. Full detail: doc 62 §5.1a.

## Start / stop / check status (Fargate: `mathbank-web`, `mathbank-live`, `mathbank-ml-frontend`)

Every Fargate service defaults to `desired_count=0` — **$0/month while stopped**, no idle floor.

```bash
cd mathbank-infra-aws
make fargate-web-start            # or fargate-live-start / fargate-ml-frontend-start
make fargate-web-stop             # or fargate-live-stop / fargate-ml-frontend-stop
make fargate-web-status           # or fargate-live-status / fargate-ml-frontend-status

# generic form, same three verbs, any app:
make fargate-start APP=mathbank-web   # mathbank-web | mathbank-live | mathbank-ml-frontend
make fargate-stop  APP=mathbank-web
make fargate-status APP=mathbank-web
```

`-start`/`-status` resolve and print the task's **current public IP** (`http://<ip>:<port>` —
5173 web, 5174 live, 5175 ml-frontend) — it changes on every start, no ALB/EIP by design (a dev-cost
trade-off: an ALB's fixed hourly cost would dominate these tiny tasks far more than the tasks
themselves). `-stop` sets `desired_count` back to 0; billing stops once the task drains (~30s).

## Seed SSM secrets (before a Fargate/Lambda app's first start, or after rotating a secret)

```bash
cd mathbank-infra-aws
make seed-ssm SERVICE=mathbank-web    # reads mathbank-web/.env, writes SecureString params, never prints values
make seed-ssm SERVICE=mathbank-live
make seed-ssm SERVICE=mathbank-rest   # works for any Lambda service too
```

A secret-only change (no code change) needs **only** `make seed-ssm` + a stop/start cycle of the
affected Fargate app (or the next natural Lambda cold start) — not a full `make deploy`, since
secrets are fetched fresh at container/cold-start every time, never baked into the image.

## Other useful commands

```bash
make outputs                              # print every deployed stack's Function URLs
make outputs STACK=MathBankRestStack      # just one
make destroy-one STACK=MathBankXStack     # tear down one stack (frees its ECR storage/log group)
make destroy                              # tear down everything (stops all AWS charges for this project)
```

## Before changing `fargate_web_stack.py`, `app.py`, or any `stacks/*.py`

1. `make synth` (not just a Python import check) must succeed — it's the only way this catches a
   real CDK/jsii-level error, not just a Python syntax error.
2. If you touch `FargateAppSpec`/`FargateWebStack`, re-verify **all three** apps still deploy and
   start cleanly (`make deploy STACKS=MathBankFargateWebStack` then `make fargate-<app>-start` for
   each) — it's one shared construct, and a fix for one app's IAM/env-var needs can silently change
   behavior for the other two.
3. Treat "the container is RUNNING and the homepage returns 200" as an **insufficient** smoke test
   for anything touching Cognito/IAM/secrets — confirm with a real `curl .../api/auth/*-login` call
   against the deployed app, not just a reachability check (GOTCHAS §51/§52 were both missed by a
   homepage-only check and only caught by an actual login attempt).
