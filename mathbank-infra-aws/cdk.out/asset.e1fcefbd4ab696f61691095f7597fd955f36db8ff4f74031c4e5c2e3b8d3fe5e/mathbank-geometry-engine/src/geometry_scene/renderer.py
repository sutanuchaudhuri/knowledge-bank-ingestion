from __future__ import annotations

import math
import xml.etree.ElementTree as ET

from .policy import arc_points

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
LAYERS = ("base", "construction", "annotations", "overlay", "interaction")


def render(scene, visual):
    def node(parent, tag, **attrs):
        return ET.SubElement(
            parent,
            f"{{{NS}}}{tag}",
            {
                key: format(value, ".17g")
                if isinstance(value, (int, float)) and not isinstance(value, bool)
                else str(value)
                for key, value in attrs.items()
            },
        )

    root = ET.Element(
        f"{{{NS}}}svg",
        {
            "viewBox": " ".join(str(v) for v in visual.view_box),
            "role": "img",
            "aria-labelledby": "scene_title",
            "data-scene-id": scene.scene_id,
            "data-version": str(scene.version),
        },
    )
    node(root, "title", id="scene_title").text = visual.caption or "Constrained geometry scene"
    node(root, "desc", id="scene_description").text = "Illustrative configuration, not a proof."
    layers = {name: node(root, "g", id=name) for name in LAYERS}
    points = {e.refs[0]: (e.x, e.y) for e in scene.entities.values() if e.type == "POINT"}

    def line(group, a, b, **attrs):
        node(group, "line", x1=a[0], y1=a[1], x2=b[0], y2=b[1], **attrs)

    def extended_line(group, a, b, ray=False):
        xmin, ymin, width, height = visual.view_box
        direction = (b[0] - a[0], b[1] - a[1])
        low, high = (0 if ray else -math.inf), math.inf
        for origin, component, start, end in zip(
            a, direction, (xmin, ymin), (xmin + width, ymin + height)
        ):
            if abs(component) < 1e-10:
                if origin < start or origin > end:
                    return
                continue
            first, last = sorted(((start - origin) / component, (end - origin) / component))
            low, high = max(low, first), min(high, last)
        if low <= high and math.isfinite(low) and math.isfinite(high):
            line(
                group,
                (a[0] + low * direction[0], a[1] + low * direction[1]),
                (a[0] + high * direction[0], a[1] + high * direction[1]),
            )

    def arc(group, a, b, c, **attrs):
        u, v = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
        norm_u, norm_v = math.hypot(*u), math.hypot(*v)
        if min(norm_u, norm_v) < 1e-8:
            return
        p = (b[0] + 18 * u[0] / norm_u, b[1] + 18 * u[1] / norm_u)
        q = (b[0] + 18 * v[0] / norm_v, b[1] + 18 * v[1] / norm_v)
        sweep = 1 if u[0] * v[1] - u[1] * v[0] >= 0 else 0
        node(group, "path", d=f"M {p[0]} {p[1]} A 18 18 0 0 {sweep} {q[0]} {q[1]}", **attrs)

    for name, entity in sorted(scene.entities.items()):
        style = visual.styles[name]
        layer = (
            "annotations"
            if "MARK" in entity.type
            else "construction"
            if entity.role in ("AUXILIARY", "EXTENSION")
            else "base"
        )
        group = node(
            layers[layer],
            "g",
            id=name,
            **{
                "data-semantic-id": name,
                "data-entity-type": entity.type,
                "data-relation-id": entity.relation_id or "",
                "opacity": style.opacity,
                "display": "inline" if style.visible else "none",
                "stroke": "#d97706" if style.emphasis == "HIGHLIGHT" else "#334155",
                "stroke-width": 1 if style.emphasis == "BACKGROUND" else 2.5,
                "stroke-dasharray": "6 5" if style.line_style == "DASHED" else "none",
                "fill": "none",
            },
        )
        refs = [points[p] for p in entity.refs if p in points]
        if entity.type == "POINT":
            node(
                group,
                "circle",
                cx=entity.x,
                cy=entity.y,
                r=5 if entity.role == "CONTACT" or style.emphasis == "HIGHLIGHT" else 3,
                fill="#d97706" if style.emphasis == "HIGHLIGHT" else "#334155",
            )
            if style.label and style.label_position:
                label = node(
                    layers["annotations"],
                    "text",
                    id=f"label_{entity.refs[0]}",
                    x=style.label_position[0],
                    y=style.label_position[1],
                    **{
                        "font-size": 15,
                        "font-family": "system-ui, sans-serif",
                        "fill": "#0f172a",
                        "display": "inline" if style.visible else "none",
                    },
                )
                label.text = style.label
        elif entity.type == "SEGMENT":
            line(group, refs[0], refs[-1])
        elif entity.type in ("LINE", "RAY"):
            extended_line(group, refs[0], refs[-1], entity.type == "RAY")
        elif entity.type == "POLYGON":
            node(group, "polygon", points=" ".join(f"{x},{y}" for x, y in refs))
        elif entity.type in ("CIRCLE", "ARC"):
            if style.render_mode == "VISIBLE_ARC" or entity.type == "ARC":
                p, q = arc_points(entity, style)
                angle = style.arc_angles[1] - style.arc_angles[0]
                node(
                    group,
                    "path",
                    d=f"M {p[0]} {p[1]} A {entity.radius} {entity.radius} "
                    f"0 {int(abs(angle) > 180)} {int(angle >= 0)} {q[0]} {q[1]}",
                )
            else:
                node(group, "circle", cx=entity.x, cy=entity.y, r=entity.radius)
        elif entity.type in ("EQUAL_LENGTH_MARK", "PARALLEL_MARK"):
            for a, b in zip(refs[::2], refs[1::2]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy)
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                normal = (-dy * 5 / length, dx * 5 / length)
                if entity.type == "PARALLEL_MARK":
                    tail = (m[0] - dx * 6 / length, m[1] - dy * 6 / length)
                    line(group, (tail[0] + normal[0], tail[1] + normal[1]), m)
                    line(group, (tail[0] - normal[0], tail[1] - normal[1]), m)
                else:
                    line(
                        group,
                        (m[0] - normal[0], m[1] - normal[1]),
                        (m[0] + normal[0], m[1] + normal[1]),
                    )
        elif entity.type == "RIGHT_ANGLE_MARK":
            # Four refs denote two lines; the shared vertex is established by the state.
            a, b, c, d = refs
            vertex = b if b in (c, d) else c if c == a else d if d == a else b
            other1 = a if a != vertex else b
            other2 = c if c != vertex else d
            if vertex not in (c, d):
                other2 = (vertex[0] + d[0] - c[0], vertex[1] + d[1] - c[1])
            u = (other1[0] - vertex[0], other1[1] - vertex[1])
            v = (other2[0] - vertex[0], other2[1] - vertex[1])
            lu, lv = math.hypot(*u), math.hypot(*v)
            p = (vertex[0] + 10 * u[0] / lu, vertex[1] + 10 * u[1] / lu)
            q = (vertex[0] + 10 * v[0] / lv, vertex[1] + 10 * v[1] / lv)
            middle = (p[0] + q[0] - vertex[0], p[1] + q[1] - vertex[1])
            node(group, "polyline", points=f"{p[0]},{p[1]} {middle[0]},{middle[1]} {q[0]},{q[1]}")
        elif entity.type == "ANGLE_MARK":
            for index in range(0, len(refs), 3):
                arc(group, *refs[index : index + 3])
        elif entity.type == "CORRESPONDENCE_MARK":
            node(
                group, "text", x=24, y=32, fill="#334155", stroke="none"
            ).text = f"{''.join(entity.refs[:3])} ~ {''.join(entity.refs[3:])}"
    for overlay in visual.overlays:
        group = node(
            layers["overlay"],
            "g",
            id=overlay.id,
            **{
                "data-targets": " ".join(overlay.targets),
                "pointer-events": "none",
            },
        )
        node(group, "title").text = overlay.caption
        for target in overlay.targets:
            if visual.styles[target].visible:
                node(group, "use", href="#" + target)
    return ET.tostring(root, encoding="unicode")
