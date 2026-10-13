"""The "video creator agent" (requirements/60 §1): given a validated SceneSpec JSON,
actually renders it with Manim and stores the result. Pure orchestration — all the real
work is `manim_compiler.render_scene_spec` (compile + render) and `object_store.put_file`
(persist); this module just wires the two together and cleans up the temp file.
"""
from __future__ import annotations

from pathlib import Path

from mathbank_manim_studio import object_store
from mathbank_manim_studio.manim_compiler import render_scene_spec
from mathbank_manim_studio.scene_spec_validation import validate_scene_spec_dict


def render_and_store(scene_spec_json: dict) -> tuple[str, int]:
    """Returns (video_object_key, duration_ms). Raises ValueError if the SceneSpec is
    invalid, RenderError if `manim` itself fails."""
    errors = validate_scene_spec_dict(scene_spec_json)
    if errors:
        raise ValueError("invalid SceneSpec: " + "; ".join(errors))

    rendered_path, duration_s = render_scene_spec(scene_spec_json)
    try:
        object_key = object_store.put_file(rendered_path, "mp4")
    finally:
        Path(rendered_path).unlink(missing_ok=True)
    return object_key, round(duration_s * 1000)
