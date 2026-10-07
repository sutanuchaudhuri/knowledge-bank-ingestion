import { expect, test } from "@playwright/test";
import { loginAdmin, watchPageErrors } from "./helpers.mjs";

for (const width of [1440, 390]) {
  test(`feedback queue paginates and records evidence separately at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await loginAdmin(page);
    const watch = watchPageErrors(page);
    let reviewed = false;
    await page.route("**/api/rest/admin/pedagogy?view=feedback&*", (route) => {
      const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
      const count = offset === 0 ? 10 : 1;
      return route.fulfill({ json: { total: 11, items: Array.from({ length: count }, (_, index) => ({
        feedback_id: `report-${offset + index}`, canonical_code: `TEST_${offset + index}`,
        topic: "Power of point", reason: "No circle or secant evidence in the statement.",
        status: reviewed && offset === 10 ? "RESOLVED" : "PENDING",
        audit: { version: "topic-audit-v1", published_step_count: 9, supporting_step_ids: [],
          structural_validation: { status: "REVIEW_REQUIRED" }, suggested_error_kind: "METADATA" },
        related_report_count: 2,
        review_note: reviewed && offset === 10 ? "Checked source and solution-step evidence." : null,
      })) } });
    });
    await page.route("**/api/rest/admin/pedagogy", async (route) => {
      const body = route.request().postDataJSON();
      expect(body.action).toBe("feedback-review");
      expect(body.feedback_id).toBe("report-10");
      expect(body.status).toBe("RESOLVED");
      expect(body.note).toBe("Checked source and solution-step evidence.");
      expect(body.retrieval_verdict).toBe("IRRELEVANT");
      expect(body.error_kind).toBe("METADATA");
      reviewed = true;
      await route.fulfill({ json: { status: "RESOLVED" } });
    });
    await page.goto("/admin/pedagogy");
    const queue = page.getByRole("region", { name: "Learner relevance reports" });
    await expect(queue.getByRole("button", { name: "TEST_0", exact: true })).toBeVisible();
    await queue.getByRole("button", { name: "Next page" }).click();
    await queue.getByRole("button", { name: "TEST_10", exact: true }).click();
    await expect(queue.getByRole("button", { name: "Load original problem and solution evidence" })).toBeVisible();
    await queue.locator("summary").click();
    await expect(queue).toContainText("9 published steps");
    await expect(queue.getByRole("button", { name: "Save report decision" })).toBeDisabled();
    await queue.getByLabel("Review evidence", { exact: true }).fill("Checked source and solution-step evidence.");
    await queue.getByLabel("Retrieval relevance").selectOption("IRRELEVANT");
    await queue.getByLabel("Issue type").selectOption("METADATA");
    await queue.getByRole("button", { name: "Save report decision" }).click();
    await expect(queue).toContainText("RESOLVED");
    await queue.getByRole("button", { name: "TEST_10", exact: true }).click();
    await expect(queue).toContainText("Checked source and solution-step evidence.");
    await expect(queue.getByRole("button", { name: "Save report decision" })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    watch.assertClean();
  });
}
