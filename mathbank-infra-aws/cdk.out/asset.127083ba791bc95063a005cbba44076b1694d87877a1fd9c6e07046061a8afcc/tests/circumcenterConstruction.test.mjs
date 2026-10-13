import assert from "node:assert/strict";
import test from "node:test";
import { buildCircumcenterConstruction, circumcenter, constructionViewport, validateVisualFrame } from "../lib/circumcenterConstruction.mjs";
import { CODE, intent } from "./fixtures/circumcenterIntent.mjs";

test("computes a real circumcenter and rejects invalid or collinear inputs", () => {
  assert.deepEqual(circumcenter([0, 0], [4, 0], [0, 4]), [2, 2]);
  assert.throws(() => circumcenter([0, 0], [1, 1], [2, 2]), /degenerate/);
  assert.throws(() => circumcenter([Infinity, 0], [1, 1], [2, 2]), /finite/);
});

test("all eight centers have equal distances to the exact defining vertices", () => {
  const { points, definitions } = buildCircumcenterConstruction(intent(), CODE);
  for (const [id, definition] of Object.entries(definitions)) {
    const distances = definition.triangle.map((vertex) => Math.hypot(points[id][0] - points[vertex][0], points[id][1] - points[vertex][1]));
    assert(Math.max(...distances) - Math.min(...distances) < 1e-8, id);
  }
  assert.deepEqual(definitions.A1.triangle, ["B", "C", "D"]);
  assert.deepEqual(definitions.A2.triangle, ["B1", "C1", "D1"]);
});

for (const step of ["DEFINE_A1", "SHARED_CD", "EQUAL_RADII", "ITERATE_CIRCUMCENTERS"]) {
  test(`every ${step} frame meets its current-object contract and fits the viewport`, () => {
    const request = intent(step), construction = buildCircumcenterConstruction(request, CODE);
    for (const frame of construction.frames) {
      assert(validateVisualFrame(request, frame));
      const viewport = constructionViewport(construction, frame);
      for (const id of frame.visible) {
        const [x, y] = viewport.point(id);
        assert(x >= 39 && x <= 441 && y >= 39 && y <= 301, id);
      }
      for (const id of frame.circles) {
        const [x, y] = viewport.point(id), radius = viewport.radius(id);
        assert(x - radius >= 39 && x + radius <= 441 && y - radius >= 39 && y + radius <= 301, id);
      }
    }
  });
}

test("generic frames, spoilers, wrong problem and altered definitions are refused", () => {
  const request = intent();
  assert.throws(() => validateVisualFrame(request, { elements: ["quadrilateral_ABCD"], level: 1, claims: [] }), /missing/);
  const construction = buildCircumcenterConstruction(request, CODE);
  assert.throws(() => validateVisualFrame(request, { ...construction.frames[0], claims: ["similarity-proof"] }), /exceeds/);
  assert.throws(() => buildCircumcenterConstruction(request, "OTHER"), /mismatched/);
  request.setup.definitions[0].triangle = ["A", "B", "C"];
  assert.throws(() => buildCircumcenterConstruction(request, CODE), /canonical triangle/);
  const unbounded = intent("ITERATE_CIRCUMCENTERS");
  unbounded.max_level = 1;
  assert.throws(() => buildCircumcenterConstruction(unbounded, CODE), /exceeds/);
});
