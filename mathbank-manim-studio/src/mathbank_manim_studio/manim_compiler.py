"""Deterministic SceneSpec → real Manim compiler (requirements/60 §3). Translates a
validated SceneSpec dict into literal Manim Python source (never `exec`/`eval` of
untrusted text) and actually invokes the real `manim` CLI as a subprocess to render it.

Security note: `FUNCTION_GRAPH.expr` is the one field that must become a Python lambda
body embedded in generated source. It is never passed through `eval`/`exec` directly;
`_validate_expr` walks the parsed AST and rejects anything outside a small whitelist
(numeric literals, `x`, +-*/**, unary minus, and calls to a fixed set of named math
functions) before the (now provably safe) text is embedded in the generated script.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from mathbank_manim_studio.scene_spec_validation import validate_scene_spec_dict

_ALLOWED_FUNCS = {"sin", "cos", "tan", "sqrt", "exp", "log", "abs"}


class CompileError(ValueError):
    pass


class RenderError(RuntimeError):
    pass


def _validate_expr(expr: str) -> None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise CompileError(f"invalid expression {expr!r}: {exc}") from None
    allowed_node_types = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Load,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Call,
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id != "x" and node.id not in _ALLOWED_FUNCS:
                raise CompileError(f"expression uses a disallowed name {node.id!r}")
        elif isinstance(node, ast.Call):
            if not (isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCS):
                raise CompileError("expression calls a disallowed function")
        elif not isinstance(node, allowed_node_types):
            raise CompileError(f"expression uses a disallowed construct: {type(node).__name__}")


def _expr_to_numpy_lambda_body(expr: str) -> str:
    _validate_expr(expr)
    return re.sub(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\b",
        lambda m: f"np.{m.group(1)}" if m.group(1) in _ALLOWED_FUNCS else m.group(1),
        expr,
    )


def _py_str(value: object) -> str:
    """repr() with the extra guarantee the caller actually wanted a string literal."""
    return repr(str(value))


def _object_statement(obj: dict) -> str:
    oid, otype = obj["id"], obj["type"]
    var = f"obj_{oid}"
    x, y = obj.get("x", 0), obj.get("y", 0)
    if otype == "TITLE_TEXT":
        return f"{var} = Text({_py_str(obj.get('label', ''))}, font_size=42).to_edge(UP)"
    if otype == "TEXT":
        return (f"{var} = Text({_py_str(obj.get('label', ''))}, font_size=32)"
                f".move_to(np.array([{x}, {y}, 0]))")
    if otype == "EQUATION":
        return (f"{var} = MathTex({_py_str(obj.get('latex', ''))}, font_size=36)"
                f".move_to(np.array([{x}, {y}, 0]))")
    if otype == "STATE_NODE":
        return (
            f"_rect_{oid} = RoundedRectangle(width=2.2, height=1.0, corner_radius=0.15)\n"
            f"        _label_{oid} = Text({_py_str(obj.get('label', ''))}, font_size=28)"
            f".move_to(_rect_{oid}.get_center())\n"
            f"        {var} = VGroup(_rect_{oid}, _label_{oid}).move_to(np.array([{x}, {y}, 0]))"
        )
    if otype == "FUNCTION_GRAPH":
        x_range = obj.get("x_range", [-3, 3])
        y_range = obj.get("y_range", [-3, 3])
        lambda_body = _expr_to_numpy_lambda_body(obj.get("expr", "x"))
        return (
            f"_axes_{oid} = Axes(x_range={list(x_range)}, y_range={list(y_range)}, "
            f"x_length=6, y_length=4).move_to(np.array([{x}, {y}, 0]))\n"
            f"        _graph_{oid} = _axes_{oid}.plot(lambda x: {lambda_body}, color=BLUE)\n"
            f"        {var} = VGroup(_axes_{oid}, _graph_{oid})"
        )
    if otype == "GRAPH_POINT":
        on = obj["on"]
        return (
            f"{var} = Dot(_axes_{on}.c2p({obj.get('x', 0)}, {obj.get('y', 0)}), "
            f"color=YELLOW)"
        )
    if otype == "MATRIX":
        rows = obj.get("rows", [["0"]])
        body = r" \\ ".join(" & ".join(str(cell) for cell in row) for row in rows)
        latex = r"\begin{bmatrix}" + body + r"\end{bmatrix}"
        return f"{var} = MathTex({_py_str(latex)}, font_size=36)"
    raise CompileError(f"unsupported object type {otype!r}")


def _animation_expr(action: str, var: str) -> str:
    if action == "SHOW":
        return f"FadeIn({var})"
    if action == "HIDE":
        return f"FadeOut({var})"
    if action == "WRITE":
        return f"Write({var})"
    if action == "HIGHLIGHT":
        return f"Indicate({var}, scale_factor=1.2, color=YELLOW)"
    raise CompileError(f"{action} is not a single-target animation")


def compile_scene_spec_to_manim_source(scene_json: dict, scene_class_name: str = "GeneratedScene"
                                        ) -> str:
    """Pure function: validated SceneSpec dict -> complete, literal Manim Python source."""
    errors = validate_scene_spec_dict(scene_json)
    if errors:
        raise CompileError("invalid SceneSpec: " + "; ".join(errors))

    objects_by_id = {obj["id"]: obj for obj in scene_json["objects"]}
    object_statements = [f"        {_object_statement(obj)}" for obj in scene_json["objects"]]

    timeline = sorted(scene_json["timeline"], key=lambda entry: entry["at_ms"])
    play_lines: list[str] = []
    previous_at_ms = 0
    index = 0
    while index < len(timeline):
        at_ms = timeline[index]["at_ms"]
        group = [e for e in timeline if e["at_ms"] == at_ms]
        index += len(group)

        gap_s = max(0.0, (at_ms - previous_at_ms) / 1000.0 - 1.0) if play_lines else 0.0
        if gap_s > 0.01:
            play_lines.append(f"        self.wait({gap_s:.2f})")

        anims: list[str] = []
        for entry in group:
            action = entry["action"]
            if action == "WAIT":
                duration_s = entry.get("duration_ms", 1000) / 1000.0
                play_lines.append(f"        self.wait({duration_s:.2f})")
                continue
            if action == "DRAW_TRANSITION":
                arrow_var = f"arrow_{uuid4().hex[:8]}"
                anims.append(
                    f"GrowArrow({arrow_var} := Arrow("
                    f"obj_{entry['from']}.get_center(), obj_{entry['to']}.get_center(), buff=0.7))"
                )
                if entry.get("label"):
                    anims.append(
                        f"Write(MathTex({_py_str(entry['label'])}, font_size=28)"
                        f".next_to({arrow_var}, UP, buff=0.15))"
                    )
                continue
            if action == "EQUATION_MORPH":
                anims.append(f"Transform(obj_{entry['from']}, obj_{entry['to']}.copy())")
                continue
            for target in entry.get("targets", []):
                anims.append(_animation_expr(action, f"obj_{target}"))
        if anims:
            play_lines.append(f"        self.play({', '.join(anims)})")
        previous_at_ms = at_ms

    body = "\n".join(object_statements + play_lines) or "        pass"
    return (
        "from manim import *\n"
        "import numpy as np\n\n"
        f"class {scene_class_name}(Scene):\n"
        "    def construct(self):\n"
        f"{body}\n"
    )


def render_scene_spec(scene_json: dict, *, quality: str = "ql") -> tuple[Path, float]:
    """Compiles and actually renders the SceneSpec with the real `manim` CLI. Returns
    (path to the rendered .mp4, duration in seconds). Raises RenderError on failure."""
    source = compile_scene_spec_to_manim_source(scene_json)
    with tempfile.TemporaryDirectory(prefix="manim_studio_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        script_path = tmp_path / "scene.py"
        script_path.write_text(source)
        media_dir = tmp_path / "media"
        # Invoke the same interpreter's `manim` module, not a bare "manim" on PATH, so
        # this works regardless of which venv/shell launched the calling process.
        result = subprocess.run(
            [sys.executable, "-m", "manim", f"-{quality}", "--media_dir", str(media_dir),
             str(script_path), "GeneratedScene"],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            raise RenderError(f"manim render failed: {result.stderr[-4000:]}")
        candidates = list(media_dir.rglob("GeneratedScene.mp4"))
        if not candidates:
            raise RenderError("manim reported success but produced no .mp4")
        rendered = candidates[0]
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(rendered)],
            capture_output=True, text=True, timeout=30,
        )
        duration = float(probe.stdout.strip() or 0.0)
        # Copy out of the TemporaryDirectory before it's cleaned up on context exit.
        persisted = Path(tempfile.mkstemp(suffix=".mp4")[1])
        persisted.write_bytes(rendered.read_bytes())
        return persisted, duration
