"""Create or update the SQS queues (and dead-letter queues) used by the Studio job workers (idempotent).

    python -m aws.sqs.provision --env dev [--only studio-research studio-render] [--dry-run]

Every queue is named ``mb-<name>-<env>``; its DLQ is ``mb-<kind>-dlq-<env>`` where ``<name>`` is ``<group>-<kind>``
(14 days retention). The main queues use long polling, SQS-managed encryption and a redrive policy (maxReceiveCount 3), so a
message a worker keeps failing on lands in the DLQ, where the DLQ handler marks the job FAILED (``DELIVERY_EXHAUSTED``). The
visibility timeout (360 s) is longer than the worker lease (330 s) so SQS never hands a message to a second worker while the
first holds the lease. Existing queues are only converged to these attributes; nothing is ever deleted or purged.

Names and attributes must match ``mathbank_rest.jobs_queue`` (``queue_name``, ``DEFAULT_VISIBILITY_SECONDS``,
``MAX_RECEIVE_COUNT``).
"""
from __future__ import annotations

import argparse
import dataclasses
import json

from ..common import LOG, Env, client, setup_logging

MAX_RECEIVE_COUNT = 3
DLQ_RETENTION_SECONDS = 14 * 24 * 3600
RETENTION_SECONDS = 4 * 24 * 3600


@dataclasses.dataclass(frozen=True)
class QueueSpec:
    name: str                     # "<group>-<kind>", without the mb- prefix and the env suffix
    visibility_seconds: int
    purpose: str


QUEUES: tuple[QueueSpec, ...] = (
    QueueSpec("studio-research", 360, "wake-ups for RESEARCHJOB items in mb-jobs (research agent)"),
    QueueSpec("studio-render", 360, "wake-ups for RENDERJOB items in mb-jobs (Manim render)"),
    QueueSpec("geometry-interpret", 360, "async geometry interpretation (INTERPJOB in mb-geometry)"),
)


def queue_name(spec: QueueSpec, env: Env, *, dlq: bool = False) -> str:
    group, kind = spec.name.rsplit("-", 1)
    return f"mb-{group}-{kind}-{'dlq-' if dlq else ''}{env.name}"


def _attributes(spec: QueueSpec, *, dlq_arn: str | None) -> dict[str, str]:
    attrs = {"SqsManagedSseEnabled": "true", "VisibilityTimeout": str(spec.visibility_seconds)}
    if dlq_arn:
        attrs.update({"ReceiveMessageWaitTimeSeconds": "20", "MessageRetentionPeriod": str(RETENTION_SECONDS),
                      "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": str(MAX_RECEIVE_COUNT)})})
    else:
        attrs["MessageRetentionPeriod"] = str(DLQ_RETENTION_SECONDS)
    return attrs


def _ensure(sqs, name: str, attrs: dict[str, str], tags: dict[str, str], dry: bool) -> str | None:
    """Create the queue if missing, otherwise converge its attributes. Returns the queue URL (None on a dry run)."""
    try:
        url = sqs.get_queue_url(QueueName=name)["QueueUrl"]
        LOG.info("exists %s", name)
        if not dry:
            sqs.set_queue_attributes(QueueUrl=url, Attributes=attrs)
        return url
    except sqs.exceptions.QueueDoesNotExist:
        LOG.info("create %s", name)
        if dry:
            return None
        return sqs.create_queue(QueueName=name, Attributes=attrs, tags=tags)["QueueUrl"]


def ensure(env: Env, spec: QueueSpec, dry: bool = False) -> None:
    sqs = client("sqs")
    tags = {"app": "mathbank", "env": env.name, "context": "jobs", "managed-by": "mathbank-db/aws"}
    dlq_url = _ensure(sqs, queue_name(spec, env, dlq=True), _attributes(spec, dlq_arn=None), tags, dry)
    dlq_arn = (sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
               if dlq_url else f"arn:aws:sqs:dry-run:0:{queue_name(spec, env, dlq=True)}")
    _ensure(sqs, queue_name(spec, env), _attributes(spec, dlq_arn=dlq_arn), tags, dry)
    LOG.info("ready %s (%s)", queue_name(spec, env), spec.purpose)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="dev")
    ap.add_argument("--only", nargs="*", help=f"queue names (default: all of {[q.name for q in QUEUES]})")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    setup_logging()
    known = {q.name for q in QUEUES}
    if a.only and set(a.only) - known:
        raise SystemExit(f"unknown queue(s) {sorted(set(a.only) - known)}; known: {sorted(known)}")
    env = Env(a.env)
    for spec in QUEUES:
        if not a.only or spec.name in a.only:
            ensure(env, spec, a.dry_run)


if __name__ == "__main__":
    main()
