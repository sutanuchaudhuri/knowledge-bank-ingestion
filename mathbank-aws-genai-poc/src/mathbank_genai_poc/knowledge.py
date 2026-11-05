"""Read-only topic retrieval over the MathBank S3 Vectors indexes, hydrated from ``mb-content`` (requirements 70/71).

A student topic is embedded with ``text-embedding-3-small`` (the model every index was built with; any other embedding
model would live in a different vector space) and queried against three indexes in parallel:

* ``taxonomy-search``  -> concepts / skills / techniques (``TAXNODE#<id>``)
* ``step``             -> worked solution steps used privately as teaching moves (``STEP#<id>``)
* ``problem``          -> practice problem statements (``PROBLEM#<code>``)

Vector metadata holds only ids and hashes, so every hit is hydrated from its ``mb-content`` item and re-checked the same way
``mathbank-rest`` does (``content_lookup.hit_is_current``): the item must be published and the hit's key must be one of the
item's *current* vector keys. Offloaded attributes (``<attr>_ref``) are fetched from S3 and verified by size and SHA-256.
Nothing is written anywhere. Full solutions, answer keys and learner data are never read.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from boto3.dynamodb.types import TypeDeserializer

from mathbank_genai_poc.config import REPO_ROOT, Settings

LOG = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
DIMENSIONS = 1536
MODEL_TAG = "te3small-1536-v1"
INDEXES = {
    "taxonomy": f"taxonomy-search-{MODEL_TAG}",
    "step": f"step-{MODEL_TAG}",
    "problem": f"problem-{MODEL_TAG}",
}
TOP_K = {"taxonomy": 8, "step": 8, "problem": 6}
LIMITS = {"concepts": 3, "teaching_moves": 3, "practice_problems": 2}
TEXT_LIMITS = {"summary": 500, "guidance": 420, "statement": 600}
MAX_TOPIC_CHARS = 300
MAX_OFFLOAD_BYTES = 256 * 1024


class TopicError(ValueError):
    """The student's topic cannot be searched (empty or too long)."""


class ContentIntegrityError(RuntimeError):
    """An offloaded content object did not match its recorded size or digest."""


Embedder = Callable[[str], list[float]]


def openai_embedder() -> Embedder:
    """Paid OpenAI query embeddings, using the repository-root OPENAI_API_KEY (shell variables are ignored)."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "mathbank-scripts"))
    from openai import OpenAI
    from project_env import load_project_openai

    client = OpenAI(api_key=load_project_openai(REPO_ROOT / "mathbank-aws-genai-poc" / ".env"), timeout=15, max_retries=1)

    def embed(text: str) -> list[float]:
        return list(client.embeddings.create(model=EMBEDDING_MODEL, input=[text]).data[0].embedding)

    return embed


@dataclass(frozen=True)
class Clients:
    s3vectors: Any
    dynamodb: Any
    s3: Any

    @classmethod
    def create(cls, settings: Settings) -> Clients:
        import boto3

        session = boto3.Session(profile_name=settings.aws_profile or None, region_name=settings.data_region)
        return cls(session.client("s3vectors"), session.client("dynamodb"), session.client("s3"))


def clean(text: Any, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    cut = value[:limit].rsplit(" ", 1)[0]
    return cut + " …"


class KnowledgeBase:
    def __init__(self, settings: Settings, *, embedder: Embedder | None = None, clients: Clients | None = None):
        self.settings = settings
        self._embedder = embedder
        self._clients = clients
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._deserializer = TypeDeserializer()

    @property
    def clients(self) -> Clients:
        if self._clients is None:
            self._clients = Clients.create(self.settings)
        return self._clients

    def embed(self, topic: str) -> list[float]:
        key = topic.casefold()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            if self._embedder is None:
                self._embedder = openai_embedder()
            embedder = self._embedder
        vector = [float(x) for x in embedder(topic)]
        if len(vector) != DIMENSIONS:
            raise ValueError(f"embedder returned {len(vector)} dimensions, expected {DIMENSIONS}")
        with self._lock:
            self._cache[key] = vector
            while len(self._cache) > 128:
                self._cache.popitem(last=False)
        return vector

    # ------------------------------------------------------------------ AWS reads

    def _query(self, family: str, vector: Sequence[float]) -> list[dict]:
        response = self.clients.s3vectors.query_vectors(
            vectorBucketName=self.settings.vector_bucket, indexName=INDEXES[family], queryVector={"float32": list(vector)},
            topK=TOP_K[family], returnMetadata=True, returnDistance=True,
        )
        hits = []
        for hit in response.get("vectors", []):
            similarity = 1.0 - float(hit.get("distance", 1.0))
            if similarity >= self.settings.min_similarity:
                hits.append({"key": hit["key"], "similarity": round(similarity, 3), "metadata": hit.get("metadata") or {}})
        return sorted(hits, key=lambda h: -h["similarity"])

    def _batch_get(self, pks: Sequence[str]) -> dict[str, dict]:
        keys = [{"PK": {"S": pk}, "SK": {"S": "META"}} for pk in dict.fromkeys(pks)]
        items: dict[str, dict] = {}
        for start in range(0, len(keys), 100):
            request = {self.settings.content_table: {"Keys": keys[start:start + 100]}}
            for _ in range(4):
                response = self.clients.dynamodb.batch_get_item(RequestItems=request)
                for raw in response.get("Responses", {}).get(self.settings.content_table, []):
                    item = {k: self._deserializer.deserialize(v) for k, v in raw.items()}
                    items[item["PK"]] = item
                request = response.get("UnprocessedKeys") or {}
                if not request:
                    break
        return items

    def _text(self, item: dict, attr: str) -> str:
        if item.get(attr) is not None:
            return str(item[attr])
        ref = item.get(f"{attr}_ref")
        if not ref:
            return ""
        if int(ref.get("bytes", 0)) > MAX_OFFLOAD_BYTES:
            raise ContentIntegrityError("offloaded object is larger than this tutor reads")
        body = self.clients.s3.get_object(Bucket=ref["bucket"], Key=ref["key"])["Body"].read()
        if len(body) != int(ref["bytes"]) or hashlib.sha256(body).hexdigest() != ref["sha256"]:
            raise ContentIntegrityError("offloaded object failed its size/SHA-256 check")
        value = json.loads(body)
        return value if isinstance(value, str) else json.dumps(value)

    @staticmethod
    def _current(item: dict | None, vector_key: str, *, state: str = "vector_state") -> bool:
        if not item:
            return False
        published = item.get("visibility") == "ACTIVE" if item.get("type") == "PROBLEM" else item.get("eligible") is True
        keys = {str(k) for k in ((item.get(state) or {}).get("keys") or [])}
        return published and vector_key in keys

    def _accepted(self, hits: list[dict], items: dict[str, dict], pk: Callable[[dict], str], limit: int,
                  state: str = "vector_state") -> Iterator[tuple[dict, dict]]:
        """Published, current hits in similarity order, within ``relative_window`` of the best accepted one."""
        best: float | None = None
        taken = 0
        for h in hits:
            item = items.get(pk(h))
            if item is None or not self._current(item, h["key"], state=state):
                continue
            if best is None:
                best = h["similarity"]
            elif h["similarity"] < best - self.settings.relative_window:
                return
            if taken == limit:
                return
            taken += 1
            yield h, item

    # ------------------------------------------------------------------ search

    def search(self, topic: str) -> dict:
        topic = clean(topic, MAX_TOPIC_CHARS + 1)
        if len(topic) < 2 or len(topic) > MAX_TOPIC_CHARS:
            raise TopicError(f"topic must be 2-{MAX_TOPIC_CHARS} characters")
        vector = self.embed(topic)
        with ThreadPoolExecutor(max_workers=len(INDEXES)) as pool:
            futures = {family: pool.submit(self._query, family, vector) for family in INDEXES}
            hits = {family: future.result() for family, future in futures.items()}

        pk = {
            "taxonomy": lambda h: f"TAXNODE#{h['metadata'].get('taxonomy_node_id', '')}",
            "step": lambda h: f"STEP#{h['metadata'].get('solution_step_id', '')}",
            "problem": lambda h: f"PROBLEM#{h['metadata'].get('canonical_code', '')}",
        }
        wanted = [pk[f](h) for f, family_hits in hits.items() for h in family_hits if not pk[f](h).endswith("#")]
        items = self._batch_get(wanted) if wanted else {}

        concepts: list[dict] = []
        seen: set[str] = set()
        for h, item in self._accepted(hits["taxonomy"], items, pk["taxonomy"], TOP_K["taxonomy"], "search_vector_state"):
            if len(concepts) == LIMITS["concepts"] or item["taxonomy_node_id"] in seen:
                continue
            seen.add(item["taxonomy_node_id"])
            concepts.append({
                "id": item["taxonomy_node_id"], "name": clean(item.get("name"), 160),
                "type": item.get("node_type"), "summary": clean(self._text(item, "description"), TEXT_LIMITS["summary"]),
                "similarity": h["similarity"],
            })

        moves: list[dict] = []
        for h, item in self._accepted(hits["step"], items, pk["step"], LIMITS["teaching_moves"]):
            text = clean(self._text(item, "step_text"), TEXT_LIMITS["guidance"])
            if text:
                moves.append({"skill": clean(item.get("skill_name"), 160), "guidance": text,
                              "source_problem": item.get("problem_code"), "role": item.get("tutor_role"),
                              "similarity": h["similarity"]})

        problems: list[dict] = []
        for h, item in self._accepted(hits["problem"], items, pk["problem"], TOP_K["problem"]):
            if len(problems) == LIMITS["practice_problems"] or any(p["code"] == item["canonical_code"] for p in problems):
                continue
            statement = clean(self._text(item, "statement_text"), TEXT_LIMITS["statement"])
            if statement:
                problems.append({"code": item["canonical_code"], "source": clean((item.get("competition") or {}).get("name"), 120),
                                 "statement": statement, "similarity": h["similarity"]})

        return {
            "topic": topic,
            "grounded": bool(concepts or moves or problems),
            "concepts": concepts,
            "teaching_moves": moves,
            "practice_problems": problems,
            "source": f"S3 Vectors {self.settings.vector_bucket} + {self.settings.content_table}",
        }


def public_view(result: dict) -> dict:
    """What the browser may display: concepts and practice statements, never the private teaching moves."""
    return {
        "topic": result["topic"], "grounded": result["grounded"], "source": result["source"],
        "concepts": result["concepts"], "practice_problems": result["practice_problems"],
        "teaching_moves": len(result["teaching_moves"]),
    }
