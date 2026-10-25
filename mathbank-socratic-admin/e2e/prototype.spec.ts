import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import type { Preview, Program } from "../src/contracts";
import { assessmentPreview } from "../tests/fixtures";
import { prototypeWorkflow } from "../tests/prototype";

async function navigate(page: Page, label: string) {
  if (!await page.getByRole("link", { name: label, exact: true }).isVisible()) {
    await page.getByRole("button", { name: "Toggle navigation" }).click();
  }
  await page.getByRole("link", { name: label, exact: true }).click();
}

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
  await page.getByRole("button", { name: /Stars and Bars · Discovery journey/ }).click();
});

test("reference map, inspector and simulator preserve the two-column desktop hierarchy", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.getByRole("button", { name: "Save draft & start preview" }).click();
  await expect(page.getByRole("radio")).toHaveCount(5);
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  const viewport = page.viewportSize()!;
  const map = await page.getByRole("region", { name: "Workflow map" }).boundingBox();
  const simulator = await page.getByRole("region", { name: "Synthetic simulator" }).boundingBox();
  expect(map).not.toBeNull(); expect(simulator).not.toBeNull();
  if (viewport.width >= 1120) expect(simulator!.x).toBeGreaterThan(map!.x + map!.width);
  else expect(simulator!.y).toBeGreaterThan(map!.y);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator(".katex").first()).toBeVisible();
  const nodes = page.getByRole("group", { name: "Keyboard workflow nodes" }).getByRole("button");
  await nodes.first().focus();
  await page.keyboard.press("ArrowDown");
  await expect(nodes.nth(1)).toBeFocused();
  await expect(page.getByText("Current node: quiz", { exact: false })).toBeVisible();
  expect(errors).toEqual([]);
  await page.screenshot({ path: test.info().outputPath("designer.png"), fullPage: true });
});

test("student choices, hints, history and selected branch use server test responses", async ({ page }) => {
  await page.getByRole("button", { name: "Save draft & start preview" }).click();
  await page.getByRole("button", { name: "Request hint" }).click();
  await expect(page.getByLabel("Current hint")).toContainText("H1");
  await page.getByRole("button", { name: "Hide hint" }).click();
  await expect(page.getByLabel("Current hint")).toHaveCount(0);
  await page.getByRole("radio", { name: /Both false/ }).check();
  const response = page.waitForRequest(request => request.url().endsWith("/respond"));
  await page.getByRole("button", { name: "Submit answer" }).click();
  expect((await response).postDataJSON()).toMatchObject({ response: { selected_keys: ["AR5"] }, expected_version: 2 });
  await expect(page.getByText("Current node: lesson", { exact: false })).toBeVisible();
  await expect(page.locator(".sc-branch-hit")).toContainText("Bijections mini-lesson");
  await expect(page.getByRole("region", { name: "Latest routing decision" })).toContainText("DETERMINISTIC");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("topic rule cards retain annotations and editable proposal source/outcome/destination", async ({ page }) => {
  await navigate(page, "Rules by topic");
  await page.getByLabel("Filter rules by topic").selectOption("Bijections");
  await expect(page.getByLabel("Plain-language explanation (editable)")).toHaveValue("Check the explanation with a simpler counting question.");
  await page.getByLabel("Plain-language explanation (editable)").fill("Reviewed explanation for a smaller example.");
  await page.getByRole("button", { name: "Example", exact: true }).click();
  await page.getByRole("button", { name: "Save draft & request proposal" }).click();
  await expect(page.getByLabel("Proposed edge comparison")).toBeVisible();
  await page.getByLabel("Proposed destination").selectOption("topic");
  await expect(page.getByLabel("Proposed edge comparison")).toContainText("quiz — RETRY → topic");
  await expect(page.getByRole("button", { name: "Accept proposed edge into draft" })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("resource library keeps all reference quizzes, lessons and topics", async ({ page }) => {
  await navigate(page, "Resource Library");
  const library = page.getByRole("region", { name: "Workflow resource library" });
  await expect(library.getByRole("button", { name: /View in simulator/ })).toHaveCount(10);
  await library.getByLabel(/Resource topic/).selectOption("Geometry / Loci");
  await expect(library.getByRole("button", { name: /View in simulator/ })).toHaveCount(1);
  await library.getByRole("button", { name: /View in simulator/ }).click();
  await expect(page.getByText("Current node: geometry", { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
