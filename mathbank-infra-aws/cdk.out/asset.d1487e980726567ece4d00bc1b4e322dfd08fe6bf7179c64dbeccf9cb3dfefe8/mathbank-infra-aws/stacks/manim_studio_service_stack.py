"""CDK stack: `mathbank-manim-studio` as **two** Lambda functions sharing one container
image (requirements/60, requirements/62 §4, requirements/63) — lambda_handler.py's own
module docstring explains why a single in-process worker loop (this service's local-dev
model) doesn't translate directly to Lambda's frozen-between-invocations execution model:

- `ManimStudioApiFunction` — Function URL, job-queue CRUD only (`api_handler`, Mangum
  with `lifespan="off"`). Light and fast; never renders anything itself.
- `ManimStudioWorkerFunction` — no Function URL, triggered on an EventBridge schedule
  (`worker_handler`, a plain non-ASGI handler). Claims and processes at most one
  research job and one render job per invocation — this is where the actual (slow,
  CPU-heavy) Manim render subprocess runs, so it gets its own generous memory/timeout/
  ephemeral-storage budget, independent of the API function's.

Build context is this service's OWN directory, NOT the repo root (unlike
RestServiceStack) — the sibling mathbank-mcp-competitions dependency (requirements/49)
is reached via a BuildKit *additional build context* (`build_contexts=`) instead.
Confirmed live, requirements/63: a REPO_ROOT-context build triggered *twice* within one
CDK synth (api + worker, each its own `from_image_asset` call) self-nests into
`mathbank-infra-aws/cdk.out` far worse than GOTCHAS.md #44's original single-call case —
`exclude=[...]` patterns did not prevent it. Scoping the primary context to this
directory sidesteps the whole bug class: `cdk.out` is never inside the walked tree at
all, for either of this stack's two builds. Requires the `docker-buildx` CLI plugin
installed locally (`brew install docker-buildx`) — CDK's own docker invocation enables
BuildKit automatically whenever `build_contexts` is set.
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, Duration, Size, Stack
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from .ssm_config import grant_and_map_secrets, plain_env_vars

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = "mathbank-manim-studio"
SERVICE_DIR = REPO_ROOT / SERVICE

# Non-secret config, read straight from the local .env and written as literal Lambda
# environment variables (same rationale as RestServiceStack's own PLAIN_ENV_KEYS).
PLAIN_ENV_KEYS = [
    "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_SSLMODE",
    "MATHBANK_OBJECT_BUCKET",
]

SECRET_KEY_TARGETS = {
    "POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
    "OPENAI_API_KEY": "OPENAI_API_KEY",
    "ADMIN_API_KEY": "ADMIN_API_KEY",
    # Same Neon S3-compatible credential mathbank-rest uses (its own .env is the
    # original source; copied into this service's .env — requirements/63), under the
    # MATHBANK_S3_* alias object_store.py's S3 backend checks first — never the bare
    # AWS_* names, which Lambda reserves for its own execution-role credentials.
    "AWS_SECRET_ACCESS_KEY": "MATHBANK_S3_SECRET_ACCESS_KEY",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    """Keys are upper-cased for lookup — mathbank-manim-studio's own `.env` (unlike
    every other service's, which sync-env.sh generates uppercase) uses lowercase keys;
    pydantic-settings matches env vars case-insensitively so the app itself is
    unaffected, but this stack's PLAIN_ENV_KEYS/SECRET_KEY_TARGETS lookups are not."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip().upper()] = value.strip().strip('"')
    return values


class ManimStudioServiceStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, rest_function_url: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_values = _parse_env_file(SERVICE_DIR / ".env")
        environment = plain_env_vars(env_values, PLAIN_ENV_KEYS)
        environment["MATHBANK_OBJECT_BACKEND"] = "s3"
        if env_values.get("AWS_ENDPOINT_URL_S3"):
            environment["MATHBANK_S3_ENDPOINT_URL"] = env_values["AWS_ENDPOINT_URL_S3"]
        if env_values.get("AWS_REGION"):
            environment["MATHBANK_S3_REGION"] = env_values["AWS_REGION"]
        if env_values.get("AWS_ACCESS_KEY_ID"):
            environment["MATHBANK_S3_ACCESS_KEY_ID"] = env_values["AWS_ACCESS_KEY_ID"]
        # Points the research agent's bundled mathbank-mcp-competitions stdio subprocess
        # at the already-deployed mathbank-rest Lambda, not localhost (same cross-stack
        # pattern as AgentServiceStack/McpCompetitionsServiceStack).
        environment["MATHBANK_REST_BASE_URL"] = rest_function_url.rstrip("/")

        def _image_code(cmd: str) -> lambda_.DockerImageCode:
            # `cmd` belongs to DockerImageCode.from_image_asset (not DockerImageFunction
            # itself) — each call does its own `docker build`, but since only the final
            # CMD instruction differs between the two, every earlier layer (the
            # expensive TeX Live/Cairo/Pango install + pip installs) is served from
            # Docker's local build cache, and the underlying layer blobs are
            # content-addressed/deduplicated in ECR regardless.
            return lambda_.DockerImageCode.from_image_asset(
                directory=str(SERVICE_DIR),
                file="Dockerfile.lambda",
                platform=ecr_assets.Platform.LINUX_ARM64,
                build_contexts={"mcp_competitions": str(REPO_ROOT / "mathbank-mcp-competitions")},
                cmd=[cmd],
            )

        api_fn = lambda_.DockerImageFunction(
            self, "ManimStudioApiFunction",
            function_name="mathbank-manim-studio-api",
            code=_image_code("mathbank_manim_studio.lambda_handler.api_handler"),
            architecture=lambda_.Architecture.ARM_64,
            memory_size=1024,
            timeout=Duration.seconds(30),
            environment=dict(environment),
        )

        worker_fn = lambda_.DockerImageFunction(
            self, "ManimStudioWorkerFunction",
            function_name="mathbank-manim-studio-worker",
            code=_image_code("mathbank_manim_studio.lambda_handler.worker_handler"),
            architecture=lambda_.Architecture.ARM_64,
            # Manim (Cairo rasterization + LaTeX compilation via dvisvgm + ffmpeg mux)
            # is genuinely CPU/memory-heavy compared to the API function's plain CRUD —
            # 3008MB is Lambda's practical "more vCPU too" sweet spot (Lambda allocates
            # CPU proportionally to configured memory).
            memory_size=3008,
            # Generous ceiling for a short explainer-video render (research + Manim
            # compile + ffmpeg encode); well under Lambda's 900s hard max.
            timeout=Duration.seconds(300),
            # Manim's own temp/media directories plus TeX Live's auxiliary files land in
            # /tmp — Lambda's default 512MB ephemeral storage is tight for even a short
            # render; 2048MB is comfortable headroom under this service's own 200MB
            # per-video cap (object_store.py).
            ephemeral_storage_size=Size.mebibytes(2048),
            environment=dict(environment),
        )

        present_secrets = {k: v for k, v in SECRET_KEY_TARGETS.items() if env_values.get(k)}
        for fn in (api_fn, worker_fn):
            secret_env = grant_and_map_secrets(self, fn, SERVICE, present_secrets)
            for key, value in secret_env.items():
                fn.add_environment(key, value)

        url = api_fn.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        self.function_url = url.url

        # Polls both job tables every minute — generous enough for a low-traffic dev
        # environment's research/render turnaround without needing SQS/webhooks.
        rule = events.Rule(
            self, "ManimStudioWorkerSchedule",
            schedule=events.Schedule.rate(Duration.minutes(1)),
        )
        rule.add_target(events_targets.LambdaFunction(worker_fn))

        CfnOutput(self, "ManimStudioApiFunctionUrl", value=url.url)
