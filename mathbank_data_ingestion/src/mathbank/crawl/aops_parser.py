"""
AoPS MediaWiki page parser.

AoPS wiki page structure (rendered MediaWiki HTML):
  <div class="mw-parser-output">
    <h2><span class="mw-headline" id="Problem">Problem</span></h2>
    <p>...problem statement with math in <span class="latex">...</span>...</p>
    <h2><span class="mw-headline" id="Solution">Solution</span></h2>
    <p>...solution text...</p>
    ...optional Solution_2, Solution_3...
  </h2>

Math is either:
  - <span class="latex">$\\frac{1}{2}$</span>  (older pages)
  - Inline text like \\(...\\) or $...$ (wiki source leaked through)
  - MathJax spans with class "math"

Output: ParsedQuestion dataclass with plain-text fields + raw LaTeX preserved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag


# ── Output model ──────────────────────────────────────────────────────────────

@dataclass
class ParsedQuestion:
    question_id: str
    url: str
    problem_text: str          # LaTeX-preserved plain text
    solution_texts: list[str]  # one entry per Solution section found
    answer_choices: list[str]  # e.g. ["A) 12", "B) 24", ...] for MCQ
    answer_value: str          # final boxed answer if found
    image_urls: list[str]      # <img> src values inside problem/solution
    parse_warnings: list[str] = field(default_factory=list)

    @property
    def has_problem(self) -> bool:
        return bool(self.problem_text.strip())

    @property
    def solution_count(self) -> int:
        return len(self.solution_texts)

    def to_md(self) -> str:
        lines = [f"# {self.question_id}", "", "## Problem", "", self.problem_text.strip()]
        for i, sol in enumerate(self.solution_texts, 1):
            label = "Solution" if len(self.solution_texts) == 1 else f"Solution {i}"
            lines += ["", f"## {label}", "", sol.strip()]
        if self.answer_value:
            lines += ["", f"**Answer:** {self.answer_value}"]
        return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

_SECTION_RE = re.compile(r"^(Problem|Solution|See\s+Also|Video|Alternate)", re.I)
_ANSWER_BOX_RE = re.compile(r"\\boxed\{([^}]+)\}")
_AMC_CHOICE_RE = re.compile(
    r"\((?P<letter>[A-E])\)\s*(?P<val>[^(]+?)(?=\s*\([A-E]\)|$)", re.S
)

def _headline_text(tag: Tag) -> str:
    span = tag.find("span", class_="mw-headline")
    return (span.get_text(" ") if span else tag.get_text(" ")).strip()


def _node_to_text(node: Tag | NavigableString) -> str:
    """Convert a BS4 node to LaTeX-preserving plain text."""
    if isinstance(node, NavigableString):
        return str(node)

    # Math spans: preserve LaTeX source
    if node.name == "span" and ("latex" in (node.get("class") or [])
                                 or "math" in (node.get("class") or [])):
        return node.get_text(" ")

    # AoPS image-rendered math: alt contains the LaTeX source (e.g. '$x^2$')
    if node.name == "img":
        alt = (node.get("alt") or "").strip()
        src = node.get("src", "")
        if alt and "latex.artofproblemsolving.com" in src:
            # alt is already dollar-wrapped LaTeX; return as-is
            return alt
        if alt:
            return alt
        if src:
            return f"[IMG:{src}]"
        return ""

    # Lists: convert to readable form
    if node.name in ("ul", "ol"):
        items = []
        for li in node.find_all("li", recursive=False):
            items.append("• " + _subtree_text(li))
        return "\n".join(items)

    if node.name == "li":
        return "• " + _subtree_text(node)

    return _subtree_text(node)


def _subtree_text(tag: Tag) -> str:
    parts = []
    for child in tag.children:
        parts.append(_node_to_text(child))
    return "".join(parts)


def _section_nodes(soup: BeautifulSoup, headline_id_prefix: str) -> list[Tag]:
    """Return all block-level nodes that belong to sections matching the prefix."""
    collecting = False
    nodes: list[Tag] = []
    for tag in soup.select("div.mw-parser-output > *"):
        if tag.name in ("h2", "h3", "h4"):
            text = _headline_text(tag)
            if re.match(rf"^{re.escape(headline_id_prefix)}", text, re.I):
                collecting = True
                continue
            elif collecting and _SECTION_RE.match(text):
                collecting = False
        elif collecting:
            nodes.append(tag)
    return nodes


def _extract_section(soup: BeautifulSoup, prefix: str) -> str:
    nodes = _section_nodes(soup, prefix)
    parts = []
    for node in nodes:
        txt = _node_to_text(node).strip()
        if txt:
            parts.append(txt)
    return "\n\n".join(parts)


def _extract_all_solutions(soup: BeautifulSoup) -> list[str]:
    solutions: list[str] = []
    in_solution = False
    current: list[str] = []

    for tag in soup.select("div.mw-parser-output > *"):
        if tag.name in ("h2", "h3"):
            text = _headline_text(tag)
            if re.match(r"^Solution", text, re.I):
                if in_solution and current:
                    solutions.append("\n\n".join(current))
                    current = []
                in_solution = True
                continue
            elif in_solution and _SECTION_RE.match(text):
                if current:
                    solutions.append("\n\n".join(current))
                    current = []
                in_solution = False
        elif in_solution:
            txt = _node_to_text(tag).strip()
            if txt:
                current.append(txt)

    if in_solution and current:
        solutions.append("\n\n".join(current))

    return solutions or []


def _extract_answer_choices(problem_text: str) -> list[str]:
    choices = _AMC_CHOICE_RE.findall(problem_text)
    return [f"({letter}) {val.strip()}" for letter, val in choices]


def _extract_boxed_answer(solution_text: str) -> str:
    m = _ANSWER_BOX_RE.search(solution_text)
    return m.group(1).strip() if m else ""


def _extract_image_urls(soup: BeautifulSoup, section_prefix: str) -> list[str]:
    nodes = _section_nodes(soup, section_prefix)
    urls: list[str] = []
    for node in nodes:
        for img in node.find_all("img"):
            src = img.get("src", "")
            if src and src not in urls:
                urls.append(src)
    return urls


# ── Public API ────────────────────────────────────────────────────────────────

def parse_aops_page(html: str, question_id: str, url: str) -> ParsedQuestion:
    """Parse an AoPS wiki problem page and return a structured ParsedQuestion."""
    soup = BeautifulSoup(html, "html.parser")
    warnings: list[str] = []

    problem_text = _extract_section(soup, "Problem")
    if not problem_text.strip():
        warnings.append("Problem section not found or empty")

    solution_texts = _extract_all_solutions(soup)
    if not solution_texts:
        warnings.append("No Solution section found")

    answer_choices = _extract_answer_choices(problem_text)
    combined_solutions = "\n\n".join(solution_texts)
    answer_value = _extract_boxed_answer(combined_solutions)

    image_urls: list[str] = []
    for node in soup.select("div.mw-parser-output img"):
        src = node.get("src", "")
        if src and src not in image_urls:
            image_urls.append(src)

    return ParsedQuestion(
        question_id=question_id,
        url=url,
        problem_text=problem_text,
        solution_texts=solution_texts,
        answer_choices=answer_choices,
        answer_value=answer_value,
        image_urls=image_urls,
        parse_warnings=warnings,
    )
