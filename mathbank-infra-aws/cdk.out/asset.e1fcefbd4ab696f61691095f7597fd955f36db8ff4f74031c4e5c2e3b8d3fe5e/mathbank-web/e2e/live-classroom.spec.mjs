// mathbank-live (separate deployable on :5174) — two browsers in one class, no paid calls.
// Instructor creates a session in the console UI; student joins by code; board widget, instructor
// message (LaTeX) and a live poll reach the student in realtime; results reveal to both.
import { expect, test } from "@playwright/test";
import { E2E_STUDENT, adminCredentials, loginStudent, watchPageErrors } from "./helpers.mjs";

const LIVE = process.env.E2E_LIVE_URL || "http://localhost:5174";

test.describe("live classroom", () => {
  test.skip(process.env.E2E_SKIP_LIVE === "1", "live app disabled");

  test("instructor drives, student receives widgets, messages and polls in realtime", async ({ browser }) => {
    const reachable = await fetch(`${LIVE}/login`).then((r) => r.ok).catch(() => false);
    test.skip(!reachable, `mathbank-live not running at ${LIVE}`);

    const insCtx = await browser.newContext();
    const stuCtx = await browser.newContext();
    const ins = await insCtx.newPage();
    const stu = await stuCtx.newPage();
    const insErrors = watchPageErrors(ins);
    const stuErrors = watchPageErrors(stu);

    // sign-in through the live app's own UI
    await ins.goto(`${LIVE}/login`);
    const creds = adminCredentials();
    await ins.getByTestId("instructor-login").getByLabel("Username").fill(creds.username);
    await ins.getByTestId("instructor-login").getByLabel("Password").fill(creds.password);
    await ins.getByTestId("instructor-login").getByRole("button", { name: "Sign in" }).click();
    await expect(ins.getByText("Start a live session")).toBeVisible();

    await stu.goto("http://localhost:5173/login");
    await loginStudent(stu); // ensures the regression learner exists (registers once)
    await stu.goto(`${LIVE}/login`);
    await stu.getByTestId("student-login").getByLabel("Email").fill(E2E_STUDENT.email);
    await stu.getByTestId("student-login").getByLabel("Password").fill(E2E_STUDENT.password);
    await stu.getByTestId("student-login").getByRole("button", { name: "Sign in" }).click();
    await expect(stu.getByText("Join a live class")).toBeVisible();

    // instructor creates the session → console
    await ins.getByLabel("Title").fill(`E2E live ${Date.now()}`);
    await ins.getByRole("button", { name: "Create session" }).click();
    await expect(ins.getByTestId("connection-status")).toHaveText("live");
    const code = (await ins.getByTestId("join-code").textContent()).trim();
    await ins.getByRole("button", { name: "Start" }).click();

    // student joins by code → classroom
    await stu.getByLabel("Join code").fill(code);
    await stu.getByRole("button", { name: "Join" }).click();
    await expect(stu.getByTestId("connection-status")).toHaveText("live");
    await expect(ins.getByTestId("participants")).toContainText("E2E");

    // board widget
    await ins.getByRole("button", { name: "power of a point" }).click();
    await expect(stu.getByTestId("live-stage").locator("svg").first()).toBeVisible();

    // instructor message with LaTeX renders as KaTeX for the student
    await ins.getByLabel("Message to class").fill("Remember $PA \\cdot PB = PT^2$");
    await ins.getByTestId("instructor-composer").getByRole("button", { name: "Send to class" }).click();
    await expect(stu.getByTestId("live-message").last()).toContainText("Remember");
    await expect(stu.getByTestId("live-message").last().locator(".katex").first()).toBeVisible();

    // live poll → answer → reveal
    await ins.getByRole("button", { name: "Open poll" }).click();
    await expect(stu.getByTestId("live-activity")).toBeVisible();
    await stu.getByTestId("live-activity").getByRole("button", { name: "6", exact: true }).click();
    await expect(stu.getByTestId("answer-sent")).toBeVisible();
    await expect(ins.getByTestId("poll-status")).toContainText("1");
    await ins.getByTestId("poll-status").getByRole("button", { name: "Reveal" }).click();
    await expect(stu.getByTestId("live-activity")).toContainText(/100|1 response/);

    // question to the instructor (no paid call) is echoed locally and reaches the console
    await stu.getByLabel("Your question").fill("Why is PT squared?");
    await stu.getByRole("button", { name: "Ask instructor" }).click();
    await expect(stu.getByTestId("live-feed")).toContainText("Why is PT squared?");
    await expect(ins.getByTestId("event-log")).toContainText("student.");

    await ins.getByRole("button", { name: "Complete" }).click();
    insErrors.assertClean();
    stuErrors.assertClean();
    await insCtx.close();
    await stuCtx.close();
  });
});
