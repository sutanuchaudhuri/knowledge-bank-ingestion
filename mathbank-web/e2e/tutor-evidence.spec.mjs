import { expect, test } from "@playwright/test";
import { createAgentEventMapper } from "../lib/agentStream.mjs";

for (const width of [1440, 390]) {
  test(`coaching evidence is visible without private payloads at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
    const map = createAgentEventMapper();
    const events = [
      { content: { parts: [{ functionCall: { name: "get_problem_learning_context", args: { problem_code: "AIME_2002_I_Q15" } } }] } },
      { content: { parts: [{ functionResponse: { name: "get_problem_learning_context", response: {
        problem: { statement: "PRIVATE_RAW_CONTEXT" }, metadata_status: "automatic",
        skills: [{}, {}], prerequisites: [], concepts: [{}], techniques: [],
        warnings: ["PRIVATE_RAW_WARNING"],
      } } }] } },
      { content: { parts: [{ functionCall: { name: "prepare_problem_guidance", args: { problem_code: "AIME_1985_Q01" } } }] } },
      { content: { parts: [{ functionResponse: { name: "prepare_problem_guidance", response: {
        status: "ready", stages: ["Read", "Explore", "Group", "Check"], diagram_count: 0,
        solution_evidence: { status: "available", references_considered: 2, sources: [
          { verification_status: "UNVERIFIED", body_markdown: "PRIVATE_SOLUTION", official_answer: "PRIVATE_ANSWER" },
        ] },
      } } }] } },
      { content: { parts: [{ thought: true, text: "PRIVATE_THOUGHT" }, { text:
        "### Provisional approach\n1. Represent the square in coordinates.\n2. Translate the parallelism and lengths into constraints.\n3. Check consistency before finding the target distance.\n\nFirst checkpoint: which constraints must the trapezoid satisfy?" }] } },
    ];
    const updates = [...events.flatMap(map), { type: "done" }];
    await page.route("**/api/agent/run", (route) => route.fulfill({
      contentType: "text/event-stream",
      body: updates.map((update) => `data: ${JSON.stringify(update)}\n\n`).join(""),
    }));
    await page.goto("/");
    await page.getByRole("textbox", { name: "Your question" }).fill("problem 1 help me think");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const activity = page.getByRole("region", { name: "Agent activity" });
    await expect(activity).toContainText("Canonical problem loaded · answer-free");
    await expect(activity).toContainText("2 graph-linked skills · machine-approved, not human verified");
    await expect(activity).toContainText("1 evidence limitations reported");
    await expect(activity).toContainText("2 stored solution records consulted for guidance");
    await expect(activity).toContainText("Solution references include unverified records");
    await expect(activity).toContainText("not private reasoning");
    await expect(page.getByRole("heading", { name: "Provisional approach" })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("PRIVATE_");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}
