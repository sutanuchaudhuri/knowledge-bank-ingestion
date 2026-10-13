"""CLI for the interaction template library (requirements/41 ITL-13).
Shares the exact same service-layer functions as the REST router
(routers/interaction_templates.py) and the runtime engine
(interaction_runtime.py) — no divergent logic paths.

    python -m mathbank_rest.interactions_cli templates list
    python -m mathbank_rest.interactions_cli templates load-seeds
    python -m mathbank_rest.interactions_cli templates validate <version-id>
    python -m mathbank_rest.interactions_cli templates publish <version-id>
    python -m mathbank_rest.interactions_cli instances validate <instance-id>
    python -m mathbank_rest.interactions_cli instances approve <instance-id>
    python -m mathbank_rest.interactions_cli graph rebuild
    python -m mathbank_rest.interactions_cli graph verify
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import text

from mathbank_rest import interaction_catalog, interaction_validators
from mathbank_rest.db.postgres import engine


def _publish_version(version_id: str) -> dict:
    with engine.begin() as conn:
        errors = interaction_validators.validate_interaction_template_version(conn, version_id)
        if errors:
            return {"status": "REJECTED", "errors": errors}
        conn.execute(
            text("""
            UPDATE visual.interaction_template_version
            SET status='PUBLISHED', published_at=now()
            WHERE interaction_template_version_id=:id AND status IN ('DRAFT','REVIEWED')
        """),
            {"id": version_id},
        )
    return {"status": "PUBLISHED"}


def _approve_instance(instance_id: str) -> dict:
    with engine.begin() as conn:
        errors = interaction_validators.validate_interaction_instance(conn, instance_id)
        if errors:
            return {"status": "REJECTED", "errors": errors}
        conn.execute(
            text("""
            UPDATE visual.interaction_instance SET review_status='APPROVED', approved_at=now()
            WHERE interaction_instance_id=:id AND review_status='PENDING_REVIEW'
        """),
            {"id": instance_id},
        )
    return {"status": "APPROVED"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="group", required=True)

    templates = sub.add_parser("templates").add_subparsers(dest="action", required=True)
    templates.add_parser("list")
    templates.add_parser("load-seeds")
    validate_p = templates.add_parser("validate")
    validate_p.add_argument("version_id")
    publish_p = templates.add_parser("publish")
    publish_p.add_argument("version_id")

    instances = sub.add_parser("instances").add_subparsers(dest="action", required=True)
    inst_validate_p = instances.add_parser("validate")
    inst_validate_p.add_argument("instance_id")
    inst_approve_p = instances.add_parser("approve")
    inst_approve_p.add_argument("instance_id")

    graph = sub.add_parser("graph").add_subparsers(dest="action", required=True)
    graph.add_parser("rebuild")
    graph.add_parser("verify")

    args = parser.parse_args()
    report: object

    if args.group == "templates":
        if args.action == "list":
            with engine.connect() as conn:
                report = interaction_catalog.list_templates(conn)
        elif args.action == "load-seeds":
            with engine.begin() as conn:
                report = interaction_catalog.load_all(conn)
        elif args.action == "validate":
            with engine.connect() as conn:
                report = {
                    "errors": interaction_validators.validate_interaction_template_version(
                        conn, args.version_id
                    )
                }
        elif args.action == "publish":
            report = _publish_version(args.version_id)
    elif args.group == "instances":
        if args.action == "validate":
            with engine.connect() as conn:
                report = {
                    "errors": interaction_validators.validate_interaction_instance(
                        conn, args.instance_id
                    )
                }
        elif args.action == "approve":
            report = _approve_instance(args.instance_id)
    elif args.group == "graph":
        from mathbank_rest import interaction_template_projection as itp

        report = itp.project() if args.action == "rebuild" else itp.verify()
    else:
        parser.error(f"unknown command group {args.group!r}")

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
