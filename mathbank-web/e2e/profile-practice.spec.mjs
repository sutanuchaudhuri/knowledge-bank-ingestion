import { test, expect } from "@playwright/test";
import { watchPageErrors } from "./helpers.mjs";

for (const width of [1440, 390]) {
  test(`profile shows exact theme coverage, tabs and practice links at ${width}px`, async ({ page, baseURL }) => {
    const errors = watchPageErrors(page);
    await page.context().addCookies([{ name: "mb_student_token", value: "mock-student-token", url: baseURL }]);
    await page.setViewportSize({ width, height: 900 });
    let fail = true;
    await page.route("**/api/rest/learner/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/me")) return route.fulfill({ json: { student_id: "mock", first_name: "Test", email: "test@example.test" } });
      if (path.endsWith("/attempts")) return route.fulfill({ json: [] });
      if (path.endsWith("/improvement-plan")) return route.fulfill({ json: { focus_areas: [] } });
      if (path.endsWith("/practice-progress")) return fail
        ? route.fulfill({ status: 503, json: { error: "Practice coverage unavailable" } })
        : route.fulfill({ json: { items: [
          { kind: "concept", name: "Circles", slug: "geo-circles", available: 10, attempted: 3, remaining: 7 },
          { kind: "concept", name: "Sequences", slug: "alg-sequences", available: 5, attempted: 0, remaining: 5 },
          { kind: "technique", name: "Power of a Point", slug: "geo-power-method", available: 8, attempted: 8, remaining: 0 },
          { kind: "technique", name: "No evidence", slug: "empty", available: 0, attempted: 0, remaining: 0 },
          ...Array.from({ length: 13 }, (_, index) => ({ kind: "concept", name: `Extra ${index}`, slug: `extra-${index}`, available: 1, attempted: 0, remaining: 1 })),
        ] } });
      return route.fulfill({ json: { concepts: [], techniques: [] } });
    });
    await page.goto("/profile");
    await expect(page.getByRole("alert").filter({ hasText: "Practice coverage unavailable" })).toBeVisible();
    fail = false;
    await page.getByRole("button", { name: "Retry practice progress" }).click();
    const circles = page.getByRole("article", { name: "Circles", exact: true });
    await expect(circles).toBeVisible();
    await expect(circles.locator("dd")).toHaveText(["10", "3", "7"]);
    const bar = circles.getByRole("progressbar");
    await expect(bar).toHaveAttribute("aria-valuenow", "3");
    await expect(bar).toHaveAttribute("aria-valuemax", "10");
    expect(await bar.locator(".mb-bar-fill").evaluate((element) => element.style.width)).toBe("30%");
    await expect(circles.getByRole("link", { name: "Jump to practice Circles" })).toHaveAttribute("href", "/db/problems?concept=geo-circles");
    await expect(page.getByRole("article")).toHaveCount(12);
    await page.getByRole("button", { name: "Next page" }).click();
    await expect(page.getByRole("article")).toHaveCount(3);
    await page.getByLabel("Practice coverage", { exact: true }).selectOption("new");
    await expect(circles).toHaveCount(0);
    await page.getByLabel("Search practice themes").fill("Sequences");
    await expect(page.getByRole("article")).toHaveCount(1);
    await page.getByLabel("Search practice themes").fill("");
    await page.getByLabel("Practice coverage", { exact: true }).selectOption("all");
    await page.getByRole("tab", { name: /^Techniques/ }).click();
    const power = page.getByRole("article", { name: "Power of a Point", exact: true });
    await expect(power).toContainText("All attempted");
    await expect(power.getByRole("link")).toHaveAttribute("href", "/db/problems?technique=geo-power-method");
    await expect(page.getByRole("article", { name: "No evidence" }).getByRole("link")).toHaveCount(0);
    await page.getByRole("tab", { name: "Strength & weakness", exact: true }).click();
    await expect(page.getByText("No mastery data yet.", { exact: false })).toBeVisible();
    await expect(power).toHaveCount(0);
    await page.getByRole("tab", { name: "Past attempts", exact: true }).click();
    await expect(page.getByText("No attempts recorded yet.")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    errors.assertClean();
  });
}
