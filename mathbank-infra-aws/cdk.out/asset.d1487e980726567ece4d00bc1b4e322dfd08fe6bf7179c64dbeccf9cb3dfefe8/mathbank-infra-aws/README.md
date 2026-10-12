# mathbank-infra-aws

AWS CDK (Python) deployment project for hosting the MathBank app/compute layer on AWS at
minimum cost, while keeping Neon Postgres and Neo4j AuraDB exactly as they are —
implements [documentation/requirements/62](../documentation/requirements/62_AWS_SERVERLESS_DEV_HOSTING_COST_RESEARCH.md)'s
recommendations. Full implementation status, real measured cold-start/cost numbers, and
every bug found along the way are in
[documentation/requirements/63](../documentation/requirements/63_AWS_SERVERLESS_DEPLOYMENT_IMPLEMENTATION.md).

## Status

| Service | Status |
|---|---|
| `mathbank-rest` | ✅ Deployed — Lambda container image (ARM64) + Function URL, live-verified against real Postgres/Neo4j |
| `mathbank-agent`, `mathbank-ml-inference`, `mathbank-mcp-competitions`, `mathbank-manim-studio` | ⏳ Not started — `mathbank-rest`'s stack is the template to copy |
| `mathbank-web`, `mathbank-ml-frontend` (Amplify Hosting) | ⏳ Not started |
| `mathbank-live` (Fargate) | ⏳ Not started |

## Prerequisites

- A Docker-compatible build runtime. Docker Desktop isn't required —
  [colima](https://colima.run) works and is what this project was built/verified with:
  ```bash
  brew install colima docker
  colima start --cpu 2 --memory 4 --disk 30
  ```
- An authenticated AWS CLI session (`aws sts get-caller-identity` must succeed).
- Node.js (for `npx aws-cdk`) and Python 3.11+.

## One-time setup

```bash
make infra-install      # from the repo root — creates this project's venv
make infra-bootstrap    # CDK bootstrap for this AWS account/region (safe to re-run)
```

Seed the secrets a service's Lambda needs, read from that service's own `.env` and
written straight into SSM `SecureString` parameters (values are never printed):

```bash
cd mathbank-infra-aws
./seed_ssm.sh mathbank-rest
```

## Deploy / update / tear down

```bash
make infra-synth      # validate without deploying
make infra-diff       # see what would change
make infra-deploy     # build the image(s), push to ECR, deploy every stack
make infra-outputs    # print the Function URL(s)
make infra-destroy    # tear down everything — stops all AWS charges for this project
```

## Why this shape (short version — see doc 62/63 for the full reasoning)

- **No VPC, no NAT Gateway.** Neon and AuraDB are public, TLS-protected endpoints, not
  private resources inside this AWS account — putting Lambda in a VPC would only add a
  ~$32+/month idle NAT Gateway cost for no benefit.
- **Lambda container images, not zip packaging.** `mathbank-rest`'s dependency set
  (`scipy`, `pymupdf`, `psycopg[binary]`) exceeds Lambda's 250 MB uncompressed zip limit
  (confirmed by actually trying it: 363 MB). Container images go up to 10 GB.
- **A Lambda Function URL, not API Gateway.** Cheapest front door for a single-function
  dev deployment; the app already has its own admin-API-key gates on sensitive routes.
- **Secrets fetched from SSM at Lambda cold start, not a CloudFormation dynamic
  reference.** CloudFormation rejects `{{resolve:ssm-secure:...}}` directly inside a
  Lambda's `Environment.Variables` (confirmed live — see
  [GOTCHAS.md](../documentation/GOTCHAS.md) §42). `lambda_handler.py` fetches each
  secret once per cold start instead, using the execution role's least-privilege
  `ssm:GetParameter` grant.

## Layout

```
mathbank-infra-aws/
├── app.py                   # CDK entrypoint
├── cdk.json
├── requirements.txt
├── seed_ssm.sh               # populate SSM SecureString secrets for one service
├── Makefile                  # delegated from the root Makefile's `make infra-*` targets
└── stacks/
    ├── ssm_config.py         # shared secret/plain-env-var helpers, reused by every stack
    └── rest_service_stack.py # mathbank-rest's stack — the template for the next service
```
