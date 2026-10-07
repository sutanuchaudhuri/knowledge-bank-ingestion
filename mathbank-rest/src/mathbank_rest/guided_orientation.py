"""Authored, statement-gated orientation checks; never a complete solution."""

from mathbank_rest.guided_visuals import visual_intent

JOURNEY = [
    {"id": "understand", "title": "Understand", "icon": "search"},
    {"id": "plan", "title": "Plan", "icon": "signpost-split"},
    {"id": "work", "title": "Work", "icon": "pencil"},
    {"id": "check", "title": "Check", "icon": "check2-circle"},
    {"id": "reflect", "title": "Reflect", "icon": "lightbulb"},
]


def _checks(problem: dict) -> list[dict]:
    code = problem["canonical_code"]
    statement = problem.get("statement_text", "")
    if code == "PRASOLOV_PGV1_CH06_P031" and all(
        word in statement.lower() for word in ("circumscribed", "bcd", "cda")
    ):
        return [
            {
                "prompt": "Which triangle defines the circumcenter $A_1$?",
                "choices": ["BCD", "CDA", "DAB", "ABC"],
                "answer": "BCD",
                "explanation": "The statement defines $A_1$ as the center of the circle through $B,C,D$.",
                "nudge": "Read the order of the four centers and their defining triangles.",
            },
            {
                "prompt": "The triangles defining $A_1$ and $B_1$ share which side?",
                "choices": ["CD", "DA", "BC", "AB"],
                "answer": "CD",
                "explanation": "The defining triangles are $BCD$ and $CDA$, so both contain $C$ and $D$.",
                "nudge": "Compare the vertex lists BCD and CDA.",
            },
            {
                "prompt": "What distance relation follows from $A_1$ being a circumcenter?",
                "choices": ["$A_1C=A_1D$", "$A_1C$ is perpendicular to $A_1D$", "$A_1$ lies on $CD$"],
                "answer": "$A_1C=A_1D$",
                "explanation": "Both distances are radii of the same circle. This is a definition, not the similarity proof.",
                "nudge": "A circle's center has the same distance to every point on that circle.",
            },
        ]
    if code == "AIME_1985_Q01" and all(word in statement for word in ("97", "x_", "product")):
        return [
            {
                "prompt": "Which term is given directly in the statement?",
                "choices": ["$x_1=97$", "$x_2=97$", "$x_8=97$"],
                "answer": "$x_1=97$",
                "explanation": "The initial condition is $x_1=97$; later terms follow from the recurrence.",
                "nudge": "Look at the initial condition, before the recurrence.",
            },
            {
                "prompt": "Using the recurrence at $n=2$, what is $x_2$?",
                "choices": ["$2/97$", "$97/2$", "$2\\cdot97$"],
                "answer": "$2/97$",
                "explanation": "Substitute $n=2$ and $x_1=97$ into $x_n=n/x_{n-1}$. The requested product is still for you to find.",
                "nudge": "The previous term belongs in the denominator.",
            },
        ]
    return []


def orientation(problem: dict, index: int = 0) -> dict:
    checks = _checks(problem)
    action = {
        "action": "REQUEST_STUDENT_STEP", "response_type": "TEXT",
        "goal": "PLAN", "prompt": "Write one relation or starting idea you can justify from the statement.",
    }
    if index < len(checks):
        action = {
            "action": "ASK_MICRO_CHECK", "response_type": "MCQ", "goal": "UNDERSTAND",
            "index": index, "prompt": checks[index]["prompt"], "choices": checks[index]["choices"],
        }
    return {
        "journey": JOURNEY, "active_prompt": action,
        "orientation_count": len(checks), "completed_orientation": min(index, len(checks)),
        "status": "temporary", "provenance": "authored-statement-gated" if checks else "generic-workspace",
        "visual_intent": visual_intent(problem, index),
    }


def check_orientation(problem: dict, index: int, response: str) -> dict:
    checks = _checks(problem)
    if index < 0 or index >= len(checks):
        raise ValueError("No authored orientation check at that index.")
    check = checks[index]
    if response not in check["choices"] and response != "hint":
        raise ValueError("Choose one of the current orientation responses.")
    if response == "hint":
        return {"hint": check["nudge"], "session": orientation(problem, index)}
    correct = response == check["answer"]
    return {
        "correct": correct,
        "explanation": check["explanation"] if correct else "Not quite. Re-read the defining information and try again, or request a small nudge.",
        "session": orientation(problem, index + 1 if correct else index),
    }
