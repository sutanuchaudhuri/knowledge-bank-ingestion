"""Vector index spec API used by aws/s3/vector_indexes.py."""
from __future__ import annotations

import dataclasses
from typing import Callable


@dataclasses.dataclass
class VectorIndex:
    name: str                                   # S3 Vectors index name, e.g. misconception-te3small-1536-v1
    sql: str                                    # SELECT key, embedding::text AS embedding, <metadata columns>
    metadata: Callable[[dict], dict]            # row → metadata dict (filterable + non-filterable keys)
    non_filterable: tuple[str, ...] = ()        # metadata keys excluded from filtering (≤ 10)
    expected_source: str | None = None          # SQL expression for the expected vector count
    filter_key: str | None = None               # metadata key used to partition exact-recall checks (e.g. node_type)
    dimension: int = 1536
    metric: str = "cosine"
    note: str = ""
