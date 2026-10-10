import { expect, test } from "@playwright/test";
import { loginAdmin, watchPageErrors } from "./helpers.mjs";

const releaseId = "00000000-0000-4000-8000-000000000001";
const stateId = "00000000-0000-4000-8000-000000000002";
const course = {
  canonical_code: "MC-REFERENCE",
  title: "Reference lesson",
  description: "Explore a published mathematical idea.",
  metadata: { collection: "examples" },
  releases: [{ release_id: releaseId, version: 1, status: "DRAFT" }],
};
const release = {
  release_id: releaseId,
  version: 1,
  status: "DRAFT",
  modules: [],
  states: [{
    state_id: stateId,
    state_key: "EXPLORE",
    state_type: "VISUAL",
    title: "Explore the idea",
    objective: "Observe the relationship.",
    student_instruction: "Move a point and compare the values.",
    bindings: { concept: [], technique: [], skill: [], misconception: [] },
    interactions: [],
    assets: [],
  }],
  transitions: [],
};

const publishedCourse = {
  canonical_code: "MC-REFERENCE",
  title: "Reference lesson",
  description: "Explore a published mathematical idea.",
  version: 1,
  estimated_minutes: 8,
  learning_objectives: ["Observe the relationship."],
  primary_targets: [{ target_type: "CONCEPT", name: "Mathematical relationship", slug: "relationship" }],
  modules: [],
  transitions: [],
  states: [{
    ...release.states[0],
    interactions: [
      {
        interaction_instance_id: "graph-1",
        title: "Two-state model",
        template_key: "STATE_GRAPH_EXPLORER_V1",
        learning_objective: "Describe possible transitions.",
        instance_config: {
          states: [{ id: "A", label: "First state" }, { id: "B", label: "Second state" }],
          transitions: [
            { from: "A", to: "A", p: "1/4" },
            { from: "A", to: "B", p: "3/4" },
            { from: "B", to: "A", p: "1/4" },
            { from: "B", to: "B", p: "3/4" },
          ],
        },
        initial_state: {},
      },
      {
        interaction_instance_id: "matrix-1",
        title: "Transition matrix",
        template_key: "TRANSITION_MATRIX_EDITOR_V1",
        learning_objective: "Connect graph probabilities to matrix rows.",
        instance_config: {
          states: [{ id: "A", label: "First state" }, { id: "B", label: "Second state" }],
          transitions: [
            { from: "A", to: "A", p: "1/4" },
            { from: "A", to: "B", p: "3/4" },
            { from: "B", to: "A", p: "1/4" },
            { from: "B", to: "B", p: "3/4" },
          ],
        },
        initial_state: {},
      },
      {
        interaction_instance_id: "recurrence-1",
        title: "Recurrence explorer",
        template_key: "RECURRENCE_EXPLORER_V1",
        learning_objective: "Follow the sequence.",
        instance_config: { recurrence: "p[n+1]=0.5*(1-p[n])", initial: "p[0]=1", fixed_point: "1/3" },
        initial_state: {},
      },
      {
        interaction_instance_id: "vieta-1",
        title: "Roots and coefficients",
        template_key: "POLYNOMIAL_ROOT_COEFFICIENT_EXPLORER_V1",
        learning_objective: "Map roots to coefficients.",
        instance_config: {
          controls: {
            r1: { control: "REAL_SLIDER", min: -5, max: 5, step: 0.1, initial: 1 },
            r2: { control: "REAL_SLIDER", min: -5, max: 5, step: 0.1, initial: 2 },
            r3: { control: "REAL_SLIDER", min: -5, max: 5, step: 0.1, initial: -3 },
          },
        },
        initial_state: {},
      },
      {
        interaction_instance_id: "jensen-1",
        title: "Convexity and Jensen",
        template_key: "FUNCTION_GRAPH_EXPLORER_V1",
        learning_objective: "Connect convexity to Jensen direction.",
        instance_config: {
          controls: {
            x1: { control: "REAL_SLIDER", min: -4, max: 4, step: 0.1, initial: -2 },
            x2: { control: "REAL_SLIDER", min: -4, max: 4, step: 0.1, initial: 3 },
            lambda: { control: "PROBABILITY_SLIDER", min: 0, max: 1, step: 0.01, initial: 0.4 },
          },
          function: { expression: "x^2", convexity: "CONVEX" },
        },
        initial_state: {},
      },
    ],
  }],
};

test("published course renders approved template interactions without horizontal overflow", async ({ page }) => {
  const watch = watchPageErrors(page);
  await page.route("**/api/rest/micro-courses/MC-REFERENCE", route => route.fulfill({ json: publishedCourse }));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/learn/courses/MC-REFERENCE");

  await expect(page.getByRole("heading", { level: 1, name: "Reference lesson" })).toBeVisible();
  await expect(page.getByText("First state", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("img", { name: "State transition diagram" })).toBeVisible();
  await expect(page.getByText("p = 3/4", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("p[6] = 0.344")).toBeVisible();
  await expect(page.getByText("Roots to coefficients", { exact: true })).toBeVisible();
  await expect(page.getByText("Jensen's inequality")).toBeVisible();
  await expect(page.getByRole("img", { name: /Graph of x squared/ })).toBeVisible();
  const matrix = page.getByRole("table", { name: "Transition probabilities by source and destination state" });
  await expect(matrix).toBeVisible();
  await expect(page.getByLabel("Probability from First state to Second state")).toHaveValue("0.75");
  await page.getByLabel("Probability from First state to Second state").fill("0.5");
  await expect(matrix).toContainText("0.75");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { level: 1, name: "Reference lesson" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  watch.assertClean();
});

test("admin preview mode renders a DRAFT release with a persistent preview banner (AMC-14)", async ({ page }) => {
  await loginAdmin(page);
  const watch = watchPageErrors(page);
  await page.route("**/api/rest/admin/micro-courses/MC-REFERENCE/preview**", route => route.fulfill({
    json: { ...publishedCourse, version: 1, release_status: "DRAFT" },
  }));
  await page.goto("/learn/courses/MC-REFERENCE?preview=1");

  await expect(page.getByRole("heading", { level: 1, name: "Reference lesson" })).toBeVisible();
  await expect(page.getByText("Admin preview — not visible to students")).toBeVisible();
  await expect(page.getByText("Draft v1")).toBeVisible();
  await expect(page.getByRole("button", { name: /Start lesson/ })).toHaveCount(0);
  watch.assertClean();
});

test("admin micro-course catalog lists courses and links to the workspace", async ({ page }) => {
  await loginAdmin(page);
  const watch = watchPageErrors(page);
  await page.route("**/api/rest/admin/micro-courses", async route => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({ json: [{ ...course, status: "DRAFT", version: 1, state_count: 1, primary_targets: [], updated_at: "2024-01-01T00:00:00Z" }] });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/admin/micro-courses");
  await expect(page.getByRole("heading", { level: 1, name: "Micro-courses" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Reference lesson" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  watch.assertClean();
});

test("admin course workspace tabs expose content authoring and private media upload", async ({ page }) => {
  await loginAdmin(page);
  const watch = watchPageErrors(page);
  await page.route("**/api/rest/admin/micro-courses**", async route => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;
    if (pathname.endsWith("/interactions")) {
      return route.fulfill({ json: [{
        interaction_instance_id: "interaction-1",
        title: "Approved template",
        template_key: "STATE_GRAPH_EXPLORER_V1",
      }] });
    }
    if (pathname.endsWith("/targets")) return route.fulfill({ json: [] });
    if (pathname.endsWith(`/releases/${releaseId}`)) return route.fulfill({ json: release });
    if (pathname.endsWith("/MC-REFERENCE")) return route.fulfill({ json: course });
    return route.fulfill({ json: [{ ...course, status: "DRAFT", state_count: 1, primary_targets: [] }] });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/admin/micro-courses/MC-REFERENCE");
  await expect(page.getByRole("heading", { level: 1, name: "Reference lesson" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("tab", { name: "Content" }).click();
  await expect(page.getByLabel("Approved interaction")).toBeVisible();

  await page.getByRole("tab", { name: "Media" }).click();
  await expect(page.getByLabel("Asset file")).toBeVisible();
  await expect(page.getByLabel("I reviewed this asset and confirm it is approved for course use.")).toBeVisible();
  await expect(page.getByLabel("Asset reviewer")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  watch.assertClean();
});

test("admin course workspace widgets, versions, activity and json tabs render", async ({ page }) => {
  const publishedCourseDetail = {
    ...course,
    releases: [{ release_id: releaseId, version: 1, status: "PUBLISHED", created_by: "admin", created_at: "2024-01-01T00:00:00Z" }],
  };
  await loginAdmin(page);
  const watch = watchPageErrors(page);
  await page.route("**/api/rest/admin/micro-courses**", async route => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;
    if (pathname.endsWith("/templates")) {
      return route.fulfill({ json: {
        templates: [{ interaction_template_version_id: "v1", template_key: "STATE_GRAPH_EXPLORER_V1", interaction_family: "GRAPH", version: 1, version_status: "PUBLISHED" }],
        controls: [{ control_key: "REAL_SLIDER" }],
        icons: [{ token_key: "check", accessible_label: "Check" }],
        animations: [{ animation_key: "FADE_IN" }],
      } });
    }
    if (pathname.endsWith("/activity")) {
      return route.fulfill({ json: {
        canonical_code: "MC-REFERENCE", release_id: releaseId, version: 1,
        total_enrollments: 3, in_progress: 1, completed: 2, completion_rate: 0.6667,
        step_funnel: [{ state_id: stateId, state_key: "EXPLORE", ordinal: 0, title: "Explore the idea", reached_count: 3 }],
        quiz_accuracy: [{ activity_id: "a1", prompt: "What is 2+2?", state_key: "EXPLORE", attempts: 3, correct: 2 }],
        recent_activity: [{ event_id: "e1", event_type: "ENROLLED", created_at: "2024-01-02T10:00:00Z", state_title: "Explore the idea", student_initials: "AB" }],
      } });
    }
    if (pathname.endsWith(`/releases/${releaseId}`)) return route.fulfill({ json: { ...release, status: "PUBLISHED" } });
    if (pathname.endsWith("/MC-REFERENCE")) return route.fulfill({ json: publishedCourseDetail });
    return route.fulfill({ json: [{ ...course, status: "PUBLISHED", version: 1, state_count: 1, primary_targets: [] }] });
  });
  await page.route("**/api/rest/micro-courses/MC-REFERENCE", route => route.fulfill({ json: publishedCourse }));

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/admin/micro-courses/MC-REFERENCE");
  await expect(page.getByRole("heading", { level: 1, name: "Reference lesson" })).toBeVisible();

  await page.getByRole("tab", { name: "Widgets" }).click();
  await expect(page.getByText("STATE_GRAPH_EXPLORER_V1")).toBeVisible();

  await page.getByRole("tab", { name: "Versions" }).click();
  await expect(page.getByText(/v1/).first()).toBeVisible();

  await page.getByRole("tab", { name: "Activity" }).click();
  await expect(page.getByText("What is 2+2?")).toBeVisible();

  await page.getByRole("tab", { name: "JSON" }).click();
  await expect(page.getByText(/"canonical_code": "MC-REFERENCE"/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  watch.assertClean();
});
