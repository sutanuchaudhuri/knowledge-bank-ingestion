const CODE = "PRASOLOV_PGV1_CH06_P031";
const BASE = { A: [0, 0], B: [7, 1], C: [6, 5], D: [1, 4] };
const finitePoint = (p) => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
const distance = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

export function circumcenter(a, b, c) {
  if (![a, b, c].every(finitePoint)) throw new Error("Circumcenter coordinates must be finite.");
  const u = [b[0] - a[0], b[1] - a[1]], v = [c[0] - a[0], c[1] - a[1]];
  const det = 2 * (u[0] * v[1] - u[1] * v[0]);
  const scale = Math.max(distance(a, b), distance(a, c), distance(b, c));
  if (!scale || Math.abs(det) <= 1e-10 * scale ** 2) throw new Error("The defining triangle is degenerate.");
  const norm = (p) => p[0] ** 2 + p[1] ** 2;
  const center = [
    a[0] + (norm(u) * v[1] - norm(v) * u[1]) / det,
    a[1] + (norm(v) * u[0] - norm(u) * v[0]) / det,
  ];
  const radii = [a, b, c].map((p) => distance(center, p));
  if (!finitePoint(center) || Math.max(...radii) - Math.min(...radii) > 1e-8 * scale) {
    throw new Error("The calculated circumcenter failed the equal-radii check.");
  }
  return center;
}

export function validateVisualFrame(intent, frame) {
  const shown = new Set(frame.elements);
  if (intent.must_show.some((id) => !shown.has(id))) throw new Error("No step-aligned construction yet: a required object is missing.");
  if (frame.level > intent.max_level || frame.claims.length) throw new Error("This construction exceeds the current visual hint.");
  return true;
}

export function buildCircumcenterConstruction(intent, code) {
  const setup = intent?.setup;
  const goals = {
    DEFINE_A1: ["quadrilateral_ABCD", "triangle_BCD", "A1"],
    SHARED_CD: ["triangle_BCD", "triangle_CDA", "A1", "B1", "segment_CD"],
    EQUAL_RADII: ["triangle_BCD", "A1", "radius_A1C", "radius_A1D"],
    ITERATE_CIRCUMCENTERS: ["quadrilateral_A1B1C1D1", "A1", "B1", "C1", "D1"],
  };
  if (code !== CODE || intent?.problem_code !== code || setup?.problem_code !== code ||
      setup?.version !== "circumcenter-iteration-v1" || intent.artifact_goal !== "TEACH_CURRENT_OBJECT" ||
      !goals[intent.current_step] || JSON.stringify(setup.base?.vertices) !== JSON.stringify(Object.keys(BASE)) ||
      setup.definitions?.length !== 8 || !Array.isArray(intent.must_show) ||
      goals[intent.current_step].some((id) => !intent.must_show.includes(id))) {
    throw new Error("No step-aligned construction yet: the visual definition is unavailable or mismatched.");
  }
  const points = Object.fromEntries(Object.entries(BASE).map(([id, p]) => [id, [...p]]));
  const definitions = {};
  for (let level = 1; level <= 2; level++) {
    const parent = [..."ABCD"].map((letter) => level === 1 ? letter : `${letter}1`);
    for (const [i, letter] of [..."ABCD"].entries()) {
      const id = `${letter}${level}`;
      const definition = setup.definitions.find((item) => item.id === id);
      const triangle = [1, 2, 3].map((offset) => parent[(i + offset) % 4]);
      if (definition?.type !== "circumcenter" || definition.level !== level ||
          definition.provenance !== "canonical-statement-definition" ||
          JSON.stringify(definition.triangle) !== JSON.stringify(triangle)) {
        throw new Error(`The definition of ${id} does not match its canonical triangle.`);
      }
      points[id] = circumcenter(...triangle.map((vertex) => points[vertex]));
      definitions[id] = definition;
    }
  }
  const frames = [];
  function frame(caption, centers, { circles = [], radii = [], shared = false, level = 1, allSecond = false } = {}) {
    const parents = level === 1 ? [..."ABCD"] : ["A1", "B1", "C1", "D1"];
    const triangles = centers.filter((id) => definitions[id].level === level);
    const visible = [...new Set([...parents, ...centers, ...(allSecond ? ["A2", "B2", "C2", "D2"] : [])])];
    const elements = [
      `quadrilateral_${parents.join("")}`, ...visible,
      ...(centers.length === 4 ? [`quadrilateral_${centers.join("")}`] : []),
      ...triangles.map((id) => `triangle_${definitions[id].triangle.join("")}`),
      ...circles.map((id) => `circumcircle_${id}`),
      ...radii.flatMap((id) => definitions[id].triangle.map((v) => `radius_${id}${v}`)),
      ...(shared ? ["segment_CD"] : []),
    ];
    // Level-two frames retain the first-level quadrilateral required by the intent.
    const result = { caption, centers, circles, radii, shared, level, allSecond, parents, triangles, visible, elements, claims: [] };
    validateVisualFrame(intent, result);
    frames.push(result);
  }
  switch (intent.current_step) {
    case "DEFINE_A1":
      frame("A₁ is the circumcenter of triangle BCD.", ["A1"]);
      frame("The circumcircle centered at A₁ passes through B, C and D.", ["A1"], { circles: ["A1"], radii: ["A1"] });
      break;
    case "SHARED_CD":
      frame("A₁ comes from BCD; B₁ comes from CDA. Both triangles contain CD.", ["A1", "B1"], { shared: true });
      frame("The two centers belong to different circumcircles through C and D.", ["A1", "B1"], { shared: true, circles: ["A1", "B1"] });
      break;
    case "EQUAL_RADII":
      frame("A₁C and A₁D are radii of the circumcircle of BCD.", ["A1"], { radii: ["A1"] });
      frame("The equal distances follow from the definition of a circumcenter.", ["A1"], { circles: ["A1"], radii: ["A1"] });
      break;
    case "ITERATE_CIRCUMCENTERS":
      frame("The four first-level circumcenters form A₁B₁C₁D₁.", ["A1", "B1", "C1", "D1"]);
      frame("Repeat the same definition: A₂ is the circumcenter of B₁C₁D₁.", ["A2"], { level: 2, circles: ["A2"] });
      frame("The second-level circumcenters form A₂B₂C₂D₂. This illustration is not a similarity proof.", ["A2", "B2", "C2", "D2"], { level: 2, allSecond: true });
      break;
  }
  return { points, definitions, frames, provenance: setup.coordinate_policy };
}

export function constructionViewport(construction, frame) {
  const { points, definitions } = construction;
  const bounds = frame.visible.map((id) => points[id]);
  for (const id of frame.circles) {
    const center = points[id], radius = distance(center, points[definitions[id].triangle[0]]);
    bounds.push([center[0] - radius, center[1] - radius], [center[0] + radius, center[1] + radius]);
  }
  const xs = bounds.map((p) => p[0]), ys = bounds.map((p) => p[1]);
  const minX = Math.min(...xs), minY = Math.min(...ys);
  const width = Math.max(...xs) - minX, height = Math.max(...ys) - minY;
  const scale = Math.min(400 / width, 260 / height);
  if (!Number.isFinite(scale) || scale <= 0) throw new Error("The construction cannot be framed safely.");
  const transform = (p) => [40 + (400 - width * scale) / 2 + (p[0] - minX) * scale, 40 + (260 - height * scale) / 2 + (p[1] - minY) * scale];
  return { point: (id) => transform(points[id]), radius: (id) => distance(points[id], points[definitions[id].triangle[0]]) * scale };
}
