from __future__ import annotations

import xml.etree.ElementTree as ET

from geometry_scene.schemas import Frame

from .models import CurveState

SVG = "http://www.w3.org/2000/svg"


def render_curves(frame: Frame, curves: tuple[CurveState, ...]) -> str:
    if not curves:
        return frame.svg
    root = ET.fromstring(frame.svg)
    group = ET.Element(f"{{{SVG}}}g", {"data-layer": "provisional", "pointer-events": "none"})
    # Draw behind established geometry. Paths remain open; they are not circle/arc primitives.
    root.insert(0, group)
    for curve in sorted(curves, key=lambda value: value.id):
        points = [frame.scene_state.entities[f"point_{name}"] for name in curve.through]
        coordinates = [(float(point.x), float(point.y)) for point in points]
        commands = [f"M {coordinates[0][0]:.17g} {coordinates[0][1]:.17g}"]
        for index in range(len(coordinates) - 1):
            p0 = coordinates[max(0, index - 1)]
            p1 = coordinates[index]
            p2 = coordinates[index + 1]
            p3 = coordinates[min(len(coordinates) - 1, index + 2)]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            commands.append(
                f"C {c1[0]:.17g} {c1[1]:.17g} {c2[0]:.17g} {c2[1]:.17g} {p2[0]:.17g} {p2[1]:.17g}"
            )
        path = ET.SubElement(
            group,
            f"{{{SVG}}}path",
            {
                "id": curve.id,
                "d": " ".join(commands),
                "fill": "none",
                "stroke": "#64748b",
                "stroke-width": "1.5",
                "stroke-dasharray": "5 5",
                "opacity": "0.55",
                "data-semantic-type": curve.semantic_type,
                "data-category": curve.category,
            },
        )
        ET.SubElement(
            path, f"{{{SVG}}}title"
        ).text = f"{curve.id}: provisional visual guide; not a circle or proven relation"
        x, y = coordinates[0]
        text = ET.SubElement(
            group,
            f"{{{SVG}}}text",
            {
                "x": f"{x:.17g}",
                "y": f"{y - 18:.17g}",
                "fill": "#64748b",
                "font-size": "11",
                "font-family": "sans-serif",
            },
        )
        text.text = f"{curve.id} (provisional)"
    return ET.tostring(root, encoding="unicode")
