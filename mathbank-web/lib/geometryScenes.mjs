export const SCENE_ID = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;
// Shared by staff pages and proxies; includes run_<hex> and failed_<hex> receipts.
export const RUN_ID = /^[A-Za-z0-9_-]{1,128}$/;
export const DEBUG_OWNER = /^(?:admin|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$/;
export const sceneVersion = (value) => Number.isSafeInteger(value) && value >= 0;

/** @typedef {{scene_id: string, version: number, caption: string, current_math_step?: string}} GeometrySceneReference */

/** Parse a declarative reference, never scene geometry or executable markup. */
export function parseGeometryScene(source, { pending = false } = {}) {
  if (source.length > 8192) return { error: "The geometry scene reference is too large." };
  if (pending) return { pending: true };
  try {
    const value = JSON.parse(source);
    const keys = ["scene_id", "version", "caption", "current_math_step"];
    if (!value || Array.isArray(value) || typeof value !== "object"
      || Object.keys(value).some((key) => !keys.includes(key))
      || !SCENE_ID.test(value.scene_id || "") || !sceneVersion(value.version)
      || typeof value.caption !== "string" || value.caption.length > 2000
      || (value.current_math_step !== undefined && (typeof value.current_math_step !== "string"
        || !value.current_math_step.trim() || value.current_math_step.length > 200))) {
      return { error: "The geometry scene reference is invalid." };
    }
    return { scene: value };
  } catch {
    return { error: "The geometry scene reference contains invalid JSON." };
  }
}

export function geometrySceneSource(node) {
  const code = node?.children?.find((child) => child.tagName === "code");
  const classes = code?.properties?.className || [];
  const languages = Array.isArray(classes) ? classes : [classes];
  if (!languages.some((name) => ["language-geometry-scene", "language-geometry-scene-pending"].includes(name))) return null;
  return parseGeometryScene((code.children || []).map((child) => child.value || "").join(""), {
    pending: languages.includes("language-geometry-scene-pending"),
  });
}

export function pinnedSceneVersions(body, pinned) {
  if (!Array.isArray(body?.frames)) throw new Error("Unexpected diagram frames.");
  return [...new Set([...body.frames.map((frame) => frame.version)
    .filter((version) => sceneVersion(version) && version <= pinned), pinned])].sort((a, b) => a - b);
}

export function sceneFrameCaption(body, sceneId, version) {
  if (body?.scene_id !== sceneId || body?.version !== version
    || typeof body?.visual_state?.caption !== "string" || body.visual_state.caption.length > 2000) {
    throw new Error("Unexpected diagram frame.");
  }
  return body.visual_state.caption;
}
