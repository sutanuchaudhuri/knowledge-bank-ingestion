import { test, expect } from "@playwright/test";
import { watchPageErrors } from "./helpers.mjs";
import { mockAdminSession } from "./mock-auth.mjs";

const id = "11111111-1111-4111-8111-111111111111";
const image = "22222222-2222-4222-8222-222222222222";
const r1 = "33333333-3333-4333-8333-333333333333";
const r2 = "44444444-4444-4444-8444-444444444444";
const s1 = "55555555-5555-4555-8555-555555555555";
const s2 = "66666666-6666-4666-8666-666666666666";
const pixel = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=", "base64");
function snapshot() {
  return {
    submission_id: id, problem_id: "DEMO", status: "CANDIDATE", transcription_version: 1, approved_version: null,
    assets: [{ media_asset_id: image, content_type: "image/png", filename: "work.png" }],
    regions: [
      { region_id: r1, media_asset_id: image, page_number: 1, x_norm: .05, y_norm: .1, width_norm: .3, height_norm: .2, region_type: "MATH_LINE", reading_order: 1, confidence: .6 },
      { region_id: r2, media_asset_id: image, page_number: 1, x_norm: .55, y_norm: .5, width_norm: .3, height_norm: .2, region_type: "MATH_LINE", reading_order: 2, confidence: .95 },
    ],
    steps: [
      { step_id: s1, ordinal: 1, plain_text: "AB / AE = AC / AD", latex_text: "AB/AE=AC/AD", step_type: "RATIO", confidence: .6, evidence_ids: [r1] },
      { step_id: s2, ordinal: 2, plain_text: "My conclusion", latex_text: "", step_type: "CONCLUSION", confidence: .95, evidence_ids: [r2] },
    ],
    assessments: [], approvals: [], events: [],
  };
}
async function mock(page, state, content = pixel) {
  const calls = [];
  await page.context().addCookies([{ name: "mb_student_token", value: "mock-student-token", url: "http://localhost:5173" }]);
  await page.route("**/api/rest/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.endsWith("/learner/me")) return route.fulfill({ json: { student_id: id, first_name: "Test", email: "mock@example.test" } });
    if (!url.pathname.includes("/attempt-media/")) return route.fulfill({ json: {} });
    calls.push({ path: url.pathname, method: request.method(), data: request.headers()["content-type"]?.includes("application/json") ? request.postDataJSON() : null });
    if (/\/pages\/\d+$/.test(url.pathname)) return route.fulfill({ contentType: "image/png", body: pixel });
    if (url.pathname.endsWith("/content")) {
      const asset = state.assets.find((a) => a.media_asset_id === url.pathname.split("/").at(-2)) || state.assets[0];
      return route.fulfill({ contentType: asset.content_type || asset.mime_type, body: content });
    }
    if (url.pathname.endsWith("/submissions")) return route.fulfill({ json: request.method() === "POST" ? state : { items: [state], has_more: false } });
    if (url.pathname.endsWith("/transcription")) {
      const data = request.postDataJSON();
      expect(data.expected_version).toBe(state.transcription_version);
      state.steps = data.steps.map((s, index) => ({ ...s, step_id: s.step_id || `77777777-7777-4777-8777-${String(index).padStart(12, "0")}` }));
      state.regions = data.regions; state.transcription_version++; state.approved_version = null;
      return route.fulfill({ json: state });
    }
    if (url.pathname.endsWith("/approve")) {
      expect(request.postDataJSON().expected_version).toBe(state.transcription_version);
      state.approved_version = (state.approved_version || 0) + 1;
      state.approvals.push({ approved_version: state.approved_version, transcription_version: state.transcription_version });
      return route.fulfill({ json: { approved_version: state.approved_version, learner_attempt_id: id } });
    }
    if (url.pathname.endsWith("/override")) {
      const data = request.postDataJSON();
      state.assessments.push({ ...data, transcription_version: state.transcription_version, approved_version: state.approved_version, source: "INSTRUCTOR" });
      state.events.push({ sequence: state.events.length + 1, event_type: "INSTRUCTOR_OVERRIDE" });
      return route.fulfill({ json: state });
    }
    return route.fulfill({ json: state });
  });
  return calls;
}
  function twoPagePdf() {
    const objects = [
      "<< /Type /Catalog /Pages 2 0 R >>",
      "<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 600] /Resources << >> /Contents 5 0 R >>",
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 600] /Resources << >> /Contents 5 0 R >>",
      "<< /Length 0 >>\nstream\n\nendstream",
    ];
    let text = "%PDF-1.4\n", offsets = [0];
    objects.forEach((object, index) => { offsets.push(Buffer.byteLength(text)); text += `${index + 1} 0 obj\n${object}\nendobj\n`; });
    const xref = Buffer.byteLength(text);
    text += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
    text += offsets.slice(1).map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
    text += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
    return Buffer.from(text);
  }
  test("PDF rows preserve pages and normalized rectangles on rendered originals", async ({ page }) => {
    const state = snapshot(), errors = watchPageErrors(page);
    state.assets[0].content_type = "application/pdf";
    state.assets[0].page_count = 2;
    state.regions[1].page_number = 2;
    await mock(page, state, twoPagePdf());
    await page.goto(`/learn/attempt-media?submission_id=${id}`);
    await expect(page.getByRole("img", { name: "Original PDF page 1", exact: true })).toBeVisible();
    await expect(page.getByLabel("PDF page", { exact: true })).toHaveValue("1");
    await page.getByRole("button", { name: "Select step 2", exact: true }).click();
    await expect(page.getByLabel("PDF page", { exact: true })).toHaveValue("2");
    await expect(page.getByRole("button", { name: "Select evidence region 2", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Select evidence region 1", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Previous PDF page", exact: true }).click();
    await expect(page.getByLabel("PDF page", { exact: true })).toHaveValue("1");
    errors.assertClean();
  });
  test("instructor overrides preserve AI decisions and append audited history", async ({ page, baseURL }) => {
    const state = snapshot(); state.approved_version = 1; state.approvals = [{ approved_version: 1, transcription_version: 1 }];
    state.assessments = [{ step_id: s1, transcription_version: 1, approved_version: 1, correctness: "INCORRECT", why: "Prior AI reasoning", next_action: "Check correspondence", source: "AI" }];
    await mock(page, state);
    await mockAdminSession(page, baseURL);
    await page.goto(`/admin/attempt-media?submission_id=${id}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Attempt media review");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByLabel("Correctness", { exact: true }).selectOption("CORRECT");
    await page.getByLabel("Why", { exact: true }).fill("Valid alternate argument");
    await page.getByLabel("Next useful action", { exact: true }).fill("Continue your approach");
    await page.getByRole("button", { name: "Record audited override", exact: true }).click();
    expect(state.assessments).toHaveLength(2);
    expect(state.assessments[0].why).toBe("Prior AI reasoning");
    await page.getByText("Approval and review history", { exact: true }).click();
    await expect(page.getByText("INSTRUCTOR_OVERRIDE", { exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
test("candidate review is bidirectional, editable, versioned and explicitly approved", async ({ page }) => {
  const state = snapshot(), errors = watchPageErrors(page), calls = await mock(page, state);
  await page.goto(`/learn/attempt-media?submission_id=${id}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("My submitted work");
  await expect(page.getByText("Candidate · not submitted")).toBeVisible();
  expect(calls.some((c) => /approve|process|analyse/.test(c.path))).toBe(false);
  await page.getByRole("button", { name: "Select evidence region 2", exact: true }).click();
  await expect(page.getByRole("button", { name: "Select step 2", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "Select step 1", exact: true }).click();
  await expect(page.getByRole("button", { name: "Select evidence region 1", exact: true })).toHaveClass(/selected/);
  await page.getByLabel("Step text", { exact: true }).fill("My corrected reading");
  await expect(page.getByText("Unsaved edits", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save transcription edits" }).click();
  expect(calls.find((c) => c.method === "PUT").data.steps[0].plain_text).toBe("My corrected reading");
  await page.getByRole("button", { name: "Approve transcription as my submitted attempt", exact: true }).click();
  await expect(page.getByText("Approved attempt", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Approved attempt", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Step text", { exact: true })).toHaveValue("My corrected reading");
  await page.getByLabel("Step text", { exact: true }).fill("New correction");
  await expect(page.getByRole("button", { name: "Analyse approved attempt · uses AI" })).toHaveCount(0);
  errors.assertClean();
});
test("merge, split, reorder, add and delete maintain editable one-based rows", async ({ page }) => {
  const state = snapshot(); await mock(page, state);
  await page.goto(`/learn/attempt-media?submission_id=${id}`);
  await page.getByRole("button", { name: "Merge with next", exact: true }).click();
  await expect(page.getByRole("button", { name: "Select step 2", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Split step", exact: true }).click();
  await expect(page.getByRole("button", { name: "Select step 2", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Move step down", exact: true }).click();
  await expect(page.getByRole("button", { name: "Select step 2", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Add missing step", exact: true }).click();
  await page.getByRole("button", { name: "Delete step", exact: true }).click();
  await page.getByRole("button", { name: "Save transcription edits" }).click();
  expect(state.steps.map((s) => s.ordinal)).toEqual([1, 2]);
});
test("temporal rows seek the exact original interval and mobile layout remains bounded", async ({ page }) => {
  const state = snapshot(); state.assets[0].content_type = "audio/mpeg";
  state.regions = [{ region_id: r1, media_asset_id: image, start_ms: 7400, end_ms: 12900, region_type: "SPEECH", reading_order: 1 }];
  state.steps = [state.steps[0]];
  await mock(page, state); await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/learn/attempt-media?submission_id=${id}`);
  await expect(page.getByText("00:07.4–00:12.9", { exact: true })).toBeVisible();
  await page.locator("audio").evaluate((media) => {
    let time = 0;
    Object.defineProperty(media, "currentTime", { get: () => time, set: (value) => { time = value; } });
    media.play = () => Promise.resolve();
  });
  await page.getByRole("button", { name: "Select step 1", exact: true }).click();
  await expect.poll(() => page.locator("audio").evaluate((media) => media.currentTime)).toBe(7.4);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
test("video speech and its accompanying keyframe remain jointly grounded", async ({ page }) => {
    const state = snapshot();
    const keyframe = "77777777-7777-4777-8777-777777777777";
    state.assets = [{ ...state.assets[0], content_type: "video/mp4" }, { media_asset_id: keyframe, mime_type: "image/png", timestamp_ms: 7400 }];
    state.regions = [
      { region_id: r1, media_asset_id: image, start_ms: 7400, end_ms: 12900, region_type: "SPEECH", reading_order: 1 },
      { ...state.regions[1], media_asset_id: keyframe, region_type: "KEYFRAME" },
    ];
    state.steps = [{ ...state.steps[0], evidence_ids: [r1, r2] }];
    await mock(page, state);
    await page.goto(`/learn/attempt-media?submission_id=${id}`);
    await expect(page.locator("video")).toBeVisible();
    await expect(page.getByRole("img", { name: "Accompanying original evidence", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Select accompanying evidence region 2", exact: true })).toHaveClass(/selected/);
    await page.locator("video").evaluate((media) => {
      let time = 0;
      Object.defineProperty(media, "currentTime", { get: () => time, set: (value) => { time = value; } });
      media.play = () => Promise.resolve();
    });
    await page.getByRole("button", { name: "Select step 1", exact: true }).click();
    await expect.poll(() => page.locator("video").evaluate((media) => media.currentTime)).toBe(7.4);
});
test("new upload previews immediately and processing remains an explicit stage", async ({ page }) => {
  const candidate = snapshot();
  const state = { ...snapshot(), assets: [], regions: [], steps: [] };
  const calls = await mock(page, state);
  await page.route("**/api/rest/attempt-media/submissions/*/assets?*", async (route) => {
    expect(route.request().headers()["content-type"]).toBe("image/png");
    expect(new URL(route.request().url()).searchParams.get("expected_version")).toBe("1");
    state.assets = candidate.assets; state.transcription_version = 2;
    calls.push({ path: "upload", method: "POST" });
    return route.fulfill({ json: { media_asset_id: image, transcription_version: 2 } });
  });
  await page.route("**/api/rest/attempt-media/submissions/*/process", async (route) => {
    expect(route.request().postDataJSON().expected_version).toBe(2);
    state.steps = candidate.steps; state.regions = candidate.regions; state.transcription_version = 3;
    calls.push({ path: "process", method: "POST" });
    return route.fulfill({ json: state });
  });
  await page.goto("/learn/attempt-media?problem_ref=DEMO");
  await expect(page.getByLabel("Problem reference", { exact: true })).toHaveValue("DEMO");
  await page.getByRole("button", { name: "Start media submission", exact: true }).click();
  await page.getByLabel("Upload original media", { exact: true }).setInputFiles({ name: "work.png", mimeType: "image/png", buffer: pixel });
  await expect(page.getByRole("img", { name: "Original submitted work", exact: true })).toBeVisible();
  expect(calls.some((c) => /process|approve|analyse/.test(c.path))).toBe(false);
  await page.getByRole("button", { name: "Transcribe media · uses AI", exact: true }).click();
  await expect(page.getByRole("button", { name: "Select step 1", exact: true })).toBeVisible();
  await expect(page.getByText("Candidate · not submitted", { exact: true })).toBeVisible();
  expect(calls.filter((c) => c.path === "process")).toHaveLength(1);
  expect(calls.some((c) => /approve|analyse/.test(c.path))).toBe(false);
});
test("edits hide current assessments and version conflicts preserve unsaved corrections", async ({ page }) => {
  const state = snapshot(); state.transcription_version = 4; state.approved_version = 1;
  state.approvals = [{ approved_version: 1, transcription_version: 4 }];
  state.assessments = [{ step_id: s1, transcription_version: 4, approved_version: 1, correctness: "CORRECT", why: "Current reviewed reasoning", next_action: "Continue", evidence_ids: [r1] }];
  await mock(page, state);
  await page.route("**/api/rest/attempt-media/submissions/*/transcription", (route) => route.fulfill({ status: 409, json: { detail: { code: "STALE_VERSION" } } }));
  await page.goto(`/learn/attempt-media?submission_id=${id}`);
  const transcript = page.getByRole("region", { name: "Editable transcription", exact: true });
  await expect(transcript.getByText("CORRECT", { exact: true }).first()).toBeVisible();
  await page.getByLabel("Step text", { exact: true }).fill("My unsaved correction");
  await expect(transcript.getByText("CORRECT", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Save transcription edits", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "This submission changed" })).toBeVisible();
  await expect(page.getByLabel("Step text", { exact: true })).toHaveValue("My unsaved correction");
  expect(state.transcription_version).toBe(4);
});
test("provider failures retain manual transcription and approved attempts", async ({ page }) => {
  const state = snapshot();
  await mock(page, state);
  await page.route("**/api/rest/attempt-media/submissions/*/process", (route) => route.fulfill({ status: 503, json: { detail: { code: "TRANSCRIPTION_UNAVAILABLE" } } }));
  await page.route("**/api/rest/attempt-media/submissions/*/analyse", (route) => route.fulfill({ status: 503, json: { detail: { code: "ANALYSIS_UNAVAILABLE" } } }));
  await page.goto(`/learn/attempt-media?submission_id=${id}`);
  await page.getByRole("button", { name: "Transcribe media · uses AI", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Transcription is unavailable" })).toContainText("enter the transcription manually");
  await expect(page.getByLabel("Step text", { exact: true })).toBeEditable();
  await page.getByRole("button", { name: "Approve transcription as my submitted attempt", exact: true }).click();
  await page.getByRole("button", { name: "Analyse approved attempt · uses AI", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Analysis is unavailable" })).toContainText("approved attempt is still saved");
  await expect(page.getByText("Approved attempt", { exact: true })).toBeVisible();
});
test("expired student sessions show sign-in required, never a successful empty workspace", async ({ page, baseURL }) => {
  await page.context().addCookies([{ name: "mb_student_token", value: "expired-mock-token", url: baseURL }]);
  await page.route("**/api/rest/**", (route) => route.fulfill({ status: 401, json: { detail: "Sign in required" } }));
  await page.goto("/learn/attempt-media");
  await expect(page.getByText("Sign in required", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start media submission", exact: true })).toBeDisabled();
  await expect(page.getByText("There are no saved submissions to review.", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Student login", exact: true }).last()).toHaveAttribute("href", /\/login/);
});
test("submission-list service errors disable creation and expose an explicit retry", async ({ page, baseURL }) => {
  await page.context().addCookies([{ name: "mb_student_token", value: "mock-token", url: baseURL }]);
  let failed = true;
  await page.route("**/api/rest/**", (route) => {
    if (route.request().url().includes("/learner/me")) return route.fulfill({ json: { student_id: id, email: "mock@example.test" } });
    return failed ? route.fulfill({ status: 503, json: { detail: "Service temporarily unavailable" } }) : route.fulfill({ json: { items: [], has_more: false } });
  });
  await page.goto("/learn/attempt-media");
  await expect(page.getByRole("alert").filter({ hasText: "Saved submissions are unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start media submission", exact: true })).toBeDisabled();
  await expect(page.getByText("There are no saved submissions to review.", { exact: true })).toHaveCount(0);
  failed = false;
  await page.getByRole("button", { name: "Retry workspace connection", exact: true }).click();
  await expect(page.getByRole("button", { name: "Start media submission", exact: true })).toBeEnabled();
  await expect(page.getByText("There are no saved submissions to review.", { exact: true })).toBeVisible();
});
