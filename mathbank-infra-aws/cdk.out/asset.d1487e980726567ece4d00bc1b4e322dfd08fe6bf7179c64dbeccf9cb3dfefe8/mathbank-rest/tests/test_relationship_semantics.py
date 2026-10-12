"""Independent semantic verification must reject plausible but incorrect edges."""

import json
from types import SimpleNamespace

import pytest

from mathbank_rest import tutor
from mathbank_rest.relationship_enrichment import Proposal, verify_semantics


@pytest.mark.parametrize("accepted", [True, False])
def test_semantic_review_accepts_only_explicit_complete_verdicts(monkeypatch, accepted):
    calls = []
    verdict = {
        "reviews": [
            {
                "edge_index": 0,
                "accepted": accepted,
                "reason": "This direction is justified by the supplied definitions.",
            }
        ]
    }

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(verdict)))]
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.with_options = lambda **kwargs: client
    monkeypatch.setattr(tutor, "_client", client)
    proposal = Proposal.model_validate(
        {
            "relationships": [
                {
                    "from_slug": "factor",
                    "to_slug": "solve-quadratic",
                    "relation_type": "PART_OF",
                    "confidence": 0.9,
                    "rationale": "Factoring is a distinct step in solving by factorization.",
                }
            ],
            "explanation": "Catalog descriptions explicitly support this component.",
        }
    )
    if accepted:
        result = verify_semantics("skill", {"slug": "factor"}, [], proposal)
        assert result["reviews"] == verdict["reviews"]
        assert result["model"]
    else:
        with pytest.raises(ValueError, match="Semantic relationship"):
            verify_semantics("skill", {"slug": "factor"}, [], proposal)
    assert "NOT dependent -> prior" in calls[0]["messages"][0]["content"]
    assert "synonymous" in calls[0]["messages"][0]["content"]


def test_empty_proposal_does_not_pay_for_unnecessary_semantic_review(monkeypatch):
    monkeypatch.setattr(tutor, "_client", None)
    assert verify_semantics(
        "concept",
        {},
        [],
        Proposal(
            relationships=[],
            explanation="No definitions justify any proposed relationship.",
        ),
    ) == {"reviews": []}


@pytest.mark.parametrize("indexes", [[], [0, 0], [1]])
def test_semantic_review_rejects_missing_duplicate_or_unknown_verdicts(monkeypatch, indexes):
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=json.dumps(
                                    {
                                        "reviews": [
                                            {
                                                "edge_index": index,
                                                "accepted": True,
                                                "reason": "This component is supported by the target objective.",
                                            }
                                            for index in indexes
                                        ],
                                    }
                                )
                            )
                        )
                    ]
                )
            )
        )
    )
    client.with_options = lambda **kwargs: client
    monkeypatch.setattr(tutor, "_client", client)
    proposal = Proposal.model_validate(
        {
            "relationships": [
                {
                    "from_slug": "factor",
                    "to_slug": "solve-quadratic",
                    "relation_type": "PART_OF",
                    "confidence": 0.9,
                    "rationale": "Factoring is a distinct step in solving by factorization.",
                }
            ],
            "explanation": "Catalog descriptions explicitly support this component.",
        }
    )
    with pytest.raises(ValueError, match="exactly one review"):
        verify_semantics("skill", {"slug": "factor"}, [], proposal)
