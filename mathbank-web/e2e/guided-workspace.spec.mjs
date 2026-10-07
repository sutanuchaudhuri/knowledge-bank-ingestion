import { expect, test } from "@playwright/test";
import { watchPageErrors } from "./helpers.mjs";
import { intent } from "../tests/fixtures/circumcenterIntent.mjs";

const Q31 = "PRASOLOV_PGV1_CH06_P031";
const AIME = "AIME_1985_Q01";
const Q31_STATEMENT = "Given a convex quadrilateral ABCD and the centers A1, B1, C1 and D1 of the circumscribed circles of triangles BCD, CDA, DAB and ABC, respectively. For quadrilat- eral A1B1C1D1 points A2, B2, C2 and D2 are similarly defined. Prove that quadrilaterals ABCD and A2B2C2D2 are similar and their similarity coeﬃcient is equal to 1\n4 |(cot A + cot C)(cot B + cot D)|.";
const journey = ["Understand", "Plan", "Work", "Check", "Reflect"].map((title) => ({
  id: title.toLowerCase(), title, icon: "search",
}));
const problem = (code) => ({
  canonical_code: code, competition: code === Q31 ? "Problems in Plane and Solid Geometry, v.1 Plane Geometry" : "AIME", year: 1985,
  statement_text: code === Q31 ? Q31_STATEMENT : String.raw`Let $x_1=97$, and for $n>1$, let $x_n=\frac{n}{x_{n-1}}$. Calculate the product $x_1x_2x_3x_4x_5x_6x_7x_8$.`,
  diagrams: [],
});
function session(index = 0) {
  const checks = [
    ["Which triangle defines the circumcenter $A_1$?", ["BCD", "CDA", "DAB", "ABC"]],
    ["Which side is shared?", ["CD", "DA", "BC", "AB"]],
    ["What distance relation follows from being a circumcenter?", ["Equal radii", "Perpendicular radii", "Center on CD"]],
  ];
  return {
    journey, provenance: "authored-statement-gated", completed_orientation: index,
    visual_intent: intent(["DEFINE_A1", "SHARED_CD", "EQUAL_RADII", "ITERATE_CIRCUMCENTERS"][index]),
    active_prompt: index < 3 ? { action: "ASK_MICRO_CHECK", index, prompt: checks[index][0], choices: checks[index][1] }
      : { action: "REQUEST_STUDENT_STEP", prompt: "Write one relation you can justify." },
  };
}
async function mock(page, fail = false) {
  const coachCalls = [], uploads = [];
  let failed = fail;
  await page.route("**/api/rest/learner/me", (route) => route.fulfill({ status: 401, json: {} }));
  await page.route("**/api/rest/solve/source/**", (route) => route.fulfill({ json: {
    kind: "identified", book_title: "Prasolov", chapter: 6, source_problem_id: "6.31", embed_url: null,
  } }));
  await page.route("**/api/rest/solve/diagrams/**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/rest/problems/*", (route) => route.fulfill({ json: problem(route.request().url().split("/").at(-1)) }));
  await page.route("**/api/tutor/workspace/*", (route) => {
    const code = route.request().url().split("/").at(-1);
    return route.fulfill({ json: { problem: problem(code), pedagogy_session: session() } });
  });
  await page.route("**/api/tutor/learning-context/*", (route) => {
    if (failed) return route.fulfill({ status: 503, json: { error: "Learning data is unavailable; check database connectivity." } });
    const code = route.request().url().split("/").at(-1);
    return route.fulfill({ json: {
      problem: problem(code), metadata_status: "automatic", skills: [{ name: "SECRET METADATA", source: "raw-model-source", confidence: .94 }],
      pedagogy_session: session(), warnings: [],
    } });
  });
  await page.route("**/api/tutor/micro-check", (route) => {
    const data = route.request().postDataJSON();
    if (data.response === "hint") return route.fulfill({ json: { hint: "Compare the defining triangles.", session: session(data.index) } });
    const correct = data.response === ["BCD", "CD", "Equal radii"][data.index];
    return route.fulfill({ json: {
      correct, explanation: correct ? "Correct: use the defining triangles." : "Try again.",
      session: session(correct ? data.index + 1 : data.index),
    } });
  });
  await page.route("**/api/tutor/coach", (route) => {
    coachCalls.push(route.request().postDataJSON());
    return route.fulfill({ json: { hint_level: coachCalls.at(-1).hint_level,
      micro_lesson: "A center has equal radii.", hint: "Compare the two distances.", return_prompt: "Write the equality.", warnings: [] } });
  });
  await page.route("**/api/tutor/practice/*?limit=5", (route) => route.fulfill({ json: { results: [], warnings: [] } }));
  await page.route("**/api/rest/attempt-media/submissions", (route) => {
    uploads.push(route.request().postDataJSON());
    return route.fulfill({ status: 401, json: { detail: "Sign in required" } });
  });
  return { coachCalls, uploads, recover: () => { failed = false; } };
}

for (const width of [1440, 390]) {
  test(`source math has genuinely smaller, lowered subscripts at ${width}px`, async ({ page }) => {
    const watch = watchPageErrors(page);
    await mock(page);
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`/learn?problem=${AIME}`);
    const current = page.getByRole("region", { name: "Current problem" });
    await expect(current.locator(".katex").first()).toBeVisible();
    await page.evaluate(() => document.fonts.ready.then(() => true));
    const sizes = await current.locator(".katex").first().evaluate((element) => {
      const base = element.querySelector(".mathnormal");
      const sub = element.querySelector(".sizing");
      return {
        base: parseFloat(getComputedStyle(base).fontSize), sub: parseFloat(getComputedStyle(sub).fontSize),
        baseY: base.getBoundingClientRect().top, subY: sub.getBoundingClientRect().top,
        mathmlClip: getComputedStyle(element.querySelector(".katex-mathml")).clipPath,
      };
    });
    expect(sizes.sub / sizes.base).toBeCloseTo(.7, 2);
    expect(sizes.subY - sizes.baseY).toBeGreaterThan(2);
    expect(sizes.mathmlClip).toBe("inset(50%)");
    await expect(current.locator(".katex-error")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.goto(`/learn?problem=${Q31}`);
    await expect(current).not.toContainText("quadrilat- eral");
    await expect(current).toContainText("coefficient");
    await expect(current.locator(".katex annotation").filter({ hasText: "\\frac{1}{4}" })).toHaveCount(1);
    await expect(current.locator(".katex-error")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    watch.assertClean();
  });

  test(`guided discovery, private work and safe construction at ${width}px`, async ({ page }) => {
    const watch = watchPageErrors(page);
    const calls = await mock(page);
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`/learn?problem=${Q31}`);
    await expect(page.getByRole("region", { name: "Your solving journey" })).toBeVisible();
    await expect(page.getByText("SECRET METADATA")).toHaveCount(0);
    await expect(page.getByText("Original page/location provenance incomplete", { exact: false })).toBeHidden();
    await expect(page.getByRole("button", { name: "Give me a small hint" })).toBeDisabled();
    await page.getByRole("radio", { name: "CDA", exact: true }).check();
    await page.getByRole("button", { name: "Check answer", exact: true }).click();
    await expect(page.getByText("Try again.", { exact: true })).toBeVisible();
    await expect(page.getByRole("radio", { name: "BCD", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Give me a tiny nudge" }).click();
    await expect(page.getByText("Compare the defining triangles.")).toBeVisible();
    await page.getByRole("radio", { name: "BCD", exact: true }).check();
    await page.getByRole("button", { name: "Check answer", exact: true }).click();
    await expect(page.getByRole("radio", { name: "CD", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Show the construction visually" }).click();
    await expect(page.getByRole("img", { name: "Progressive circumcenter construction" })).toBeVisible();
    await page.getByRole("button", { name: "Next construction frame" }).click();
    await expect(page.getByText("2/2 · The two centers belong to different circumcircles through C and D.")).toBeVisible();
    await expect(page.locator('svg [data-element-id="A1"]')).toBeVisible();
    await expect(page.locator('svg [data-element-id="B1"]')).toBeVisible();
    await expect(page.locator('svg [data-element-id="triangle_BCD"]')).toBeVisible();
    await expect(page.locator('svg [data-element-id="segment_CD"]')).toBeVisible();
    const work = page.getByRole("textbox", { name: "Your current attempt or sticking point" });
    await work.fill("Since A1 is a circumcenter, the two radii are equal.");
    await page.getByRole("button", { name: "Give me a small hint" }).click();
    await expect(page.getByRole("region", { name: "Tutor feedback for step 1" })).toBeVisible();
    await expect(page.getByText("Generated coaching · not verified correctness")).toBeVisible();
    await expect(page.getByRole("button", { name: "Give me a small hint" })).toBeDisabled();
    await page.getByRole("button", { name: "Add another step" }).click();
    await work.fill("My second observation.");
    await page.getByRole("button", { name: "Step 1", exact: false }).click();
    await expect(work).toHaveValue("Since A1 is a circumcenter, the two radii are equal.");
    await expect(page.getByRole("button", { name: "Give me a small hint" })).toBeDisabled();
    await work.fill("I changed my first observation.");
    await expect(page.getByText("This feedback applies to your earlier draft.", { exact: false })).toBeVisible();
    await page.getByRole("button", { name: "Give me a small hint" }).click();
    expect(calls.coachCalls.at(-1).hint_level).toBe(2);
    await page.getByLabel("Upload work for this problem").setInputFiles({ name: "work.png", mimeType: "image/png", buffer: Buffer.from("mock") });
    await expect(page.getByRole("alert").filter({ hasText: "Sign in required" })).toBeVisible();
    expect(calls.uploads).toEqual([{ problem_ref: Q31 }]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    watch.assertClean();
  });
}

test("routine diagnostics and recovered orientation failure do not distract from the problem widgets", async ({ page }) => {
  await mock(page);
  await page.route("**/api/tutor/workspace/*", (route) => route.fulfill({ status: 404, json: { error: "Not Found" } }));
  const warnings = ["Prerequisite traversal is limited to 4 levels.", "Automatically approved metadata needs review."];
  await page.route("**/api/tutor/learning-context/*", (route) => route.fulfill({
    json: { problem: problem(Q31), pedagogy_session: session(), warnings },
  }));
  await page.goto(`/learn?problem=${Q31}`);
  await expect(page.getByRole("region", { name: "Current problem" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Orientation checkpoint" })).toBeVisible();
  await expect(page.locator(".mb-learning-workspace").getByRole("alert")).toHaveCount(0);
  for (const warning of warnings) await expect(page.getByText(warning, { exact: true })).toBeHidden();
  await expect(page.getByLabel("Problem code", { exact: true })).toBeHidden();
  await page.getByText("Workspace details", { exact: true }).click();
  for (const warning of warnings) await expect(page.getByText(warning, { exact: true })).toBeVisible();
  await expect(page.getByText("Problem orientation could not be loaded: Not Found", { exact: true })).toBeVisible();
});

test("AIME data failure keeps the canonical question visible and offers recovery without fake hints", async ({ page }) => {
  const calls = await mock(page, true);
  await page.goto(`/learn?problem=${AIME}`);
  await expect(page.getByRole("region", { name: "Current problem" })).toContainText(AIME);
  await expect(page.getByRole("alert").filter({ hasText: "Teaching context could not be loaded" })).toBeVisible();
  await page.getByRole("textbox", { name: "Your current attempt or sticking point" }).fill("I tried the first two terms.");
  await expect(page.getByRole("button", { name: "Give me a small hint" })).toBeDisabled();
  expect(calls.coachCalls).toEqual([]);
  calls.recover();
  await page.getByRole("button", { name: "Retry learning data" }).click();
  await expect(page.getByRole("region", { name: "Orientation checkpoint" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Your current attempt or sticking point" })).toHaveValue("I tried the first two terms.");
  await expect(page.getByRole("alert").filter({ hasText: "Teaching context could not be loaded" })).toHaveCount(0);
});

test("completed orientation asks for student work, and easier practice remains opt-in", async ({ page }) => {
  await mock(page);
  await page.goto(`/learn?problem=${Q31}`);
  for (const answer of ["BCD", "CD", "Equal radii"]) {
    await page.getByRole("radio", { name: answer, exact: true }).check();
    await page.getByRole("button", { name: "Check answer", exact: true }).click();
  }
  await expect(page.getByText("Write one relation you can justify.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Orientation checkpoint" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Plan", exact: true })).toHaveAttribute("aria-current", "step");
  await page.getByRole("button", { name: "Show the construction visually" }).click();
  await expect(page.locator('svg [data-element-id="quadrilateral_A1B1C1D1"]')).toBeVisible();
  await page.getByRole("button", { name: "Next construction frame" }).click();
  await expect(page.locator('svg [data-element-id="triangle_B1C1D1"]')).toBeVisible();
  await expect(page.locator('svg [data-element-id="A2"]')).toBeVisible();
  await page.getByRole("button", { name: "Next construction frame" }).click();
  await expect(page.locator('svg [data-element-id="quadrilateral_A2B2C2D2"]')).toBeVisible();
  await page.getByText("Lower-level same-skill practice", { exact: true }).click();
  await expect(page.getByText("No reviewed lower-level same-skill practice is available.")).toBeVisible();
});

test("unknown question and failed canonical fallback remain explicit", async ({ page }) => {
  await mock(page);
  await page.route("**/api/tutor/learning-context/UNKNOWN", (route) => route.fulfill({ status: 404, json: { error: "Unknown problem code." } }));
  await page.route("**/api/tutor/workspace/UNKNOWN", (route) => route.fulfill({ status: 404, json: { error: "Unknown problem code." } }));
  await page.route("**/api/rest/problems/UNKNOWN", (route) => route.fulfill({ status: 404, json: { error: "Unknown problem code." } }));
  await page.goto("/learn?problem=UNKNOWN");
  await expect(page.getByRole("alert").filter({ hasText: "The canonical question could not be loaded either" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Current problem" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Retry learning data" })).toBeVisible();
});

test("pasted work uploads the original with a recoverable partial-submission error", async ({ page }) => {
  await mock(page);
  const submissions = [], assets = [];
  await page.route("**/api/rest/attempt-media/submissions", (route) => {
    submissions.push(route.request().postDataJSON());
    return route.fulfill({ status: 201, json: { submission_id: "fixture-private", transcription_version: 0 } });
  });

  await page.route("**/api/rest/attempt-media/submissions/fixture-private/assets?*", (route) => {
    assets.push({ url: route.request().url(), mime: route.request().headers()["content-type"], body: route.request().postDataBuffer().toString() });
    return route.fulfill({ status: 503, json: { detail: { code: "OBJECT_STORE_UNAVAILABLE" } } });
  });
  await page.goto(`/learn?problem=${Q31}`);
  await page.getByRole("textbox", { name: "Paste an image of your work" }).evaluate((element) => {
    const clipboardData = new DataTransfer();
    clipboardData.items.add(new File(["printed-work-original"], "pasted.png", { type: "image/png" }));
    element.dispatchEvent(new ClipboardEvent("paste", { clipboardData, bubbles: true, cancelable: true }));
  });
  await expect(page.getByRole("alert").filter({ hasText: "Private media storage is unavailable" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Resume this upload" })).toHaveAttribute("href", `/learn/attempt-media?problem_ref=${Q31}&submission_id=fixture-private`);
  expect(submissions).toEqual([{ problem_ref: Q31 }]);
  expect(assets).toHaveLength(1);
  expect(assets[0].mime).toBe("image/png");
  expect(assets[0].body).toBe("printed-work-original");
  expect(assets[0].url).toContain("expected_version=0");
});

test("slow graph context cannot block the question, work or current-object construction", async ({ page }) => {
  await mock(page);
  let finishContext;
  const pendingContext = new Promise((resolve) => { finishContext = resolve; });
  await page.route("**/api/tutor/learning-context/*", async (route) => {
    await pendingContext;
    await route.fulfill({ json: { problem: problem(Q31), pedagogy_session: session(), warnings: [] } });
  });
  await page.goto(`/learn?problem=${Q31}`);
  await expect(page.getByRole("region", { name: "Current problem" })).toBeVisible({ timeout: 3000 });
  await page.getByRole("textbox", { name: "Your current attempt or sticking point" }).fill("My draft while the graph is slow.");
  await page.getByRole("button", { name: "Show the construction visually" }).click();
  await expect(page.locator('svg [data-element-id="A1"]')).toBeVisible();
  await expect(page.locator('svg [data-element-id="triangle_BCD"]')).toBeVisible();
  await page.getByRole("radio", { name: "BCD", exact: true }).check();
  await page.getByRole("button", { name: "Check answer", exact: true }).click();
  await expect(page.locator('svg [data-element-id="B1"]')).toBeVisible();
  finishContext();
  await expect(page.getByText("Hints loading…", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "CD", exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Your current attempt or sticking point" })).toHaveValue("My draft while the graph is slow.");
});

test("a malformed visual intent is suppressed rather than replaced with a quadrilateral", async ({ page }) => {
  await mock(page);
  const malformed = { ...session(), visual_intent: { ...intent(), problem_code: "WRONG" } };
  for (const name of ["workspace", "learning-context"]) {
    await page.route(`**/api/tutor/${name}/*`, (route) => route.fulfill({ json: { problem: problem(Q31), pedagogy_session: malformed, warnings: [] } }));
  }
  await page.goto(`/learn?problem=${Q31}`);
  await page.getByRole("button", { name: "Show the construction visually" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "No step-aligned construction yet" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Progressive circumcenter construction" })).toHaveCount(0);
});

test("teaching-context deadline reports a timeout while preserving the canonical workspace", async ({ page }) => {
  await mock(page);
  await page.route("**/api/tutor/learning-context/*", (route) => new Promise(() => {}));
  await page.goto(`/learn?problem=${Q31}`);
  await expect(page.getByRole("region", { name: "Current problem" })).toBeVisible();
  await page.getByRole("textbox", { name: "Your current attempt or sticking point" }).fill("My preserved draft.");
  await expect(page.getByRole("alert").filter({ hasText: "Teaching context could not be loaded" })).toBeVisible({ timeout: 18000 });
  await page.getByText("Workspace details", { exact: true }).click();
  await expect(page.getByText("Teaching data timed out.", { exact: false })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Your current attempt or sticking point" })).toHaveValue("My preserved draft.");
  await expect(page.getByRole("region", { name: "Orientation checkpoint" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Give me a small hint" })).toBeDisabled();
});
