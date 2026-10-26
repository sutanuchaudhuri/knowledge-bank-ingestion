import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import type { Preview, Program } from "../src/contracts";
import { assessmentPreview } from "../tests/fixtures";
import { prototypeWorkflow } from "../tests/prototype";

const narrow = (page: Page) => page.viewportSize()!.width < 760;
async function navigate(page: Page, label: string) {
  await page.getByRole("link", { name: label, exact: true }).click();
}
async function sidebar(page: Page) {
  if (narrow(page) && !await page.getByRole("searchbox", { name: "Search workspace" }).isVisible()) {
    await page.getByRole("button", { name: "Toggle workspace search" }).click();
  }
  return page.getByRole("complementary", { name: "Workspace search" });
}
const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);

test.beforeEach(async ({ page }) => {
  let detail = structuredClone(prototypeWorkflow);
  let preview: Preview = {
    ...structuredClone(assessmentPreview), workflow_id: detail.workflow_id, state_version: 1,
    current_node: detail.program.nodes.find(node => node.key === "quiz")!,
  };
  await page.route("**/v1/admin/socratic/**", async route => {
    const path = new URL(route.request().url()).pathname.split("/socratic")[1];
    const method = route.request().method();
    const body = method === "POST" || method === "PUT" ? route.request().postDataJSON() : null;
    let result: unknown;
    if (path === "/session") result = { actor: "TEST FIXTURE · not a live login", csrf_token: "test-only" };
    else if (path === "/strategies") result = { strategies: [{ code: detail.program.strategy_code, domain: detail.domain, label: "Stars and Bars", status: "DRAFT", phases: ["Represent", "Justify", "Generalize"] }] };
    else if (path === "/workflows") result = { workflows: [detail], has_more: false };
    else if (path === `/workflows/${detail.workflow_id}`) {
      if (method === "PUT") detail = { ...detail, program: body.program as Program, revision: detail.revision + 1, content_hash: `test-hash-${detail.revision + 1}` };
      result = detail;
    } else if (path.endsWith("/simulate")) {
      const node = detail.program.nodes.find(node => node.key === (body.start_node_key || "quiz"))!;
      preview = { ...preview, current_node: node, activity: node.key === "quiz" ? assessmentPreview.activity : undefined, history: [] };
      result = preview;
    } else if (path.endsWith("/respond")) {
      preview = { ...preview, state_version: preview.state_version + 1, current_node: detail.program.nodes.find(node => node.key === "lesson")!,
        activity: undefined, feedback: "Test verdict: review the correspondence.",
        history: [{ node_key: "lesson", from_key: "quiz", to_key: "lesson", outcome: "RETRY", decision_source: "DETERMINISTIC", reason: "Canned test response, not a mathematical evaluation" }] };
      result = preview;
    } else if (path.endsWith("/assist")) {
      preview = { ...preview, state_version: preview.state_version + 1, help: { level: 1, text: "Test hint: check the bijection.", assisted: true } };
      result = preview;
    } else if (path.endsWith("/proposals")) result = { job_id: "job-test", status: "SUCCEEDED", execution_arn: "test-only" };
    else if (path === "/jobs/job-test") result = { job_id: "job-test", status: "SUCCEEDED", error: null,
      result: { from_key: "quiz", to_key: "lesson", outcome: "RETRY", priority: 10, explanation: "Test proposal for explicit review.", model_id: "no-model-invoked" } };
    else if (path === "/resources") result = { resources: [], has_more: false };
    else {
      await route.fulfill({ status: 503, json: { message: "This test fixture does not implement the operation." } });
      return;
    }
    await route.fulfill({ json: result });
  });
  await page.goto("/");
  await (await sidebar(page)).getByRole("button", { name: /Stars and Bars · Discovery journey/ }).click();
  await expect(page.getByRole("group", { name: "Workflow steps" })).toBeVisible();
});

test("flow, plain-language and JSON views with a detail drawer for editing", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const steps = page.getByRole("group", { name: "Workflow steps" });
  await expect(steps.locator(".sc-node")).toHaveCount(10);
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await steps.locator(".sc-node").first().focus();
  await page.keyboard.press("ArrowDown");
  const drawer = page.getByRole("complementary", { name: "Edit step" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByLabel("Step title")).toHaveValue("Discover the representation");
  await expect(steps.locator(".sc-node").nth(1)).toBeFocused();
  const viewport = page.viewportSize()!;
  const canvas = await page.locator(".sc-canvas").boundingBox();
  const panel = await drawer.boundingBox();
  if (viewport.width >= 1100) expect(panel!.x).toBeGreaterThanOrEqual(canvas!.x + canvas!.width - 1);
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("designer.png"), fullPage: true });
  await drawer.getByRole("button", { name: "Close pane" }).click();
  await page.getByRole("button", { name: "Natural language" }).click();
  await expect(page.getByRole("article", { name: "Natural-language flow" })).toContainText("The journey starts at Begin discovery");
  await expect(page.locator(".sc-narrative .katex").first()).toBeVisible();
  await page.getByRole("button", { name: "JSON", exact: true }).click();
  await expect(page.getByRole("region", { name: "JSON flow" })).toContainText('"strategy_code": "COMB_STARS_BARS_BASIC"');
  expect(await noOverflow(page)).toBe(true);
  expect(errors).toEqual([]);
});

test("student choices, hints, history and selected branch use server test responses", async ({ page }) => {
  await navigate(page, "Student simulator");
  await page.getByRole("button", { name: /Save & start preview/ }).click();
  await page.getByRole("button", { name: "Hint", exact: true }).click();
  await expect(page.getByLabel("Current hint")).toContainText("Hint 1");
  await page.getByRole("button", { name: "Hide hint" }).click();
  await expect(page.getByLabel("Current hint")).toHaveCount(0);
  await page.getByRole("radio", { name: /Both false/ }).check();
  const response = page.waitForRequest(request => request.url().endsWith("/respond"));
  await page.getByRole("button", { name: "Submit answer" }).click();
  expect((await response).postDataJSON()).toMatchObject({ response: { selected_keys: ["AR5"] }, expected_version: 2 });
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Bijections mini-lesson");
  await expect(page.getByRole("region", { name: "Latest routing decision" })).toContainText("DETERMINISTIC");
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("student.png"), fullPage: true });
  await navigate(page, "Workflow designer");
  await expect(page.locator(".sc-branch .sc-live")).toContainText("bijection lesson");
});

test("rules by topic keep annotations and AI proposals stay editable until accepted", async ({ page }) => {
  await navigate(page, "Rules by topic");
  await page.getByRole("button", { name: "Bijections", exact: true }).click();
  await page.getByRole("button", { name: /Check the explanation with a simpler counting question/ }).click();
  const rule = page.getByRole("complementary", { name: "Edit rule" });
  await expect(rule.getByLabel("Describe what should happen")).toHaveValue("Check the explanation with a simpler counting question.");
  await rule.getByLabel("Describe what should happen").fill("Reviewed explanation for a smaller example.");
  await rule.getByRole("button", { name: "Close pane" }).click();
  await page.getByRole("button", { name: /Describe a new rule in English/ }).click();
  const ai = page.getByRole("complementary", { name: "Ask AI" });
  await ai.getByRole("button", { name: "Example", exact: true }).click();
  await ai.getByRole("button", { name: /Propose rule/ }).click();
  await ai.getByText("Compare and adjust").click();
  await ai.getByLabel("Proposed destination").selectOption("topic");
  await expect(ai.getByLabel("Proposed edge comparison")).toContainText("quiz — RETRY → topic");
  await expect(ai.getByRole("button", { name: "Accept into draft" })).toBeEnabled();
  expect(await noOverflow(page)).toBe(true);
});

test("library keeps every step previewable and the sidebar search finds steps", async ({ page }) => {
  await navigate(page, "Templates & sources");
  await page.getByRole("button", { name: /Steps/ }).click();
  await expect(page.getByRole("button", { name: /View in simulator/ })).toHaveCount(10);
  const search = await sidebar(page);
  await search.getByRole("searchbox", { name: "Search workspace" }).fill("loci");
  await expect(search.getByText("Steps in this workflow")).toBeVisible();
  if (narrow(page)) await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "View in simulator · Loci and geometric constraints" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Loci and geometric constraints");
  expect(await noOverflow(page)).toBe(true);
});
