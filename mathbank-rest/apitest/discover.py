"""Find real fixtures in the migrated `dev` data: students with the most history, their quizzes, and a token for each.

Read-only (DynamoDB scans of the small learner/exam tables; the harness is not a request path). Tokens are minted locally from
JWT_SECRET exactly as the API would, with the student's current token_version, so no password is needed.
"""
from __future__ import annotations

import collections
import uuid

import boto3
from boto3.dynamodb.types import TypeDeserializer

_DES = TypeDeserializer()


def _scan(client, table: str, **kw):
    for page in client.get_paginator("scan").paginate(TableName=table, **kw):
        for item in page["Items"]:
            yield {k: _DES.deserialize(v) for k, v in item.items()}


def _token(student_id: str, token_version: int) -> str:
    from mathbank_rest.security import create_access_token

    return create_access_token(uuid.UUID(student_id), token_version)


def discover(profile: str, env: str = "dev", region: str = "us-east-2") -> dict:
    client = boto3.Session(profile_name=profile, region_name=region).client("dynamodb")
    items_per_student: collections.Counter = collections.Counter()
    profiles: dict[str, dict] = {}
    for it in _scan(client, f"mb-learner-{env}"):
        items_per_student[it["PK"]] += 1
        if it.get("type") == "PROFILE" and it.get("status") == "ACTIVE":
            profiles[it["PK"]] = it
    ranked = [pk for pk, _ in items_per_student.most_common() if pk in profiles]
    fx: dict = {"students": []}
    for pk in ranked[:3]:
        p = profiles[pk]
        sid = str(p["student_id"])
        fx["students"].append({"id": sid, "token": _token(sid, int(p.get("token_version", 0))), "items": items_per_student[pk],
                               "cognito_sub": str(p["cognito_sub"]) if p.get("cognito_sub") else None})
    papers: list[dict] = []
    questions: dict[str, str] = {}
    for it in _scan(client, f"mb-exam-{env}"):
        if it.get("type") == "PAPER":
            papers.append(it)
        elif it.get("type") == "QUESTION":
            questions.setdefault(str(it["quiz_id"]), str(it.get("question_id") or it["SK"].rsplit("#", 1)[-1]))
    by_status = collections.defaultdict(list)
    for p in papers:
        by_status[str(p["status"])].append(p)
    fx["papers"] = {}
    for status, rows in by_status.items():
        p = rows[0]
        owner = str(p["student_id"])
        prof = next((v for v in profiles.values() if str(v["student_id"]) == owner), None)
        fx["papers"][status] = {"quiz_id": str(p["quiz_id"]), "student_id": owner, "question_id": questions.get(str(p["quiz_id"])),
                                "token": _token(owner, int(prof.get("token_version", 0))) if prof else None}
    return fx
