import { expect, test } from "@playwright/test";

const id = "1bdcbb22-98cf-413e-8b59-870557292dee";
const nextId = "269b92aa-d92d-442e-bc9a-d3d09872322b";

async function setup(page, width = 1440, suffix = "") {
  await page.setViewportSize({ width, height: 900 });
  await page.route("**/api/agent/session", (route) => route.fulfill({ json: { linked: false } }));
  const requests = [];
  await page.route("**/api/agent/run", async (route) => {
    const body = route.request().postDataJSON();
    requests.push(body);
    const index = requests.length - 1;
    const answer = index === 0 ? `What is $2+3$?${suffix}`
      : index === 1 ? "Start at 2 and count three more. What number do you reach?"
        : "The sum is 5. Next, what is $5+1$?";
    const window = { id: index < 2 ? id : nextId, seconds: 15,
      action: index === 1 ? "explain" : "hint", question: answer };
    await route.fulfill({
      contentType: "text/event-stream",
      body: [
        { type: "answer", text: answer },
        { type: "response-window", window },
        { type: "done" },
      ].map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""),
    });
  });
  await page.goto("/");
  await page.getByRole("textbox", { name: "Your question" }).fill("Teach me with a small question");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("region", { name: "Tutor conversation" })).toContainText("What is");
  await expect(page.getByRole("button", { name: "Pause paced tutoring" })).toBeVisible();
  await page.clock.install();
  return requests;
}

for (const width of [1440, 390]) {
  test(`idle tutoring simplifies then explains and moves forward at ${width}px`, async ({ page }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const requests = await setup(page, width);
    await page.clock.runFor(16000);
    await expect(page.getByRole("region", { name: "Tutor conversation" })).toContainText("Start at 2");
    expect(requests[1].text).toBe(`[Tutor idle:${id}:hint]`);
    await page.clock.runFor(16000);
    await expect(page.getByRole("region", { name: "Tutor conversation" })).toContainText("The sum is 5");
    expect(requests[2].text).toBe(`[Tutor idle:${id}:explain]`);
    expect(requests).toHaveLength(3);
    await expect(page.getByRole("region", { name: "Tutor conversation" })).not.toContainText("[Tutor idle:");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    expect(errors).toEqual([]);
  });
}

test("composing, explicit pause and hidden tab suspend active-time expiry", async ({ page }) => {
  const requests = await setup(page);
  const input = page.getByRole("textbox", { name: "Your question" });
  await input.fill("I am working");
  await page.clock.runFor(60000);
  expect(requests).toHaveLength(1);
  await input.fill("");
  await page.getByRole("button", { name: "Pause paced tutoring" }).click();
  await page.clock.runFor(60000);
  expect(requests).toHaveLength(1);
  await page.getByRole("button", { name: "Resume paced tutoring" }).click();
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.clock.runFor(60000);
  expect(requests).toHaveLength(1);
  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.clock.runFor(16000);
  await expect(page.getByRole("region", { name: "Tutor conversation" })).toContainText("Start at 2");
  expect(requests).toHaveLength(2);
});

test("an idle transport failure stops automation and offers explicit retry", async ({ page }) => {
  const requests = await setup(page);
  await page.route("**/api/agent/run", (route) => {
    requests.push(route.request().postDataJSON());
    return route.fulfill({ status: 503, json: { error: "Timed help unavailable" } });
  });
  await page.clock.runFor(16000);
  await expect(page.getByRole("region", { name: "Tutor conversation" }).getByRole("alert")).toContainText("Timed help unavailable");
  await expect(page.getByRole("button", { name: "Retry timed help" })).toBeVisible();
  await page.clock.runFor(120000);
  expect(requests).toHaveLength(2);
});

test("submitting a student answer cancels the old window", async ({ page }) => {
  const requests = await setup(page);
  await page.clock.runFor(10000);
  await page.getByRole("textbox", { name: "Your question" }).fill("5");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("region", { name: "Tutor conversation" })).toContainText("Start at 2");
  await page.clock.runFor(6000);
  expect(requests).toHaveLength(2);
  expect(requests[1].text).toBe("5");
});

test("recording and transcription pause the response window", async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => ({ getTracks: () => [{ stop() {} }] });
    window.MediaRecorder = class {
      constructor(stream) { this.stream = stream; this.state = "inactive"; this.mimeType = "audio/webm"; }
      start() { this.state = "recording"; }
      stop() { this.state = "inactive"; this.onstop?.(); }
    };
  });
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/voice/stt", async (route) => {
    await gate;
    await route.fulfill({ json: { text: "I am still working" } });
  });
  const requests = await setup(page);
  await page.getByRole("button", { name: "Dictate", exact: true }).click();
  await expect(page.getByTestId("mic-button")).toHaveAttribute("title", "Stop and transcribe");
  await page.clock.runFor(20000);
  expect(requests).toHaveLength(1);
  await page.getByRole("button", { name: "Dictate", exact: true }).click();
  await page.clock.runFor(20000);
  expect(requests).toHaveLength(1);
  release();
  await expect(page.getByRole("textbox", { name: "Your question" })).toHaveValue("I am still working");
});

test("private upload in progress pauses timed help", async ({ page }) => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/rest/attempt-media/submissions", async (route) => {
    await gate;
    await route.fulfill({ status: 503, json: { detail: "Upload temporarily unavailable" } });
  });
  const requests = await setup(page, 1440, "\n\nCanonical Code: AIME_1985_Q01");
  await page.getByLabel("Choose a photo or PDF of written work").setInputFiles({
    name: "work.png", mimeType: "image/png", buffer: Buffer.from("example"),
  });
  await page.clock.runFor(20000);
  expect(requests).toHaveLength(1);
  release();
  await expect(page.getByRole("region", { name: "Tutor conversation" }).getByRole("alert")).toContainText("Upload temporarily unavailable");
});
