from __future__ import annotations

import math

from .errors import GeometryError
from .schemas import ESTABLISHED, Style, VisualState


def label_bounds(position, label):
    x, y = position
    return (x, y - 13, x + max(10, len(label) * 9), y + 4)


def overlaps(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def apply_policy(math_state, scene_state, previous, delta):
    entities = scene_state.entities
    styles = {name: style.model_copy(deep=True) for name, style in previous.styles.items()}
    relations = {r.id: r for r in math_state.relations}
    for name, entity in entities.items():
        if name not in styles:
            secondary = entity.type in ("CIRCLE", "ARC") or entity.role == "AUXILIARY"
            styles[name] = Style(
                emphasis="BACKGROUND" if secondary else "PRIMARY",
                opacity=0.35 if entity.type in ("CIRCLE", "ARC") else 0.7 if secondary else 1,
                line_style="DASHED" if entity.role in ("AUXILIARY", "EXTENSION") else "SOLID",
                label=entity.refs[0] if entity.type == "POINT" else None,
            )
        if entity.relation_id and relations[entity.relation_id].status not in ESTABLISHED:
            styles[name] = styles[name].model_copy(update={"visible": False})
    actions = (*delta.show, *delta.hide, *delta.highlight, *delta.dim, *delta.focus, *delta.styles)
    for name in actions:
        if name not in entities:
            raise GeometryError(f"visual reference does not exist: {name}")
    for name, style in delta.styles.items():
        styles[name] = style.model_copy(deep=True)
    for name in delta.show:
        styles[name] = styles[name].model_copy(update={"visible": True})
    for name in delta.hide:
        styles[name] = styles[name].model_copy(update={"visible": False})
    if delta.highlight or delta.focus:
        for name, style in styles.items():
            if style.emphasis == "HIGHLIGHT":
                secondary = entities[name].type in ("CIRCLE", "ARC")
                styles[name] = style.model_copy(
                    update={
                        "emphasis": "BACKGROUND" if secondary else "PRIMARY",
                        "opacity": 0.35 if secondary else 1,
                    }
                )
    for name in (*delta.highlight, *delta.focus):
        styles[name] = styles[name].model_copy(update={"visible": True, "emphasis": "HIGHLIGHT"})
    for name in delta.dim:
        styles[name] = styles[name].model_copy(update={"emphasis": "DIM", "opacity": 0.35})
    for name, entity in entities.items():
        if entity.role in ("EXTENSION", "AUXILIARY") and entity.type in ("SEGMENT", "LINE", "RAY"):
            styles[name] = styles[name].model_copy(update={"line_style": "DASHED"})
    overlays = {overlay.id: overlay for overlay in previous.overlays}
    for overlay in delta.overlays:
        if overlay.id in entities or overlay.id in (
            "base",
            "construction",
            "annotations",
            "overlay",
            "interaction",
        ):
            raise GeometryError("overlay ID collides with scene/layer identity")
        if overlay.id in overlays and overlays[overlay.id] != overlay:
            raise GeometryError("cannot replace cumulative overlay identity")
        if any(target not in entities for target in overlay.targets):
            raise GeometryError(f"overlay refers to nonexistent entity: {overlay.id}")
        overlays[overlay.id] = overlay
    if len(overlays) > 32:
        raise GeometryError("overlay limit exceeded")
    xmin, ymin, width, height = previous.view_box
    bounds = []
    points = [e for _, e in sorted(entities.items()) if e.type == "POINT" and styles[e.id].visible]
    # Fixed deterministic candidate search; point and existing label boxes both matter.
    for point in points:
        style = styles[point.id]
        if not style.label:
            continue
        candidates = [
            (point.x + 12, point.y - 10),
            (point.x + 12, point.y + 22),
            (point.x - len(style.label) * 9 - 12, point.y - 10),
            (point.x - len(style.label) * 9 - 12, point.y + 22),
        ]
        position = None
        for candidate in candidates:
            box = label_bounds(candidate, style.label)
            if box[0] < xmin + 4 or box[1] < ymin + 4:
                continue
            if box[2] > xmin + width - 4 or box[3] > ymin + height - 4:
                continue
            if any(overlaps(box, b) for b in bounds):
                continue
            if any(overlaps(box, (p.x - 5, p.y - 5, p.x + 5, p.y + 5)) for p in points):
                continue
            position = candidate
            bounds.append(box)
            break
        if position is None:
            raise GeometryError(f"no collision-free in-viewport label position for {point.id}")
        styles[point.id] = style.model_copy(update={"label_position": position})
    return VisualState(
        version=scene_state.version,
        styles=styles,
        focus=delta.focus or previous.focus,
        caption=previous.caption if delta.caption is None else delta.caption,
        view_box=previous.view_box,
        overlays=tuple(overlays.values()),
    )


def arc_points(entity, style):
    start, end = (math.radians(a) for a in style.arc_angles)
    return (
        (entity.x + entity.radius * math.cos(start), entity.y + entity.radius * math.sin(start)),
        (entity.x + entity.radius * math.cos(end), entity.y + entity.radius * math.sin(end)),
    )
