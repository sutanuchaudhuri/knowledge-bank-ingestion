import { expect, test } from "@playwright/test";
import { watchPageErrors } from "./helpers.mjs";

const CODE = "PUMAC_2008_A_NT_Q05";
const RELATED = "AIME_2016_I_Q04";
const competition = {
  competition_id: "pumac", external_code: "PUMAC",
  name: "Princeton University Mathematics Competition (PUMaC)",
  level: "Division A/B + Team/Power/Finals/Live",
  papers: 22, problems: 174, problems_with_concept: 156, problems_with_technique: 150,
};
const problem = (code) => ({
  canonical_code: code, competition: code === CODE ? competition.name : "AIME",
  year: 2008, paper_code: "Division A Number Theory-Annual", problem_number: 5,
  statement_text: "Find $x$ when $x^2 = 16$.",
  concepts: [{ name: "Number theory", slug: "number-theory" }],
  techniques: [{ name: "Modular arithmetic", slug: "modular-arithmetic" }],
  diagrams: [{ problem_image_id: "preview-image", ordinal: 1, alt: "Question-specific figure" }],
  official_answer: "SECRET ANSWER", solutions: [{ body_markdown: "SECRET SOLUTION" }],
});

async function mockCorpus(page, { searchError = false } = {}) {
  const calls = { lists: [], details: [], searches: [], sessions: [], runs: [] };
  await page.route("**/api/rest/**", (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.endsWith("/learner/me")) return route.fulfill({ status: 401, json: { detail: "Not signed in" } });
    if (url.pathname.endsWith("/competitions")) return route.fulfill({ json: { items: [competition] } });
    if (url.pathname === "/api/rest/problems") {
      calls.lists.push(Object.fromEntries(url.searchParams));
      return route.fulfill({ json: { items: [problem(Number(url.searchParams.get("offset")) ? RELATED : CODE)], hasMore: !Number(url.searchParams.get("offset")) } });
    }
    if (url.pathname.startsWith("/api/rest/problems/")) {
      const code = decodeURIComponent(url.pathname.split("/").at(-1));
      calls.details.push(code);
      return route.fulfill({ json: problem(code) });
    }
    if (url.pathname === "/api/rest/search") {
      calls.searches.push(request.postDataJSON());
      if (searchError && calls.searches.length === 1) return route.fulfill({ status: 503, json: { error: "Related search temporarily unavailable" } });
      return route.fulfill({ json: { results: [problem(CODE), problem(RELATED), problem(RELATED)], warnings: ["Graph unavailable · text matches only"] } });
    }
    if (url.pathname.startsWith("/api/rest/solve/images/")) return route.fulfill({
      contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><circle cx="100" cy="50" r="40"/></svg>',
    });
    if (url.pathname.startsWith("/api/rest/solve/source/")) return route.fulfill({ json: { kind: "identified", book_title: "Synthetic source", embed_url: null } });
    return route.fulfill({ json: [] });
  });
  await page.route("**/api/agent/session", (route) => {
    calls.sessions.push(route.request().postDataJSON());
    return route.fulfill({ json: { linked: false } });
  });
  await page.route("**/api/agent/run", (route) => {
    calls.runs.push(route.request().postDataJSON());
    return route.fulfill({ contentType: "text/event-stream",
      body: 'data: {"type":"answer","text":"Let us start with the given information."}\n\ndata: {"type":"done"}\n\n' });
  });
  return calls;
}

for (const width of [1440, 390]) {
  test(`competition previews, related figures and tutor handoff at ${width}px`, async ({ page }) => {
    const watch = watchPageErrors(page);
    const calls = await mockCorpus(page);
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/db");
    await page.getByRole("button", { name: competition.name, exact: true }).click();
    await expect(page.getByText("Concept-tagged", { exact: true })).toBeVisible();
    expect(calls.lists).toEqual([]);
    await page.getByText("Preview questions", { exact: true }).click();
    await expect(page.locator(".mb-corpus-preview > summary").filter({ hasText: CODE })).toBeVisible();
    expect(calls.details).toEqual([]);
    await page.locator(".mb-corpus-preview > summary").filter({ hasText: CODE }).click();
    await page.getByText("Reveal answer and solutions", { exact: true }).click();
    await expect(page.getByText("SECRET ANSWER", { exact: true })).toBeVisible();
    await expect(page.getByText("SECRET SOLUTION", { exact: true })).toBeHidden();
    await page.getByText("Reveal answer and solutions", { exact: true }).click();
    await expect(page.getByText("SECRET ANSWER", { exact: true })).toHaveCount(0);
    const preview = page.getByTestId(`problem-preview-${CODE}`);
    await expect(preview.getByText("Number theory", { exact: true })).toBeVisible();
    await expect(preview.getByText("Modular arithmetic", { exact: true })).toBeVisible();
    await expect(preview.locator(".katex")).toHaveCount(2);
    await expect(preview.getByRole("img", { name: "Question-specific figure" })).toBeVisible();
    await expect(page.getByText("SECRET ANSWER")).toHaveCount(0);
    await expect(page.getByText("SECRET SOLUTION")).toHaveCount(0);
    expect(calls.searches).toEqual([]);
    await page.getByText("Explore related problems", { exact: true }).click();
    await expect(page.getByText("Graph unavailable · text matches only")).toBeVisible();
    const relatedSummary = page.locator(".mb-corpus-preview > summary").filter({ hasText: RELATED });
    await expect(relatedSummary).toHaveCount(1);
    await relatedSummary.click();
    const relatedPreview = page.getByTestId(`problem-preview-${RELATED}`);
    await expect(relatedPreview.getByRole("img", { name: "Question-specific figure" })).toBeVisible();
    await expect(relatedPreview.getByRole("link", { name: "Discuss with tutor" })).toHaveAttribute("href", `/?problem=${RELATED}`);
    expect(calls.searches[0].retrieval.semantic).toBe(false);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    watch.assertClean();

    await relatedPreview.getByRole("link", { name: "Discuss with tutor" }).click();
    const selected = page.getByRole("region", { name: "Selected corpus problem" });
    await expect(selected.getByRole("img", { name: "Question-specific figure" })).toBeVisible();
    const question = page.getByRole("textbox", { name: "Your question" });
    await expect(question).toHaveValue(new RegExp(RELATED));
    await expect(page.getByRole("button", { name: "Send", exact: true })).toBeEnabled();
    expect(calls.sessions.at(-1).context.problem_code).toBe(RELATED);
    expect(calls.runs).toEqual([]);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText("Let us start with the given information.")).toBeVisible();
    expect(calls.runs[0].text).toContain(RELATED);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    watch.assertClean();
  });
}

test("filtered problem cards stay collapsed, paginate and retry failed related searches", async ({ page }) => {
  const calls = await mockCorpus(page, { searchError: true });
  await page.goto("/db/problems?competition=PUMAC");
  await expect(page.getByRole("combobox", { name: "Competition", exact: true })).toHaveValue("PUMAC");
  await expect(page.locator(".mb-corpus-preview > summary").filter({ hasText: CODE })).toBeVisible();
  expect(calls.details).toEqual([]);
  await page.locator(".mb-corpus-preview > summary").filter({ hasText: CODE }).click();
  await page.getByText("Explore related problems", { exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Related search temporarily unavailable" })).toBeVisible();
  await page.getByRole("button", { name: "Retry related search" }).click();
  await expect(page.locator(".mb-corpus-preview > summary").filter({ hasText: RELATED })).toBeVisible();
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.locator(".mb-corpus-preview > summary").filter({ hasText: CODE })).toHaveCount(0);
  await expect(page.locator(".mb-corpus-preview > summary").filter({ hasText: RELATED })).toBeVisible();
  expect(calls.lists.at(-1).offset).toBe("20");
  expect(calls.lists.at(-1).competition).toBe("PUMAC");
  await expect(page.getByRole("button", { name: "Next page" })).toBeDisabled();
});
