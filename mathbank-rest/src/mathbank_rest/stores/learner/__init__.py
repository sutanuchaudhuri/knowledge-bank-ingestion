"""Learner store (requirement 71 WP5): every learner-owned read and write, one flag ``LEARNER_STORE=postgres|dynamodb|frozen``.

Composed from area modules (one per C1 store) so they evolve independently:

* ``identity``    IdentityStore   profiles, login, Cognito link, status/token version, password (T1-T6, A1-A5)
* ``outcomes``    OutcomeStore    outcomes, mastery evidence and scores, practice progress, daily activity, cohort (T7, A6-A9, A41, A42)
* ``solve``       SolveRuntimeStore  attempts, step state, hints, step outcome, stale sessions, learner events (T8-T12, A10-A18)
* ``diagnosis``   DiagnosisStore  diagnoses, gaps, gap overview (T13, A19-A22)
* ``recovery``    RecoveryStore   recovery plans (T14-T16, A23-A25)
* ``microcourse`` MicroCourseRuntimeStore  enrollments, item/activity responses, interaction events, misconception state (A26-A32)
* ``routes``      RouteAttemptStore, FeedbackStore, AgentLinkStore  (A33-A40)
* ``admin``       admin learner directory, events, erasure, account disable, integrity (A5, A17, A22, A25, A40, A43)

Each area defines ``<Area>Postgres`` (delegates to today's functions at call time) and ``<Area>DynamoDB`` (typed models,
``LearnerUnitOfWork``, no scans, no Postgres). Method names follow ``stores.READ_PREFIXES`` so a ``frozen`` store serves
reads and rejects writes. Callers use ``stores.get_store("learner")``.
"""
from __future__ import annotations

from mathbank_rest.stores.learner.admin import AdminDynamoDB, AdminPostgres
from mathbank_rest.stores.learner.diagnosis import DiagnosisDynamoDB, DiagnosisPostgres
from mathbank_rest.stores.learner.identity import IdentityDynamoDB, IdentityPostgres
from mathbank_rest.stores.learner.microcourse import MicroCourseDynamoDB, MicroCoursePostgres
from mathbank_rest.stores.learner.outcomes import OutcomesDynamoDB, OutcomesPostgres
from mathbank_rest.stores.learner.recovery import RecoveryDynamoDB, RecoveryPostgres
from mathbank_rest.stores.learner.routes import RoutesDynamoDB, RoutesPostgres
from mathbank_rest.stores.learner.solve import SolveDynamoDB, SolvePostgres


class PostgresLearnerStore(IdentityPostgres, OutcomesPostgres, SolvePostgres, DiagnosisPostgres, RecoveryPostgres,
                           MicroCoursePostgres, RoutesPostgres, AdminPostgres):
    backend = "postgres"


class DynamoDBLearnerStore(IdentityDynamoDB, OutcomesDynamoDB, SolveDynamoDB, DiagnosisDynamoDB, RecoveryDynamoDB,
                           MicroCourseDynamoDB, RoutesDynamoDB, AdminDynamoDB):
    backend = "dynamodb"
