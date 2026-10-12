/** Frame transforms stay inside an inert XML document, then become an image blob. */
export function svgFrameImage(source, actions = [], highlight = "currentColor") {
  if (source.length > 2 * 1024 * 1024) throw new Error("The artifact is too large to preview safely.");
  const document = new DOMParser().parseFromString(source, "image/svg+xml");
  if (document.querySelector("parsererror") || document.documentElement.localName !== "svg") throw new Error("The artifact image is not valid SVG.");
  const elements = new Set(["svg", "g", "path", "circle", "ellipse", "line", "polyline", "polygon", "rect", "text", "tspan", "defs", "marker", "clippath", "title", "desc"]);
  const attributes = new Set(["id", "viewbox", "xmlns", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points", "fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "font-size", "font-family", "font-weight", "text-anchor", "dominant-baseline", "transform", "visibility", "display", "markerwidth", "markerheight", "refx", "refy", "orient", "markerunits", "marker-end", "marker-start", "clip-path"]);
  for (const node of [...document.querySelectorAll("*")]) {
    if (!elements.has(node.localName.toLowerCase())) { node.remove(); continue; }
    for (const attribute of [...node.attributes]) {
      const value = attribute.value;
      if (!attributes.has(attribute.name.toLowerCase()) || /javascript:|data:|https?:|@import|expression\s*\(/i.test(value) || (/url\s*\(/i.test(value) && !/^url\(#[A-Za-z0-9_-]+\)$/.test(value))) node.removeAttribute(attribute.name);
    }
  }
  for (const action of actions) {
    const targets = action.targets || action.target_ids || action.element_ids || (action.target_id ? [action.target_id] : []);
    for (const id of targets) {
      const node = [...document.querySelectorAll("[id]")].find((el) => el.id === id);
      if (!node) throw new Error("This frame references a missing visual element.");
      switch (action.action || action.type) {
        case "DIM": node.setAttribute("opacity", ".22"); break;
        case "HIDE": node.setAttribute("visibility", "hidden"); break;
        case "SHOW": node.setAttribute("visibility", "visible"); break;
        case "LABEL": case "RELABEL": {
          const label = ["text", "tspan"].includes(node.localName) ? node : node.querySelector("text");
          if (label) label.textContent = action.label || action.text || "";
          break;
        }
        case "HIGHLIGHT": case "EMPHASIZE_TERM": case "EMPHASIZE_EQUATION_LINE":
          for (const target of [node, ...node.querySelectorAll("*")]) {
            if (["text", "tspan"].includes(target.localName)) {
              target.setAttribute("fill", highlight); target.setAttribute("font-weight", "700");
            } else {
              target.setAttribute("stroke", highlight); target.setAttribute("stroke-width", "3");
            }
          }
          break;
        case "FOCUS_REGION": {
          if (!Array.isArray(action.region) || action.region.length !== 4) break;
          const rectangle = document.createElementNS("http://www.w3.org/2000/svg", "rect");
          ["x", "y", "width", "height"].forEach((name, i) => rectangle.setAttribute(name, String(Number(action.region[i]))));
          rectangle.setAttribute("fill", "none"); rectangle.setAttribute("stroke", highlight); rectangle.setAttribute("stroke-width", "3");
          document.documentElement.append(rectangle);
          break;
        }
        case "MARK_EQUAL": case "MARK_PARALLEL": case "MARK_PERPENDICULAR": {
          const primitive = ["line", "circle", "rect", "text"].includes(node.localName) ? node : node.querySelector("line, circle, rect, text");
          if (!primitive) break;
          const number = (name) => Number(primitive.getAttribute(name) || 0);
          const x = primitive.localName === "line" ? (number("x1") + number("x2")) / 2 : number("cx") || number("x");
          const y = primitive.localName === "line" ? (number("y1") + number("y2")) / 2 : number("cy") || number("y");
          const marker = document.createElementNS("http://www.w3.org/2000/svg", "text");
          marker.setAttribute("x", String(x)); marker.setAttribute("y", String(y - 8));
          marker.setAttribute("fill", highlight); marker.setAttribute("text-anchor", "middle");
          marker.textContent = action.action === "MARK_EQUAL" ? "=" : action.action === "MARK_PARALLEL" ? "∥" : "⊥";
          document.documentElement.append(marker);
          break;
        }
        default: break;
      }
    }
  }
  return new Blob([new XMLSerializer().serializeToString(document)], { type: "image/svg+xml" });
}
