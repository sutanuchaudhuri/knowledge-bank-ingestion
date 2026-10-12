import json
import subprocess
from pathlib import Path

import pytest

from mathbank_manim_studio.manim_compiler import (
    CompileError,
    compile_scene_spec_to_manim_source,
    render_scene_spec,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "markov_two_state.json").read_text()
)


def test_compiles_to_syntactically_valid_python():
    source = compile_scene_spec_to_manim_source(FIXTURE)
    compile(source, "<generated>", "exec")  # raises SyntaxError if malformed


def test_compile_rejects_invalid_scene_spec():
    with pytest.raises(CompileError):
        compile_scene_spec_to_manim_source({"scene_key": "x", "objects": [], "timeline": []})


def test_compile_rejects_unsafe_function_graph_expression():
    spec = {
        "scene_key": "x", "scene_version": 1,
        "objects": [{"id": "f", "type": "FUNCTION_GRAPH", "expr": "__import__('os').system('echo hi')"}],
        "timeline": [{"at_ms": 0, "action": "SHOW", "targets": ["f"]}],
    }
    with pytest.raises(CompileError):
        compile_scene_spec_to_manim_source(spec)


def test_real_manim_render_produces_a_playable_video():
    """The single most important test in this project: proves the full compile ->
    real `manim` subprocess -> real .mp4 pipeline genuinely works, not just that the
    generated source parses."""
    path, duration_s = render_scene_spec(FIXTURE)
    try:
        assert path.is_file()
        assert path.stat().st_size > 1000
        assert duration_s > 1.0
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        assert "video" in probe.stdout
    finally:
        path.unlink(missing_ok=True)


def test_real_manim_render_with_function_graph_and_point():
    spec = {
        "scene_key": "parabola_demo", "scene_version": 1,
        "objects": [
            {"id": "title", "type": "TITLE_TEXT", "label": "y = x^2"},
            {"id": "fx", "type": "FUNCTION_GRAPH", "expr": "x**2", "x_range": [-3, 3],
             "y_range": [0, 9]},
            {"id": "pt", "type": "GRAPH_POINT", "on": "fx", "x": 2, "y": 4},
        ],
        "timeline": [
            {"at_ms": 0, "action": "SHOW", "targets": ["title"]},
            {"at_ms": 500, "action": "SHOW", "targets": ["fx"]},
            {"at_ms": 1500, "action": "SHOW", "targets": ["pt"]},
        ],
    }
    path, duration_s = render_scene_spec(spec)
    try:
        assert path.is_file() and path.stat().st_size > 1000
    finally:
        path.unlink(missing_ok=True)
