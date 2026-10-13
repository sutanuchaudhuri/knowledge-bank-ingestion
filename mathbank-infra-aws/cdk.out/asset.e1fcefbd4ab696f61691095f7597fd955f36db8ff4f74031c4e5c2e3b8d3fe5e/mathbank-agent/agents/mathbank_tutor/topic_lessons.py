"""Authored instructional checkpoints; no contest solution or model grading."""

from __future__ import annotations

import copy
import re
import time
from decimal import Decimal, InvalidOperation

PLAN_VERSION = "topic-lessons-v1"
POWER = "TECH.GEO.POWER_OF_A_POINT"
STAGES = ("THEORY", "RECOGNITION", "ISOLATED_SKILL", "GUIDED_APPLICATION",
          "MIXED_APPLICATION", "TRANSFER", "ORIGINAL_PROBLEM")
STAGE_META = {
    "THEORY": ("Theory", "TH", "book-half"),
    "RECOGNITION": ("Recognize", "REC", "eye"),
    "ISOLATED_SKILL": ("Skill", "SK", "bullseye"),
    "GUIDED_APPLICATION": ("Guided", "GUIDE", "signpost-split"),
    "MIXED_APPLICATION": ("Mixed", "MIX", "intersect"),
    "TRANSFER": ("Transfer", "TR", "arrow-repeat"),
    "ORIGINAL_PROBLEM": ("Problem", "PROB", "file-earmark-text"),
}

POWER_UNITS = [
    {
        "stage": "THEORY", "title": "Circle, chord, secant and tangent",
        "theory": "A chord joins two points on a circle. A secant line cuts the circle twice; a tangent touches it once. "
                  "Power compares directed segment products from a point to the circle. Start by recognising the configuration.",
        "question": "A chord has which endpoints?",
        "choices": ["One on the circle, one outside", "Both on the circle", "Both at the centre", "Both outside"],
        "answer": "B", "hint": "The endpoints are the two intersections with the circle.",
        "explanation": "A chord is the segment joining two points on the circle.",
        "misconception": "CHORD_ENDPOINTS",
    },
    {
        "stage": "RECOGNITION", "title": "Two chords through one point",
        "theory": "If chords AB and CD meet at P inside a circle, $PA\\cdot PB=PC\\cdot PD$. "
                  "Pair the two segments on the same chord, not segments chosen by appearance.",
        "question": "Which relation matches intersecting chords AB and CD?",
        "choices": ["$PA+PB=PC+PD$", "$PA\\cdot PB=PC\\cdot PD$", "$PA/PC=PB/PD$", "$PA^2=PC\\cdot PD$"],
        "answer": "B", "hint": "Use a product of the two distances along each chord.",
        "explanation": "The intersecting-chords theorem equates the products of the two distances on each chord.",
        "misconception": "ADDITIVE_OR_WRONG_PAIR_POWER",
    },
    {
        "stage": "ISOLATED_SKILL", "title": "Use one segment product",
        "theory": "Write the equality first, then substitute. These numbers form an instructional exercise, not a retrieved contest solution.",
        "question": "For intersecting chords, PA=3, PB=12 and PC=4. What is PD? Enter a number.",
        "input_type": "numeric", "answer_value": "9",
        "hint": "Start with $3\\cdot12=4\\cdot PD$.",
        "explanation": "$3\\cdot12=4\\cdot PD$, so $PD=9$.",
        "misconception": "SEGMENT_PRODUCT_EXECUTION",
    },
    {
        "stage": "GUIDED_APPLICATION", "title": "Tangent and secant",
        "theory": "For external P, tangent PT and secant PAB (A nearer P), $PT^2=PA\\cdot PB$. "
                  "PB is the whole distance from P to the far intersection, not AB.",
        "question": "PT=6 and PA=3. What is the whole secant distance PB?",
        "choices": ["9", "12", "18", "36"],
        "answer": "B", "hint": "Square the tangent: $6^2=3\\cdot PB$.",
        "explanation": "$PT^2=PA\\cdot PB$ gives $36=3PB$, so $PB=12$.",
        "misconception": "TANGENT_SQUARE_OR_WHOLE_SECANT",
    },
    {
        "stage": "MIXED_APPLICATION", "title": "Power and a second skill",
        "theory": "Similar triangles may establish a length ratio; power supplies a segment product. "
                  "Do not apply either theorem until its own hypotheses have been checked.",
        "question": "PAB is a secant with A nearer P. PA=2 and AB=6. If PT is tangent, what is PT?",
        "choices": ["4", "6", "8", "12"],
        "answer": "A", "hint": "First use segment addition to get PB=PA+AB, then $PT^2=PA\\cdot PB$.",
        "explanation": "$PB=PA+AB=8$, so $PT^2=2\\cdot8=16$ and $PT=4$.",
        "misconception": "NEAR_SEGMENT_VERSUS_WHOLE_SECANT",
    },
    {
        "stage": "TRANSFER", "title": "Recognise a hidden cue",
        "theory": "A theorem's name need not appear in a problem. Look for a circle, common point and two secants or a tangent.",
        "question": "From external P, two secants meet the circle at A,B and C,D. Which pairings should you compare?",
        "choices": ["PA with PC, PB with PD", "PA with PB, PC with PD", "AB with CD only", "The sums of all four distances"],
        "answer": "B", "hint": "Keep each near/far pair on its own secant.",
        "explanation": "Each product uses the near and far distances measured along one secant: $PA\\cdot PB$ and $PC\\cdot PD$.",
        "misconception": "TRANSFER_CONFIGURATION",
    },
    {
        "stage": "ORIGINAL_PROBLEM", "title": "Try a source problem",
        "theory": "You reached the end of the introductory path, not a mastery certification. "
                  "Ask for practice to select a complete, step-supported source problem; explain your first move before seeking hints.",
    },
]


def resolve_intent(query: str, active_topic: str | None = None) -> dict:
    """Conservative surface routing; semantic/ambiguous requests stay with the root."""
    value = query.strip()
    if re.search(r"\b(what went wrong|explain.*step|check.*solution)\b", value, re.IGNORECASE):
        return {"intent": "EXPLAIN_STEP", "topic": active_topic}
    for intent, pattern in (
        ("FIND_SIMILAR", r"\b(find|show).*\bsimilar\b"),
        ("SOLVE_PROBLEM", r"\b(solve|prove)\b"),
        ("QUIZ_ME", r"^(quiz me|test me)(?: on (.+))?[.!]?$"),
        ("REVIEW_TOPIC", r"^(review|recap)(?: (.+))?[.!]?$"),
        ("EXPLORE_CORPUS", r"\b(browse|explore).*\b(corpus|database)\b"),
    ):
        if re.search(pattern, value, re.IGNORECASE):
            match = re.fullmatch(pattern, value, re.IGNORECASE) if intent in {"QUIZ_ME", "REVIEW_TOPIC"} else None
            return {"intent": intent, "topic": (match.group(2) if match and match.lastindex and match.lastindex >= 2 else active_topic)}
    if active_topic:
        match = re.fullmatch(r"(?:i know the theory[;,]?\s*(?:just )?)?(?:give me (?:a )?(?:(hard|easy|intermediate) )?(?:problem|practice)|practice|next problem)[.!]?", value, re.IGNORECASE)
        if match:
            return {"intent": "FIND_PRACTICE", "topic": active_topic,
                    "target_difficulty": {"easy": 1, "intermediate": 3, "hard": 5}.get((match.group(1) or "").lower())}
    match = re.fullmatch(
        r"(?:give me|find|show me|i know the theory[;,]?\s*(?:just )?give me)\s+"
        r"(?:a |an |some )?(?:(hard|easy|intermediate)\s+)?(.+?)\s+(?:problem|problems|practice)(?: to try)?[.!]?",
        value, re.IGNORECASE,
    )
    if match:
        return {"intent": "FIND_PRACTICE", "topic": match.group(2).strip(),
                "target_difficulty": {"easy": 1, "intermediate": 3, "hard": 5}.get((match.group(1) or "").lower())}
    match = re.fullmatch(r"(?:give me|find|show me)\s+(?:a |an |some )?(?:(hard|easy|intermediate) )?problems? (?:on|about|using) (.+?)[.!]?", value, re.IGNORECASE)
    if match:
        return {"intent": "FIND_PRACTICE", "topic": match.group(2),
                "target_difficulty": {"easy": 1, "intermediate": 3, "hard": 5}.get((match.group(1) or "").lower())}
    match = re.fullmatch(r"(?:teach me|learn|explain|help me learn)(?: about)?\s+(.+?)[.!]?", value, re.IGNORECASE)
    if match:
        return {"intent": "LEARN_TOPIC", "topic": match.group(1)}
    if active_topic and re.fullmatch(r"[ABCDabcd]|(?:option|choice)\s+[ABCDabcd]|continue|next|resume", value, re.IGNORECASE):
        return {"intent": "CONTINUE_ATTEMPT", "topic": active_topic}
    return {"intent": "LEARN_TOPIC", "topic": value} if len(value) <= 80 and "\n" not in value else {"intent": "UNRESOLVED", "topic": None}


def new_plan(node: dict) -> dict:
    authored = node["taxonomy_node_id"] == POWER
    now = time.time()
    unit_count = len(POWER_UNITS) if authored else 1
    return {"version": PLAN_VERSION, "node_id": node["taxonomy_node_id"], "topic": node["name"],
            "current_unit": 0, "unit_count": unit_count,
            "completed_checkpoints": [], "quiz_results": [],
            "misconceptions": [], "exposed_codes": [], "known_skills": [],
            "status": "ACTIVE", "authored": authored, "revision": 0,
            "stage_status": {str(i): "active" if i == 0 else "pending" for i in range(unit_count)},
            "stage_seconds": {str(i): 0 for i in range(unit_count)},
            "stage_started_at": now, "hint_revealed": False}


def ensure_tracking(plan: dict) -> dict:
    """Add progress fields to sessions created before stage tracking shipped."""
    result = copy.deepcopy(plan)
    count = len(units_for(result))
    result.setdefault("stage_status", {
        str(i): "completed" if i in result.get("completed_checkpoints", [])
        else "active" if i == result.get("current_unit") else "pending"
        for i in range(count)
    })
    result.setdefault("stage_seconds", {str(i): 0 for i in range(count)})
    result.setdefault("stage_started_at", time.time())
    result.setdefault("hint_revealed", False)
    return result


def add_elapsed(plan: dict) -> None:
    started = plan.get("stage_started_at")
    index = str(plan["current_unit"])
    if isinstance(started, (int, float)):
        plan["stage_seconds"][index] = plan["stage_seconds"].get(index, 0) + max(0, int(time.time() - started))
    plan["stage_started_at"] = time.time()


def skip(plan: dict) -> tuple[dict, str]:
    result = ensure_tracking(plan)
    if result["current_unit"] >= len(units_for(result)) - 1:
        return result, "You are already at the final lesson stage. Ask for a problem when you are ready."
    add_elapsed(result)
    current_key = str(result["current_unit"])
    if result["stage_status"].get(current_key) != "completed":
        result["stage_status"][current_key] = "skipped"
    result["current_unit"] += 1
    result["stage_status"][str(result["current_unit"])] = "active"
    result["hint_revealed"] = False
    result["revision"] += 1
    return result, "Stage skipped. It remains marked as skipped, not completed."


def jump(plan: dict, target: int) -> tuple[dict, str]:
    result = ensure_tracking(plan)
    if target < 0 or target >= len(units_for(result)):
        return result, "That lesson stage is not available."
    if target == result["current_unit"]:
        return result, "You are already at that stage."
    add_elapsed(result)
    result["stage_status"][str(result["current_unit"])] = (
        "pending" if result["stage_status"].get(str(result["current_unit"])) == "active"
        else result["stage_status"].get(str(result["current_unit"]), "pending")
    )
    result["current_unit"] = target
    if result["stage_status"].get(str(target)) not in {"completed", "skipped"}:
        result["stage_status"][str(target)] = "active"
    result["hint_revealed"] = False
    result["revision"] += 1
    return result, "Moved to the selected stage. No stage was completed by jumping."


def units_for(plan: dict) -> list[dict]:
    return POWER_UNITS if plan["authored"] else [{
        "stage": "THEORY", "title": "Establish your starting point",
        "theory": f"We identified the canonical topic **{plan['topic']}**. "
                  "A validated authored checkpoint sequence is not available for this topic yet.",
        "question": "Which definitions do you know, and what would you like to understand?",
    }]


def lesson_markdown(plan: dict, notice: str = "") -> str:
    index = plan["current_unit"]
    units = units_for(plan)
    unit = units[index]
    overview = " → ".join(stage.replace("_", " ").title() for stage in STAGES)
    result = f"## Learning plan · {plan['topic']}\n{overview}\n\n"
    result += f"### Step {index + 1} of {len(units)} · {unit['title']}\n{unit['theory']}\n\n"
    if notice:
        result += notice + "\n\n"
    if unit.get("question"):
        result += f"**Checkpoint:** {unit['question']}\n"
        result += "\n".join(f"- **{letter}.** {choice}" for letter, choice in zip("ABCD", unit.get("choices", []), strict=False))
    if plan.get("hint_revealed") and unit.get("hint"):
        result += f"\n\n**Hint:** {unit['hint']}"
    return result


def advance(plan: dict, answer: str) -> tuple[dict, str]:
    result = ensure_tracking(plan)
    units = units_for(result)
    unit = units[result["current_unit"]]
    if not unit.get("answer") and not unit.get("answer_value"):
        return result, "No automatically graded checkpoint is available here. Your tutor can discuss your response; no completion or mastery was inferred."
    if unit.get("input_type") == "numeric":
        try:
            submitted = Decimal(answer.strip())
            expected = Decimal(unit["answer_value"])
        except (InvalidOperation, ValueError):
            return result, "Enter a numeric answer for this checkpoint."
        correct = submitted == expected
        response = {"unit": result["current_unit"], "answer_type": "numeric",
                    "correct": correct}
    else:
        choice = re.fullmatch(r"(?:(?:option|choice)\s+)?([ABCD])", answer.strip(), re.IGNORECASE)
        if not choice:
            return result, "Choose A, B, C or D before moving on. You can also ask the tutor to explain the idea."
        correct = choice.group(1).upper() == unit["answer"]
        response = {"unit": result["current_unit"], "choice": choice.group(1).upper(), "correct": correct}
    result["quiz_results"] = (result["quiz_results"] + [response])[-100:]
    result["revision"] += 1
    if not correct:
        if unit["misconception"] not in result["misconceptions"]:
            result["misconceptions"].append(unit["misconception"])
        result["hint_revealed"] = False
        return result, "Not quite. The checkpoint is still open. Reveal an optional hint or try again."
    add_elapsed(result)
    if result["current_unit"] not in result["completed_checkpoints"]:
        result["completed_checkpoints"].append(result["current_unit"])
    result["stage_status"][str(result["current_unit"])] = "completed"
    result["current_unit"] += 1
    result["stage_status"][str(result["current_unit"])] = "active"
    result["hint_revealed"] = False
    if result["current_unit"] == len(units) - 1:
        result["status"] = "READY_FOR_PRACTICE"
    return result, "Correct. " + unit["explanation"]


def chord_diagram(highlight: str = "all") -> dict:
    """Exact chord incidence: R=140, P displaced 40 from the centre."""
    distance = (140 ** 2 - 40 ** 2) ** 0.5
    points = {"P": (260, 220), "A": (160, 220), "B": (440, 220),
              "C": (260, 220 - distance), "D": (260, 220 + distance)}
    elements = [{"kind": "CIRCLE", "id": "circle", "cx": 300, "cy": 220, "radius": 140}]
    elements += [{"kind": "POINT", "id": name, "x": x, "y": y, "label": name} for name, (x, y) in points.items()]
    for end in ("A", "B", "C", "D"):
        elements.append({"kind": "SEGMENT", "id": f"P{end}", "start": "P", "end": end,
                         "auxiliary": highlight != "all" and end not in highlight})
    frames = [
        ("recognize", "Recognize the circle and intersection", ["circle", "P"]),
        ("first_chord", "Identify PA and PB on the same chord", ["PA", "PB"]),
        ("second_chord", "Identify PC and PD on the other chord", ["PC", "PD"]),
        ("compare", "Compare the two segment products", ["PA", "PB", "PC", "PD"]),
    ]
    return {"subject": "GEOMETRY", "topic": "Power of a point", "title": "Intersecting chords",
            "width": 600, "height": 440, "elements": elements,
            "overlays": [{"id": name, "caption": caption,
                          "actions": [{"action": "HIGHLIGHT", "targets": targets}]}
                         for name, caption, targets in frames],
            "frames": [{"overlay_id": name, "transition": "HIGHLIGHT"} for name, _, _ in frames],
            "summary": "Generated instructional diagram: two chords intersect at P; not a source figure or proof."}
