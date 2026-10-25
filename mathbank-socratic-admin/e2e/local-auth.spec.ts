import { expect, test } from "@playwright/test";

test("real local cookies, CSRF, restore, logout and replay without AWS", async ({ page, context }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("browser-author");
  await page.getByLabel("Password").fill("synthetic-browser-test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Local testing", { exact: true })).toBeVisible();
  // Auth is real; unfinished catalog routes must remain explicit failures, not fake success.
  await expect(page.getByText("Catalog unavailable. Retry before creating or choosing strategies.")).toBeVisible();
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
  await expect(page.getByText("Local testing", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Administrator sign in" })).toBeVisible();
  await context.addCookies(staffCookies);
  const replay = await page.evaluate(async () =>
    (await fetch("/v1/admin/socratic/session")).status);
  expect(replay).toBe(401);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
