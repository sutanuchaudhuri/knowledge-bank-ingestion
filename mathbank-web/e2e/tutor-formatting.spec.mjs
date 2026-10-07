import { expect, test } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`stored and streaming math plus constrained semantic styles at ${width}px`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
    await page.route("**/api/agent/run", (route) => {
      const draft = String.raw`**Problem: In the diagram below, let \\( OT = 25 \\) and \\( AM = MB = 30 \\). Find \\( MD \\).**`;
      const text = draft + "\n\n**Source:** Stanford Math Tournament\n\n" +
        String.raw`[Given \(OT=25\)](#mb-tone-given). [Find \(MD\)](#mb-tone-goal). [Key **idea**](#mb-tone-insight). [Be *careful*](#mb-tone-warning).` +
        "\n\n```js\nconst literal = \"\\\\( MD \\\\)\";\n```";
      return route.fulfill({ contentType: "text/event-stream", body:
        `data: ${JSON.stringify({ type: "answer", text: draft })}\n\n` +
        `data: ${JSON.stringify({ type: "answer", text })}\n\ndata: {"type":"done"}\n\n` });
    });
    await page.goto("/");
    await page.getByRole("textbox", { name: "Your question" }).fill("Show the formatted problem");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const problem = page.getByRole("region", { name: "Practice problem" });
    await expect(problem.locator(".mb-tutor-problem-title")).toHaveText("Problem");
    await expect(problem.locator(".katex")).toHaveCount(3);
    await expect(problem).not.toContainText("\\");
    await expect(page.locator(".mb-format-given .katex")).toHaveCount(1);
    await expect(page.locator(".mb-format-goal .katex")).toHaveCount(1);
    await expect(page.locator(".mb-format-insight strong")).toHaveText("idea");
    await expect(page.locator(".mb-format-warning em")).toHaveText("careful");
    await expect(page.locator('a[href^="#mb-tone-"]')).toHaveCount(0);
    await expect(page.locator("pre code")).toContainText(String.raw`const literal = "\\( MD \\)";`);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    expect(errors).toEqual([]);
  });
}
