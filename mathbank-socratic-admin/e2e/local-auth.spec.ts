import { expect, test } from "@playwright/test";

test("real local cookies, CSRF, restore, logout and replay without AWS", async ({ page, context }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("browser-author");
  await page.getByLabel("Password").fill("synthetic-browser-test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const localPill = page.locator(".sc-local");
  await expect(localPill).toBeVisible();
  await expect(localPill).toContainText("Local");
  // Auth is real; unfinished catalog routes must remain explicit failures, not fake success.
  if (page.viewportSize()!.width < 760) await page.getByRole("button", { name: "Toggle workspace search" }).click();
  await expect(page.getByRole("button", { name: "Retry loading drafts" })).toBeVisible();
  const cookies = await context.cookies();
  const staffCookies = cookies.filter(cookie => cookie.name.startsWith("mathbank_socratic_"));
  expect(staffCookies).toHaveLength(2);
  expect(staffCookies.every(cookie => cookie.httpOnly && cookie.sameSite === "Strict"
    && cookie.path === "/v1/admin/socratic" && !cookie.secure)).toBe(true);
  expect(await page.evaluate(() => document.cookie)).not.toContain("mathbank_socratic");
  const denied = await page.evaluate(async () =>
    (await fetch("/v1/admin/socratic/session", { method: "DELETE" })).status);
  expect(denied).toBe(403);
  await page.reload();
  await expect(page.locator(".sc-local")).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("region", { name: "Sign in" })).toBeVisible();
  await context.addCookies(staffCookies);
  const replay = await page.evaluate(async () =>
    (await fetch("/v1/admin/socratic/session")).status);
  expect(replay).toBe(401);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
