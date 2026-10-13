import { expect, test } from "@playwright/test";

test("@llm real HMMT idle windows simplify then reveal only the current step", async ({ page }) => {
  const requests = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/agent/run")) requests.push(request.postDataJSON());
  });
  await page.goto("/?problem=PAPER_HMMT_2018_NOV_GUTS_Q08");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const conversation = page.getByRole("region", { name: "Tutor conversation" });
  const timer = page.getByLabel("Tutor response window");
  await expect(conversation).toContainText("five-sided polygon");
  await expect(timer).toBeVisible();
  await page.clock.install();
  for (const action of ["hint", "explain"]) {
    const seconds = Number((await timer.innerText()).match(/· (\d+)s/)[1]);
    await page.clock.runFor((seconds + 1) * 1000);
    await expect.poll(() => requests.filter((request) => request.text.endsWith(`:${action}]`)).length).toBe(1);
    await expect(page.getByRole("button", { name: "Stop", exact: true })).toHaveCount(0, { timeout: 45000 });
    await expect(timer).toBeVisible();
  }
  const text = await conversation.innerText();
  // The opening asks for the angle-sum equation, not the angle value or final ratio.
  expect(text).toContain("540");
  expect(text).toContain("270");
  expect(text).not.toMatch(/1\s*\/\s*4|pentagon.*is a rectangle/);
  expect(text).not.toContain("[Tutor idle:");
  await page.getByRole("button", { name: "Pause paced tutoring" }).click();
  await expect(page.getByRole("button", { name: "Resume paced tutoring" })).toBeVisible();
  expect(requests).toHaveLength(3);
});
