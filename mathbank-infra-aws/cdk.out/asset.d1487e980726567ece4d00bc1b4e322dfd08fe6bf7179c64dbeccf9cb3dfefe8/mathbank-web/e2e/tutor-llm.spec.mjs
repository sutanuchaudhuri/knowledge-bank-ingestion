import { expect, test } from "@playwright/test";
import { POWER_POINT_PROBLEM, loginStudent } from "./helpers.mjs";

// @llm specs call the tutor agent / step grader (small paid OpenAI requests). Run with E2E_LLM=1.
test.describe("@llm tutor walkthrough", () => {
  test.setTimeout(180_000);

  test.beforeEach(async ({ page }) => {
    await loginStudent(page);
  });

  test("@llm home tutor answers a power-of-a-point question with hybrid retrieval", async ({ page }) => {
    await page.goto("/");
    const prompt = `E2E ${Date.now()}: show me a Prasolov radical axis / power of a point problem.`;
    await page.getByLabel("Your question").fill(prompt);
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.getByText("Response complete")).toBeVisible({ timeout: 150_000 });
    await expect(page.getByText(/Calling search_problems/)).toBeVisible();
    await expect(page.getByRole("region", { name: "Tutor conversation" })).toContainText(/PRASOLOV_PGV1/);

    await page.goto("/learn/conversations");
    await expect(page.getByText(prompt.slice(0, 40))).toBeVisible();
  });

  test("@llm step hint and grading on a power-of-a-point problem", async ({ page }) => {
    await page.goto(`/learn/solve/${POWER_POINT_PROBLEM}`);
    const leave = page.getByRole("button", { name: "Leave the detour and go back now" });
    if (await leave.isVisible().catch(() => false)) await leave.click();

    const hint = page.getByRole("button", { name: /Get a hint|Reveal this step/ });
    if (await hint.isVisible().catch(() => false)) {
      await hint.click();
      await expect(page.getByText(/You used \d+ hints? on this step/)).toBeVisible({ timeout: 60_000 });
    }

    await page.getByLabel("Your reasoning for this step").fill(
      "Draw a line through P meeting the circle at A and B; then PA times PB equals the radius squared.");
    await page.getByRole("button", { name: "Check my step" }).click();
    await expect(page.getByRole("status").filter({ hasText: /correct|incorrect|partially/i }).first())
      .toBeVisible({ timeout: 90_000 });
  });
});
