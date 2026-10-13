"""CDK stack: Fargate-hosted Next.js apps (requirements/62 §5/§6, revised) — covers
`mathbank-web`, `mathbank-live` (Socket.IO — needs a persistent process, the original
reason this repo chose Fargate at all), and `mathbank-ml-frontend`. `mathbank-web` and
`mathbank-ml-frontend` were originally slated for Amplify Hosting (doc 62 §6.1), but
Amplify's SSR hosting requires a Git-connected app and a GitHub OAuth token only the
repo owner can authorize — not something this stack can automate — so all three apps
share the one Fargate pattern already proven necessary for `mathbank-live`.

No ALB, no NAT Gateway — each task gets its own public IP directly
(`assign_public_ip=True`), reachable on its own container port. This is the cheapest
viable setup for a handful of dev services started on demand, not a 24/7 production
ingress (doc 62 §5.1); an ALB's own hourly charge would dominate the cost of these tiny
tasks far more than the tasks themselves.

Every `FargateService` is created with `desired_count=0` — "run only when needed" (doc
62 §5.1) means the service costs nothing until explicitly started. See
`mathbank-infra-aws/fargate_control.py` and the root Makefile's `fargate-*` targets for
the start/stop/status commands, which flip desired_count and resolve the task's current
public IP (it changes on every start — no static address without an ALB/EIP, a
deliberate cost trade-off for a dev project).

Secrets are fetched at container *startup* (not via ECS's native `secrets:` field,
which needs a pinned SSM parameter version — awkward for an often-reseeded dev secret)
by each container's own entrypoint (`mathbank-scripts/fetch-secrets.mjs`, the same
`MATHBANK_SSM_PREFIX`/`MATHBANK_SECRET_MAP` convention every Lambda service's
`lambda_handler.py` already uses) — so the task ROLE (not just the execution role) needs
`ssm:GetParameter` on exactly those parameters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from constructs import Construct

from .ssm_config import SECRET_ENV_KEYS, ssm_parameter_name

REPO_ROOT = Path(__file__).resolve().parents[2]

# Lambda reserves these names for its own runtime-injected credentials (requirements/63);
# Fargate does not, but the AWS SDK's default credential chain still checks the bare
# AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY env vars *before* the task role, so passing
# Neon's S3-compatible credentials under those exact names would hijack every other AWS
# SDK client in the container (Cognito, SSM) into authenticating as Neon's key instead of
# the real task role — confirmed live. Always alias on the way in, never pass bare.
_AWS_RESERVED_LOOKING_KEYS = {
    "AWS_ACCESS_KEY_ID": "MATHBANK_S3_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY": "MATHBANK_S3_SECRET_ACCESS_KEY",
    "AWS_ENDPOINT_URL_S3": "MATHBANK_S3_ENDPOINT_URL",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"')
    return values


@dataclass
class FargateAppSpec:
    service: str  # directory name, e.g. "mathbank-web"
    port: int
    dockerfile: str  # relative to build_context
    build_context: Path
    plain_env_keys: list[str]
    secret_keys: list[str] = field(default_factory=list)  # .env keys fetched at container startup
    env_overrides: dict[str, str] = field(default_factory=dict)  # wins over the .env-sourced value
    build_contexts: dict[str, str] = field(default_factory=dict)  # BuildKit additional contexts (GOTCHAS.md #44)
    cpu: int = 256
    memory_mib: int = 512
    needs_cognito: bool = False  # grants the task role AdminInitiateAuth/AdminCreateUser/etc.


class FargateWebStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, apps: list[FargateAppSpec], **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, "DefaultVpc", is_default=True)
        cluster = ecs.Cluster(self, "FargateCluster", cluster_name="mathbank-fargate-cluster", vpc=vpc)

        security_group = ec2.SecurityGroup(
            self, "FargateServicesSg",
            vpc=vpc, description="mathbank Fargate dev services - inbound on each apps own port, no ALB",
            allow_all_outbound=True,
        )
        for app in apps:
            security_group.add_ingress_rule(
                ec2.Peer.any_ipv4(), ec2.Port.tcp(app.port),
                f"{app.service} HTTP, direct task public IP (dev-only, no ALB)",
            )

        for app in apps:
            env_values = _parse_env_file(REPO_ROOT / app.service / ".env")
            environment: dict[str, str] = {"PORT": str(app.port)}
            for key in app.plain_env_keys:
                if key in SECRET_ENV_KEYS:
                    raise ValueError(f"{key} is a secret — list it in secret_keys, not plain_env_keys")
                value = env_values.get(key)
                if value is None:
                    continue
                target = _AWS_RESERVED_LOOKING_KEYS.get(key, key)
                environment[target] = value
            environment.update(app.env_overrides)

            task_def = ecs.FargateTaskDefinition(
                self, f"{app.service}TaskDef", cpu=app.cpu, memory_limit_mib=app.memory_mib,
                # Must match the DockerImageAsset's platform=LINUX_ARM64 below (Graviton
                # Fargate task), or the container fails at startup with "exec format error".
                runtime_platform=ecs.RuntimePlatform(
                    cpu_architecture=ecs.CpuArchitecture.ARM64,
                    operating_system_family=ecs.OperatingSystemFamily.LINUX,
                ),
            )

            present_secrets = [k for k in app.secret_keys if env_values.get(k)]
            if present_secrets:
                environment["MATHBANK_SSM_PREFIX"] = f"/mathbank/dev/{app.service}"
                environment["MATHBANK_SECRET_MAP"] = ",".join(
                    f"{k}={_AWS_RESERVED_LOOKING_KEYS.get(k, k)}" for k in present_secrets
                )
                task_def.task_role.add_to_principal_policy(
                    iam.PolicyStatement(
                        actions=["ssm:GetParameter"],
                        resources=[
                            self.format_arn(
                                service="ssm", resource="parameter",
                                resource_name=ssm_parameter_name(app.service, k).lstrip("/"),
                            )
                            for k in present_secrets
                        ],
                    )
                )

            if app.needs_cognito:
                task_def.task_role.add_to_principal_policy(
                    iam.PolicyStatement(
                        actions=[
                            "cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword",
                            "cognito-idp:AdminInitiateAuth", "cognito-idp:AdminGetUser",
                        ],
                        resources=[
                            self.format_arn(
                                service="cognito-idp", resource="userpool",
                                resource_name=env_values.get("COGNITO_USER_POOL_ID", "*"),
                            )
                        ],
                    )
                )

            container = task_def.add_container(
                f"{app.service}Container",
                image=ecs.ContainerImage.from_docker_image_asset(
                    ecr_assets.DockerImageAsset(
                        self, f"{app.service}Image",
                        directory=str(app.build_context), file=app.dockerfile,
                        platform=ecr_assets.Platform.LINUX_ARM64,
                        build_contexts=app.build_contexts or None,
                    )
                ),
                environment=environment,
                logging=ecs.LogDrivers.aws_logs(
                    stream_prefix=app.service,
                    log_group=logs.LogGroup(
                        self, f"{app.service}LogGroup",
                        log_group_name=f"/mathbank/fargate/{app.service}",
                        retention=logs.RetentionDays.ONE_WEEK,
                    ),
                ),
            )
            container.add_port_mappings(ecs.PortMapping(container_port=app.port))

            service = ecs.FargateService(
                self, f"{app.service}Service",
                cluster=cluster, task_definition=task_def,
                desired_count=0,  # "run only when needed" — $0 until started (doc 62 §5.1)
                assign_public_ip=True,
                security_groups=[security_group],
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            )

            CfnOutput(self, f"{app.service}ServiceName", value=service.service_name)

        CfnOutput(self, "ClusterName", value=cluster.cluster_name)
