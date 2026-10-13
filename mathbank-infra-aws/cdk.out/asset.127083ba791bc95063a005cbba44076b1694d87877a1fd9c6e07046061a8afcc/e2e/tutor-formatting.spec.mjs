import { expect, test } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`learning-plan route, checkpoint and evidence have distinct readable panels at ${width}px`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error" && /hydrat|same key/i.test(message.text())) errors.push(message.text());
    });
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
    const text = String.raw`### Learning plan

**Why this route:** Explore neighboring terms instead of computing nested fractions.

1. Read the recurrence.
2. Explore neighboring products.

**Your first checkpoint:** What expression do you get by multiplying $x_n$ by $x_{n-1}$?

**Evidence:** 2 stored solution records were supplied to the planner. Their source status is not a correctness certification.

An ordinary paragraph remains unstyled.`;
    await page.route("**/api/agent/run", (route) => route.fulfill({
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ type: "answer", text })}\n\ndata: {"type":"done"}\n\n`,
    }));
    await page.goto("/");
    await page.getByRole("textbox", { name: "Your question" }).fill("Give me a learning plan");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const answer = page.locator(".mb-tutor-answer").last();
    await expect(answer.locator(".mb-learning-plan-panel")).toHaveCount(3);
    const backgrounds = [];
    for (const [section, label] of [["route", "Why this route:"], ["checkpoint", "Your first checkpoint:"], ["evidence", "Evidence:"]]) {
      const panel = answer.locator(`.mb-learning-plan-${section}`);
      await expect(panel).toBeVisible();
      await expect(panel.locator("strong")).toHaveText(label);
      const style = await panel.evaluate((element) => {
        const css = getComputedStyle(element);
        return { background: css.backgroundColor, border: css.borderLeftWidth, padding: parseFloat(css.paddingTop) };
      });
      expect(style.background).not.toBe("rgba(0, 0, 0, 0)");
      expect(style.border).toBe("4px");
      expect(style.padding).toBeGreaterThanOrEqual(8);
      backgrounds.push(style.background);
    }
    expect(new Set(backgrounds).size).toBe(3);
    await expect(answer.locator(".mb-learning-plan-checkpoint .katex")).toHaveCount(2);
    await expect(answer.locator(".katex-error")).toHaveCount(0);
    await expect(answer.locator(".mb-learning-plan-evidence")).toContainText("not a correctness certification");
    await expect(answer.locator("p").filter({ hasText: "An ordinary paragraph" })).not.toHaveClass(/mb-learning-plan-panel/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });

  test(`tutor step headings stay compact with distinct section and step dividers at ${width}px`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
    const text = String.raw`Here's the problem from AIME 1985:

**Problem:**
Let $x_1=97$, and for $n>1$, let $x_n=\frac{n}{x_{n-1}}$. Calculate the product $x_1x_2x_3x_4x_5x_6x_7x_8$.

**Concepts involved:**
- Sequences and series
- Product of functions

**Diagrams:**
No diagrams are provided for this problem.

### Step 1: Understanding the Sequence
Read the recurrence before choosing an approach.

1. Identify the previous term.
2. Explore neighboring terms.

### Diagnostic Question
What expression do you get by multiplying $x_n$ by $x_{n-1}$?`;
    await page.route("**/api/agent/run", (route) => route.fulfill({
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ type: "answer", text })}\n\ndata: {"type":"done"}\n\n`,
    }));
    await page.goto("/");
    await page.getByRole("textbox", { name: "Your question" }).fill("Help me understand the recurrence");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const heading = page.getByRole("heading", { name: "Diagnostic Question" });
    await expect(heading).toBeVisible();
    for (const name of ["Step 1: Understanding the Sequence", "Diagnostic Question"]) {
      const style = await page.getByRole("heading", { name }).evaluate((element) => {
        const css = getComputedStyle(element);
        return { size: parseFloat(css.fontSize), border: css.borderTopWidth,
          padding: parseFloat(css.paddingTop), margin: parseFloat(css.marginBottom) };
      });
      expect(style.size).toBeLessThanOrEqual(17);
      expect(style.border).toBe("1px");
      expect(style.padding).toBeGreaterThanOrEqual(8);
      expect(style.margin).toBeGreaterThanOrEqual(8);
    }
    const answer = page.locator(".mb-tutor-answer").last();
    const listDivider = await answer.locator("ol > li").nth(1).evaluate((element) => getComputedStyle(element).borderTopWidth);
    expect(listDivider).toBe("1px");
    const labelDivider = await answer.locator("p").filter({ hasText: /^Concepts involved:$/ }).evaluate((element) => getComputedStyle(element).borderTopWidth);
    expect(labelDivider).toBe("1px");
    await expect(answer.locator(".katex-error")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });

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
