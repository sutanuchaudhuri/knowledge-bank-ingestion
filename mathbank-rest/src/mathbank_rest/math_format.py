"""Student math formatting: plain-ish typing -> clean LaTeX (student input add-ons, requirements 29).

``deterministic_format`` is free, instant and always available (it powers the composer's live
"Format" button). ``agentic`` mode asks a small model to rewrite the text with LaTeX delimiters while
keeping the student's words; its output is validated with the same safety rules and falls back to
the deterministic result on any error. The formatter never solves or corrects the mathematics.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable

FORMAT_MODEL = os.getenv("MATH_FORMAT_MODEL", "gpt-4.1-mini")
MAX_CHARS = 4000
_UNSAFE = re.compile(r"\\(href|url|includegraphics|htmlClass|htmlId|htmlStyle|htmlData|input|include|def|"
                     r"newcommand|renewcommand|write|immediate|catcode)\b|<\s*/?\s*script|javascript\s*:", re.I)

_WORD_SYMBOLS = [
    (r"\bangle\s+([A-Z]{3}|[A-Z])\b", r"\\angle \1"),
    (r"\btriangle\s+([A-Z]{3})\b", r"\\triangle \1"),
    (r"\barc\s+([A-Z]{2,3})\b", r"\\overset{\\frown}{\1}"),
    (r"\bsqrt\s*\(([^()]+)\)", r"\\sqrt{\1}"),
    (r"\bsqrt\s*([A-Za-z0-9]+)", r"\\sqrt{\1}"),
    (r"\bpi\b", r"\\pi"),
    (r"\btheta\b", r"\\theta"), (r"\balpha\b", r"\\alpha"), (r"\bbeta\b", r"\\beta"),
    (r"\bgamma\b", r"\\gamma"), (r"\binfinity\b|\binf\b", r"\\infty"),
    (r"\bperp\b|⊥", r"\\perp "), (r"\bparallel\b|∥", r"\\parallel "),
    (r"\bcong\b|≅", r"\\cong "), (r"\bsim\b|∼", r"\\sim "),
]
_OPERATORS = [
    (r"<=|≤", r"\\le "), (r">=|≥", r"\\ge "), (r"!=|≠", r"\\ne "), (r"~=", r"\\cong "),
    (r"\|\|", r"\\parallel "), (r"(?<=\w)\s*\*\s*(?=\w)", r" \\cdot "), (r"·|×", r" \\cdot "),
    (r"°|\bdeg\b|\bdegrees\b", r"^\\circ"), (r"√\s*\(([^()]+)\)", r"\\sqrt{\1}"), (r"√\s*(\w+)", r"\\sqrt{\1}"),
    (r"π", r"\\pi"), (r"θ", r"\\theta"), (r"∠\s*", r"\\angle "), (r"△\s*", r"\\triangle "),
    (r"\b(\w+|\([^()]+\))\s*/\s*(\w+|\([^()]+\))", lambda m: "\\frac{%s}{%s}" % (_strip(m.group(1)), _strip(m.group(2)))),
    (r"\^\s*\(([^()]+)\)", r"^{\1}"), (r"\^(\d{2,})", r"^{\1}"), (r"_(\d{2,}|[a-z]{2,})", r"_{\1}"),
]
# A token is "mathy" when it carries an operator/symbol or is a short all-caps point/segment name.
_MATHY = re.compile(r"[=<>+\-*/^_|°√π∠△·×≤≥≠≅∼∥⊥]|^\(?[A-Z]{1,4}\)?[.,;:]?$|^\d+(\.\d+)?[.,;:]?$|"
                    r"^(angle|triangle|sqrt|pi|theta|alpha|beta|perp|parallel|cong|sim|deg|degrees)\b|\\[a-z]+")
_CONNECTOR = re.compile(r"^(and|or|so|then|since|because|hence|thus|therefore|where|is|are|by|of|"
                        r"if|we|the|a|an|to|in|on|at|with|that|this|it|let|get|gives|from|for)$", re.I)


def _strip(group: str) -> str:
    return group[1:-1] if group.startswith("(") and group.endswith(")") else group


def _latexify(run: str) -> str:
    out = run
    for pattern, repl in _WORD_SYMBOLS + _OPERATORS:
        out = re.sub(pattern, repl, out)
    out = re.sub(r"\s+\^\\circ", r"^\\circ", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def _segment_line(line: str) -> str:
    tokens = line.split(" ")
    flags = []
    for i, tok in enumerate(tokens):
        word = tok.strip()
        mathy = bool(word) and bool(_MATHY.search(word)) and not _CONNECTOR.match(word)
        if word.lower() in ("angle", "triangle", "arc") and i + 1 < len(tokens) and re.match(r"^[A-Z]{1,3}\b", tokens[i + 1]):
            mathy = True
        # A lone capital "A"/"I" starting a sentence is English, not a point name.
        if word in ("A", "I") and (i == 0 or tokens[i - 1].endswith(".")) and not (
                i + 1 < len(tokens) and _MATHY.search(tokens[i + 1]) and tokens[i + 1][:1] in "=<>+-*/^"):
            mathy = False
        flags.append(mathy)
    pieces: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if not run:
            return
        body = " ".join(run)
        trail = ""
        while body and body[-1] in ".,;:":
            trail = body[-1] + trail
            body = body[:-1]
        has_math_signal = re.search(r"[=<>+\-*/^_|°√π∠△·×≤≥≠≅∼∥⊥]|angle|triangle|sqrt|\bpi\b|perp|parallel|"
                                    r"cong|\bsim\b|\b[A-Z]{2,4}\b|\d", body)
        pieces.append((f"${_latexify(body)}$" if has_math_signal else body) + trail)
        run.clear()

    for tok, mathy in zip(tokens, flags):
        if mathy:
            run.append(tok)
        else:
            flush()
            pieces.append(tok)
    flush()
    return " ".join(pieces)


def deterministic_format(text: str) -> str:
    """Wrap math runs in ``$…$`` and convert common typed notation to LaTeX.

    Text that already uses ``$``/``\\(``/``\\[`` delimiters is only normalised, never re-wrapped.
    """
    text = (text or "")[:MAX_CHARS]
    if not text.strip():
        return text
    if re.search(r"\$|\\\(|\\\[", text):
        return text.replace("\\(", "$").replace("\\)", "$").replace("\\[", "$$").replace("\\]", "$$")
    return "\n".join(_segment_line(line) for line in text.split("\n"))


def check_latex(text: str) -> list[str]:
    """Light structural checks shared with the web composer (mirrored in mathbank-widgets)."""
    problems: list[str] = []
    if _UNSAFE.search(text or ""):
        problems.append("contains a disallowed command")
    depth = 0
    for ch in re.sub(r"\\[{}]", "", text or ""):
        depth += ch == "{"
        depth -= ch == "}"
        if depth < 0:
            break
    if depth != 0:
        problems.append("unbalanced braces")
    if len(re.findall(r"(?<!\\)\$", re.sub(r"\$\$", "", text or ""))) % 2:
        problems.append("unbalanced $ delimiters")
    return problems


_AGENT_SYSTEM = (
    "You format a student's mathematical writing. Rewrite the text so every mathematical expression is valid "
    "LaTeX inside $...$ (inline) or $$...$$ (display). Keep the student's words, order and meaning exactly; do "
    "NOT solve, correct, complete or add any mathematics, and do not add commentary. Use \\angle, \\triangle, "
    "\\frac, \\sqrt, \\cdot, \\parallel, \\perp, \\cong, \\sim, ^\\circ where appropriate.")
_AGENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["formatted"],
                 "properties": {"formatted": {"type": "string"}}}


def openai_formatter(text: str) -> str:
    from mathbank_rest.tutor import _client  # loads the project OpenAI key

    response = _client.chat.completions.create(
        model=FORMAT_MODEL, temperature=0, max_tokens=1200,
        response_format={"type": "json_schema", "json_schema": {"name": "math_format", "strict": True,
                                                                "schema": _AGENT_SCHEMA}},
        messages=[{"role": "system", "content": _AGENT_SYSTEM}, {"role": "user", "content": text}])
    return json.loads(response.choices[0].message.content or "{}").get("formatted", "")


def format_math(text: str, mode: str = "deterministic", agent: Callable[[str], str] | None = None) -> dict:
    text = (text or "")[:MAX_CHARS]
    fallback = deterministic_format(text)
    result = {"input": text, "formatted": fallback, "engine": "deterministic", "warnings": check_latex(fallback)}
    if mode != "agentic" or not text.strip():
        return result
    try:
        candidate = (agent or openai_formatter)(text).strip()
    except Exception as exc:  # noqa: BLE001 — any model failure falls back to the deterministic result
        result["warnings"] = result["warnings"] + [f"agentic formatter unavailable ({type(exc).__name__}); used deterministic"]
        return result
    problems = check_latex(candidate)
    plain = lambda s: re.sub(r"[^a-z]", "", s.lower())  # noqa: E731
    # Reject rewrites that drop the student's words (a sign the model answered instead of formatting).
    words = [w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in ("sqrt", "angle", "triangle", "theta")]
    lost = [w for w in words if w not in plain(candidate)]
    if not candidate or problems or len(lost) > max(1, len(words) // 4) or len(candidate) > 3 * len(text) + 200:
        result["warnings"] = result["warnings"] + ["agentic output rejected by validation; used deterministic"]
        return result
    return {"input": text, "formatted": candidate, "engine": "agentic", "model": FORMAT_MODEL, "warnings": []}
