"""Offline fakes: no AWS, OpenAI or network access in any test."""
from __future__ import annotations

import hashlib
import io
import json
from typing import Any

from boto3.dynamodb.types import TypeSerializer

_ser = TypeSerializer()


def unit_vector(seed: int = 1) -> list[float]:
    vector = [0.0] * 1536
    vector[seed % 1536] = 1.0
    return vector


def ddb(item: dict) -> dict:
    return {k: _ser.serialize(v) for k, v in item.items()}


class FakeS3Vectors:
    def __init__(self, hits: dict[str, list[dict]]):
        self.hits = hits
        self.calls: list[dict] = []

    def query_vectors(self, **kw: Any) -> dict:
        self.calls.append(kw)
        family = kw["indexName"].split("-te3small")[0]
        return {"vectors": self.hits.get(family, [])}


class FakeDynamo:
    def __init__(self, items: list[dict], unprocessed_once: bool = False):
        self.items = {i["PK"]: i for i in items}
        self.unprocessed_once = unprocessed_once
        self.requests: list[dict] = []

    def batch_get_item(self, RequestItems: dict) -> dict:
        self.requests.append(RequestItems)
        table, spec = next(iter(RequestItems.items()))
        keys = spec["Keys"]
        if self.unprocessed_once:
            self.unprocessed_once = False
            keys, rest = keys[:1], keys[1:]
            unprocessed = {table: {"Keys": rest}} if rest else {}
        else:
            unprocessed = {}
        found = [ddb(self.items[k["PK"]["S"]]) for k in keys if k["PK"]["S"] in self.items]
        return {"Responses": {table: found}, "UnprocessedKeys": unprocessed}


class FakeS3:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[Key])}


def offloaded(value: Any, key: str) -> tuple[dict, bytes]:
    body = json.dumps(value).encode()
    return {"bucket": "mathbank-data-dev", "key": key, "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body), "content_type": "application/json"}, body
