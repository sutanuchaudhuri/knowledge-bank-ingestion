import { test, expect } from "@playwright/test";
import { watchPageErrors } from "./helpers.mjs";

test("profile treats approved ungraded work as awaiting and excludes it from accuracy", async ({ page, baseURL }) => {
  const errors = watchPageErrors(page);
  await page.context().addCookies([{ name: "mb_student_token", value: "mock-student-token", url: baseURL }]);
  await page.route("**/api/rest/learner/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/me")) return route.fulfill({ json: { student_id: "mock-student", email: "mock@example.test", first_name: "Test" } });
    if (path.endsWith("/attempts")) return route.fulfill({ json: [
      { attempt_id: "pending", canonical_code: "UNGRADED", is_correct: null, hint_count: 0, attempted_at: "2026-10-06T12:00:00Z" },
      { attempt_id: "correct", canonical_code: "CORRECT", is_correct: true, hint_count: 0, attempted_at: "2026-10-06T12:00:00Z" },
      { attempt_id: "incorrect", canonical_code: "INCORRECT", is_correct: false, hint_count: 1, attempted_at: "2026-10-06T12:00:00Z" },
    ] });
    if (path.endsWith("/improvement-plan")) return route.fulfill({ json: { focus_areas: [], recommended_problems: [] } });
    if (path.endsWith("/practice-progress")) return route.fulfill({ json: { items: [] } });
    return route.fulfill({ json: { concepts: [], techniques: [] } });
  });
  await page.goto("/profile");
  await page.getByRole("tab", { name: "Past attempts", exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: "UNGRADED" })).toContainText("Awaiting assessment");
  await expect(page.getByRole("row").filter({ hasText: "UNGRADED" })).not.toContainText("Not yet");
  await expect(page.getByText("50%", { exact: true })).toBeVisible();
  await expect(page.getByText("1 awaiting assessment", { exact: true })).toBeVisible();
  errors.assertClean();
});
