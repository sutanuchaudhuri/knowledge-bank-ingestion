import { expect, test } from "@playwright/test";
import { watchPageErrors } from "./helpers.mjs";

for (const width of [1440, 390]) {
  test(`body attributes injected by a grammar extension do not warn during hydration at ${width}px`, async ({ page }) => {
    const watch = watchPageErrors(page);
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
    await page.route("**/api/rest/learner/me", (route) => route.fulfill({ status: 401, json: { detail: "Not signed in" } }));
    await page.addInitScript(() => {
      const observer = new MutationObserver(() => {
        if (!document.body) return;
        document.body.setAttribute("data-new-gr-c-s-check-loaded", "14.1335.0");
        document.body.setAttribute("data-gr-ext-installed", "");
        observer.disconnect();
      });
      observer.observe(document, { childList: true, subtree: true });
    });

    await page.goto("/");
    await expect(page.getByTestId("chat-saved-state")).toContainText("Anonymous");
    await expect(page.locator("body")).toHaveAttribute("data-new-gr-c-s-check-loaded", "14.1335.0");
    await expect(page.locator("body")).toHaveAttribute("data-gr-ext-installed", "");
    await page.getByRole("textbox", { name: "Your question" }).fill("Power of a point");
    await expect(page.getByRole("button", { name: "Send", exact: true })).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    watch.assertClean();
  });
}
