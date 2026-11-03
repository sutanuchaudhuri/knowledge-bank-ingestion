"""Content store (requirement 71 WP4): published content reads, one flag ``CONTENT_STORE=postgres|dynamodb|frozen``.

The store is composed from three area modules so they can evolve independently:

* ``catalog``   competitions, problems, concepts, techniques, tags, images, corpus coverage (access patterns A1-A13)
* ``learning``  answer keys, micro-courses, activity definitions, theorems, release snapshots (A16-A20, A23, A31)
* ``pedagogy``  solution DAG, tutoring routes, taxonomy, topic pedagogy, video, cached hints (A14, A21, A22, A24, A26, A27)

Each area defines ``<Area>Postgres`` (delegates to today's SQL modules, so behaviour and existing tests are unchanged) and
``<Area>DynamoDB`` (typed models via ``stores.typed``; no scans; no Postgres). Method names follow ``stores.READ_PREFIXES`` so a
``frozen`` store serves reads and rejects writes. Callers use ``stores.get_store("content")``.
"""
from __future__ import annotations

from mathbank_rest.stores.content.catalog import CatalogDynamoDB, CatalogPostgres
from mathbank_rest.stores.content.learning import LearningDynamoDB, LearningPostgres
from mathbank_rest.stores.content.pedagogy import PedagogyDynamoDB, PedagogyPostgres


class PostgresContentStore(CatalogPostgres, LearningPostgres, PedagogyPostgres):
    backend = "postgres"


class DynamoDBContentStore(CatalogDynamoDB, LearningDynamoDB, PedagogyDynamoDB):
    backend = "dynamodb"
