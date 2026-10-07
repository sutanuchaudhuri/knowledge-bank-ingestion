import { expect, test } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`topic theory/checkpoint and progressive diagram frames at ${width}px`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 900 });
    const overlays = ["Recognize circle", "First chord", "Second chord", "Compare products"]
      .map((caption, index) => ({ id: `frame_${index}`, caption, actions: [{ action: "HIGHLIGHT", targets: ["P"] }] }));
    const plan = { subject: "GEOMETRY", topic: "Power of a point", title: "Intersecting chords",
      summary: "Instructional example, not a source figure.", elements: [{ kind: "POINT", id: "P", x: 100, y: 100 }],
      overlays, frames: overlays.map((overlay) => ({ overlay_id: overlay.id })) };
    const answer = "## Learn · Power of a point\n**Step 1 of 7 · THEORY**\n\nA chord joins two points on a circle.\n\n"
      + String.raw`For intersecting chords, $PA\cdot PB=PC\cdot PD$.`
      + "\n\n**Checkpoint:** A chord has which endpoints?\n- A. One outside\n- B. Both on the circle\n\n"
      + "```geometry-artifact\n" + JSON.stringify(plan) + "\n```";
    const names = ["Theory", "Recognition", "Skill", "Guided", "Mixed", "Transfer", "Problem"];
    const progressFor = (skipped = false) => ({
      topic: "Power of a point",
      stages: names.map((title, index) => ({
        index, title, short_title: title, acronym: title.slice(0, 3).toUpperCase(),
        icon: "book-half", status: index === 0 ? (skipped ? "skipped" : "active") : index === 1 && skipped ? "active" : "pending",
        is_current: index === (skipped ? 1 : 0), seconds: index === 0 ? 12 : 0,
      })),
      current_unit: skipped ? 1 : 0, completed: 0, skipped: skipped ? 1 : 0,
      checkpoint: skipped ? null : {
        question: "A chord has which endpoints?",
        choices: ["One outside", "Both on the circle"],
        input_type: "single-choice", hint_available: true, hint: null,
      },
      feedback: skipped ? "Stage skipped. It remains marked as skipped, not completed." : "",
      feedback_tone: skipped ? "warning" : null,
    });
    await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
    await page.route("**/api/agent/run", (route) => {
      const skipped = route.request().postDataJSON().text === "skip step";
      return route.fulfill({ contentType: "text/event-stream",
        body: `data: ${JSON.stringify({ type: "progress", progress: progressFor(skipped) })}\n\n`
          + `data: ${JSON.stringify({ type: "answer", text: answer })}\n\n`
          + "data: {\"type\":\"done\"}\n\n" });
    });
    const frames = [];
    await page.route("**/api/rest/artifacts/geometry-preview/content?*", (route) => {
      const frame = Number(new URL(route.request().url()).searchParams.get("frame"));
      frames.push(frame);
      return route.fulfill({ contentType: "image/svg+xml",
        body: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 440"><text x="10" y="40">Frame ${frame}</text></svg>` });
    });
    await page.goto("/");
    await page.getByRole("textbox", { name: "Your question" }).fill("Power of point");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText("Step 1 of 7 · THEORY", { exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "Practice problem" })).toHaveCount(0);
    await expect(page.locator(".katex")).toHaveCount(1);
    await expect(page.getByRole("heading", { name: "Path to mastery" })).toBeVisible();
    await expect(page.getByRole("radio", { name: /Both on the circle/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Upload written work for the current problem" })).toBeDisabled();
    await expect(page.getByRole("button", { name: /Skip step/ })).toBeVisible();
    await page.getByRole("button", { name: /Skip step/ }).click();
    await expect(page.getByText(/Stage skipped/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Jump to stage: Recognition" })).toBeDisabled();
    const diagram = page.locator(".mb-generated-diagram").last();
    const image = diagram.getByRole("img", { name: "Intersecting chords" });
    await expect(image).toBeVisible();
    await expect(diagram.getByRole("button", { name: "Previous diagram frame" })).toBeDisabled();
    await diagram.getByRole("button", { name: "Next diagram frame" }).click();
    await expect(diagram.getByText("2 / 4 · First chord", { exact: true })).toBeVisible();
    await expect(image).toBeVisible();
    expect(frames).toContain(1);
    await diagram.getByRole("button", { name: "Previous diagram frame" }).click();
    await expect(diagram.getByText("1 / 4 · Recognize circle", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });

  test(`known book without a PDF is distinct from a missing source at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
    await page.route("**/api/rest/solve/source/**", (route) => route.fulfill({ json: {
      kind: "identified", book_title: "Problems in Plane and Solid Geometry", chapter: 6,
      source_problem_id: "6.76", provenance_status: "LOCATION_INCOMPLETE", embed_url: null,
    } }));
    await page.route("**/api/rest/solve/diagrams/**", (route) => route.fulfill({ json: [] }));
    await page.route("**/api/agent/run", (route) => route.fulfill({ contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ type: "answer", text: "Source identity for **PRASOLOV_PGV1_CH06_P076**." })}\n\ndata: {"type":"done"}\n\n` }));
    await page.goto("/");
    await page.getByRole("textbox", { name: "Your question" }).fill("Show source identity");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const source = page.getByTestId("problem-source");
    await expect(source).toContainText("Source book identified");
    await expect(source).toContainText("Chapter 6");
    await expect(source).toContainText("Original page/location provenance incomplete");
    await expect(source.getByRole("button")).toHaveCount(0);
    await expect(source.getByRole("link")).toHaveCount(0);
    await expect(source.locator("iframe")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("written work is bound to the selected problem in a multi-problem reply", async ({ page }) => {
  const created = [];
  const uploaded = [];
  const answer = "**Canonical Code**: `FIRST_PROBLEM`\n\n**Canonical Code**: `SECOND_PROBLEM`";
  await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
  await page.route("**/api/agent/run", (route) => route.fulfill({ contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ type: "answer", text: answer })}\n\n`
      + "data: {\"type\":\"done\"}\n\n" }));
  await page.route("**/api/rest/attempt-media/submissions", (route) => {
    created.push(route.request().postDataJSON());
    return route.fulfill({ status: 201, json: {
      submission_id: "11111111-1111-4111-8111-111111111111", transcription_version: 1,
    } });
  });
  await page.route("**/api/rest/attempt-media/submissions/*/assets?*", (route) => {
    uploaded.push({
      contentType: route.request().headers()["content-type"],
      path: new URL(route.request().url()).pathname,
    });
    return route.fulfill({ status: 201, json: {
      media_asset_id: "22222222-2222-4222-8222-222222222222", transcription_version: 2,
    } });
  });
  await page.route("**/learn/attempt-media?*", (route) => route.fulfill({
    status: 200, contentType: "text/html", body: "<main>Attempt workspace</main>",
  }));

  await page.goto("/");
  await page.getByRole("textbox", { name: "Your question" }).fill("Give me two practice problems");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const problemSelect = page.getByRole("combobox", { name: "Problem for uploaded work" });
  await expect(problemSelect).toBeVisible();
  const uploadButton = page.getByRole("button", { name: "Upload written work for the current problem" });
  await expect(uploadButton).toBeDisabled();
  await problemSelect.selectOption("SECOND_PROBLEM");
  await expect(uploadButton).toBeEnabled();
  await page.getByLabel("Choose a photo or PDF of written work").setInputFiles({
    name: "work.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4"),
  });

  await expect(page).toHaveURL(/problem_ref=SECOND_PROBLEM/);
  await expect(page.getByText("Attempt workspace")).toBeVisible();
  expect(created).toEqual([{ problem_ref: "SECOND_PROBLEM" }]);
  expect(uploaded).toEqual([{
    contentType: "application/pdf",
    path: "/api/rest/attempt-media/submissions/11111111-1111-4111-8111-111111111111/assets",
  }]);
});
