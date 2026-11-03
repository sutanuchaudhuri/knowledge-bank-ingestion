"""SQS wrapper for the Studio job queues (requirement 70 C4 §4, requirement 71 WP3).

Queues are ``mb-studio-research-<env>`` and ``mb-studio-render-<env>`` with dead-letter queues
``mb-studio-<kind>-dlq-<env>`` (``mathbank-db/aws/sqs`` creates them). A message only *wakes* a worker: the
authoritative state is the ``mb-jobs`` item, claimed by a conditional update, so a duplicate, late or replayed
message is harmless. Messages are validated pydantic models both ways.

    q = JobsQueue()
    q.send(JobMessage(job_id=jid, kind="render"))
    for r in q.receive("render", wait_seconds=20):
        handle(r.message); q.delete("render", r.receipt_handle)

For a Lambda SQS trigger with ``ReportBatchItemFailures`` use :func:`process_sqs_event`.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from botocore.exceptions import ClientError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mathbank_rest.config import settings
from mathbank_rest.stores import ddb
from mathbank_rest.stores.errors import StoreUnavailable

LOG = logging.getLogger("mathbank_rest.jobs_queue")

JobKind = Literal["research", "render"]
KINDS: tuple[JobKind, ...] = ("research", "render")
# Worker lease is 330 s (stores/jobs); the visibility timeout is a little longer so SQS never redelivers a message
# to a second worker while the first one still legitimately holds the lease.
DEFAULT_VISIBILITY_SECONDS = 360
MAX_RECEIVE_COUNT = 3  # redrive policy of every queue created by mathbank-db/aws/sqs


class JobMessage(BaseModel):
    """Body of every Studio queue message. ``version`` is the item version at enqueue time (informational)."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    kind: JobKind
    version: int = Field(default=1, ge=1)


@dataclass(frozen=True)
class Received:
    """One received message. ``message`` is None (and ``error`` set) for a body that is not a valid JobMessage."""

    message_id: str
    receipt_handle: str
    receive_count: int
    body: str
    message: JobMessage | None = None
    error: str | None = None


def queue_name(kind: JobKind, *, dlq: bool = False, env: str | None = None) -> str:
    return f"mb-studio-{kind}-{'dlq-' if dlq else ''}{env or settings.ddb_env}"


def parse_body(body: str) -> JobMessage:
    return JobMessage.model_validate_json(body)


class JobsQueue:
    """Thin, typed SQS client for the two Studio queues. Queue URLs are resolved once per name."""

    def __init__(self, *, client: Any = None, env: str | None = None):
        self._client = client
        self._env = env
        self._urls: dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def sqs(self):
        return self._client or ddb.client("sqs")

    def url(self, kind: JobKind, *, dlq: bool = False) -> str:
        name = queue_name(kind, dlq=dlq, env=self._env)
        with self._lock:
            if name not in self._urls:
                try:
                    self._urls[name] = self.sqs.get_queue_url(QueueName=name)["QueueUrl"]
                except ClientError as exc:
                    raise StoreUnavailable(f"queue {name} is not available: {exc.response['Error']['Code']}", queue=name) from None
            return self._urls[name]

    # ------------------------------------------------------------------ produce

    def send(self, message: JobMessage, *, delay_seconds: int = 0) -> str:
        r = self.sqs.send_message(QueueUrl=self.url(message.kind), MessageBody=message.model_dump_json(),
                                  DelaySeconds=max(0, min(int(delay_seconds), 900)))
        return r["MessageId"]

    def send_batch(self, messages: list[JobMessage]) -> list[JobMessage]:
        """Send up to 10 messages per call per kind; returns the messages SQS refused (partial batch failure)."""
        failed: list[JobMessage] = []
        for kind in KINDS:
            mine = [m for m in messages if m.kind == kind]
            for i in range(0, len(mine), 10):
                chunk = mine[i:i + 10]
                r = self.sqs.send_message_batch(QueueUrl=self.url(kind), Entries=[
                    {"Id": str(n), "MessageBody": m.model_dump_json()} for n, m in enumerate(chunk)])
                failed += [chunk[int(f["Id"])] for f in r.get("Failed", [])]
        return failed

    # ------------------------------------------------------------------ consume

    def receive(self, kind: JobKind, *, max_messages: int = 1, wait_seconds: int = 20,
                visibility_timeout: int = DEFAULT_VISIBILITY_SECONDS) -> list[Received]:
        r = self.sqs.receive_message(
            QueueUrl=self.url(kind), MaxNumberOfMessages=max(1, min(int(max_messages), 10)),
            WaitTimeSeconds=max(0, min(int(wait_seconds), 20)), VisibilityTimeout=int(visibility_timeout),
            AttributeNames=["ApproximateReceiveCount"])
        out = []
        for m in r.get("Messages", []):
            count = int(m.get("Attributes", {}).get("ApproximateReceiveCount", 1))
            try:
                out.append(Received(m["MessageId"], m["ReceiptHandle"], count, m["Body"], parse_body(m["Body"])))
            except ValidationError as exc:
                LOG.error("poison message %s on %s: %s", m["MessageId"], kind, exc.errors()[:1])
                out.append(Received(m["MessageId"], m["ReceiptHandle"], count, m["Body"], None, "invalid_message"))
        return out

    def delete(self, kind: JobKind, receipt_handle: str) -> None:
        self.sqs.delete_message(QueueUrl=self.url(kind), ReceiptHandle=receipt_handle)

    def delete_batch(self, kind: JobKind, receipt_handles: list[str]) -> list[str]:
        """Returns the receipt handles that could not be deleted (they will be redelivered)."""
        failed: list[str] = []
        for i in range(0, len(receipt_handles), 10):
            chunk = receipt_handles[i:i + 10]
            r = self.sqs.delete_message_batch(QueueUrl=self.url(kind), Entries=[
                {"Id": str(n), "ReceiptHandle": h} for n, h in enumerate(chunk)])
            failed += [chunk[int(f["Id"])] for f in r.get("Failed", [])]
        return failed

    def extend_visibility(self, kind: JobKind, receipt_handle: str, seconds: int) -> None:
        self.sqs.change_message_visibility(QueueUrl=self.url(kind), ReceiptHandle=receipt_handle,
                                           VisibilityTimeout=max(0, min(int(seconds), 43200)))

    def poll(self, kind: JobKind, handler: Callable[[JobMessage], Any], *, max_messages: int = 1,
             wait_seconds: int = 0, visibility_timeout: int = DEFAULT_VISIBILITY_SECONDS) -> int:
        """Receive, run ``handler`` per message, delete the ones that succeeded. A handler that raises leaves its message
        in flight, so SQS redelivers it (and moves it to the DLQ after MAX_RECEIVE_COUNT). Returns the handled count."""
        done: list[str] = []
        for r in self.receive(kind, max_messages=max_messages, wait_seconds=wait_seconds, visibility_timeout=visibility_timeout):
            if r.message is None:
                continue
            try:
                handler(r.message)
            except Exception:
                LOG.exception("handler failed for %s %s (receive %s)", kind, r.message.job_id, r.receive_count)
                continue
            done.append(r.receipt_handle)
        if done:
            self.delete_batch(kind, done)
        return len(done)


def process_sqs_event(event: dict, handler: Callable[[JobMessage], Any]) -> dict:
    """Lambda SQS trigger entry point with partial batch response: only the failed messages are retried."""
    failures = []
    for rec in event.get("Records", []):
        try:
            handler(parse_body(rec["body"]))
        except Exception:
            LOG.exception("record %s failed", rec.get("messageId"))
            failures.append({"itemIdentifier": rec.get("messageId")})
    return {"batchItemFailures": failures}

