import { expect, test } from "@playwright/test";
import { IMAGE_PROBLEM, POWER_POINT_PROBLEM, loginStudent, watchPageErrors } from "./helpers.mjs";

// Signed-in learner flows that make no paid model calls.
test.beforeEach(async ({ page }) => {
  await loginStudent(page);
});

test("nav and home chat reflect the signed-in learner", async ({ page }) => {
  const watch = watchPageErrors(page);
  await page.goto("/");
  await expect(page.getByTestId("nav-student")).toContainText("Signed in");
  await expect(page.getByTestId("chat-saved-state")).toContainText("saved to");
  watch.assertClean();
});

test("my conversations page loads for the learner", async ({ page }) => {
  const watch = watchPageErrors(page);
  await page.goto("/learn/conversations");
  await expect(page.getByRole("heading", { level: 1, name: "My tutor conversations" })).toBeVisible();
  watch.assertClean();
});

test("conversation APIs enforce ownership", async ({ page }) => {
  const list = await page.request.get("/api/rest/learner/conversations");
  expect(list.status()).toBe(200);
  const foreign = await page.request.get("/api/rest/learner/conversations/not-my-session-123/transcript");
  expect([403, 404]).toContain(foreign.status());
});

test("solve workspace renders the problem diagram", async ({ page }) => {
  const watch = watchPageErrors(page);
  await page.goto(`/learn/solve/${IMAGE_PROBLEM}`);
  await expect(page.getByRole("heading", { level: 1, name: IMAGE_PROBLEM })).toBeVisible();
  const diagram = page.getByRole("img", { name: new RegExp(`Diagram 1 for ${IMAGE_PROBLEM}`) });
  await expect(diagram).toBeVisible();
  await expect.poll(() => diagram.evaluate((img) => img.complete && img.naturalWidth)).toBeGreaterThan(0);
  await expect(page.getByText("Solution path")).toBeVisible();
  watch.assertClean();
});

test("power-of-a-point workspace: similar steps and a skill detour round trip", async ({ page }) => {
  const watch = watchPageErrors(page);
  await page.goto(`/learn/solve/${POWER_POINT_PROBLEM}`);
  await expect(page.getByRole("heading", { level: 1, name: POWER_POINT_PROBLEM })).toBeVisible();
  await expect(page.getByText(/does not depend on the choice of a line/)).toBeVisible();

  const leave = page.getByRole("button", { name: "Leave the detour and go back now" });
  if (await leave.isVisible().catch(() => false)) {
    await leave.click();
    await expect(leave).toBeHidden();
  }

  await page.getByRole("button", { name: "Find similar steps" }).click();
  await expect(page.getByText(/PRASOLOV_PGV1_CH\d\d_P\d+/).first()).toBeVisible();

  await page.getByRole("button", { name: /Strengthen this skill|Start a short detour/ }).click();
  await expect(page.getByText(/Detour · strengthening a skill/i)).toBeVisible();
  await expect(page.getByText(`Returns to ${POWER_POINT_PROBLEM}`, { exact: false })).toBeVisible();
  // Import-provenance notes must never be shown as teaching content.
  await expect(page.getByText(/inferred from ordered solution steps/i)).toHaveCount(0);

  await page.getByRole("button", { name: "Leave the detour and go back now" }).click();
  await expect(page.getByRole("button", { name: "Check my step" })).toBeVisible();
  watch.assertClean();
});
