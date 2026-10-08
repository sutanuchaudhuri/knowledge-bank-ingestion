import assert from "node:assert/strict";
import test from "node:test";
import { geometrySceneSource, parseGeometryScene, pinnedSceneVersions, sceneFrameCaption, RUN_ID } from "../lib/geometryScenes.mjs";
import { prepareMathMarkdown } from "../lib/markdownText.mjs";

const scene = { scene_id: "triangle_ABC", version: 2, caption: "Draw the altitude.", current_math_step: "step_2" };
const pre = (language, source) => ({ children: [{ tagName: "code", properties: { className: [language] }, children: [{ value: source }] }] });

test("shared staff-page run parser accepts both production receipt prefixes safely", () => {
  for (const prefix of ["run", "failed"]) {
    assert.equal(RUN_ID.test(`${prefix}_0123456789abcdef0123456789abcdef`), true);
  }
  for (const value of ["", "../failed_abc", "run_abc?owner=other", "failed_abc/extra",
    "failed_abc\n", "x".repeat(129)]) assert.equal(RUN_ID.test(value), false);
});

test("typed geometry scene references accept version zero and preserve mathematical captions", () => {
  assert.deepEqual(parseGeometryScene(JSON.stringify(scene)), { scene });
  assert.deepEqual(parseGeometryScene(JSON.stringify({ ...scene, version: 0 })), { scene: { ...scene, version: 0 } });
  assert.deepEqual(geometrySceneSource(pre("language-geometry-scene", JSON.stringify(scene))), { scene });
  assert.equal(geometrySceneSource(pre("language-json", "{}")), null);
});

test("malformed or executable references fail explicitly, open streaming fences stay pending", () => {
  for (const invalid of ["{", "null", "[]", "{}", JSON.stringify({ ...scene, scene_id: "../other" }),
    JSON.stringify({ ...scene, version: -1 }), JSON.stringify({ ...scene, version: 0.5 }),
    JSON.stringify({ ...scene, caption: null }), JSON.stringify({ ...scene, svg: "<svg/>" }),
    JSON.stringify({ ...scene, current_math_step: "" }), JSON.stringify({ ...scene, caption: "x".repeat(2001) })]) {
    assert.ok(parseGeometryScene(invalid).error, invalid);
  }
  assert.deepEqual(parseGeometryScene("{", { pending: true }), { pending: true });
  assert.ok(parseGeometryScene("x".repeat(8193), { pending: true }).error);
  const open = "```geometry-scene\n" + JSON.stringify(scene);
  assert.match(prepareMathMarkdown(open), /```geometry-scene-pending/);
  assert.equal(prepareMathMarkdown(open + "\n```"), open + "\n```");
  assert.match(prepareMathMarkdown("~~~geometry-scene\n{"), /~~~geometry-scene-pending/);
  assert.equal(prepareMathMarkdown("~~~geometry-scene\n{}\n~~~"), "~~~geometry-scene\n{}\n~~~");
  assert.deepEqual(geometrySceneSource(pre("language-geometry-scene-pending", "{")), { pending: true });
});

test("frame navigation excludes all later versions and never trusts supplied render URLs", () => {
  assert.deepEqual(pinnedSceneVersions({ frames: [
    { version: 3, render_path: "https://evil.test" }, { version: 0 }, { version: 1 },
    { version: 1 }, { version: -1 }, { version: "2" }, { version: Number.MAX_SAFE_INTEGER + 1 },
  ] }, 2), [0, 1, 2]);
  assert.throws(() => pinnedSceneVersions({}, 2));
  assert.equal(sceneFrameCaption({ scene_id: scene.scene_id, version: 1, visual_state: { caption: "Earlier caption" } }, scene.scene_id, 1), "Earlier caption");
  assert.throws(() => sceneFrameCaption({ scene_id: scene.scene_id, version: 3, visual_state: { caption: "Future caption" } }, scene.scene_id, 1));
});
