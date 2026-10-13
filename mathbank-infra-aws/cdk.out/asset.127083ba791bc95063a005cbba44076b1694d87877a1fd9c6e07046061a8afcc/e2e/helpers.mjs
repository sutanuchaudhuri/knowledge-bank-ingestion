import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));

// Dedicated regression learner. Its attempts/sessions are real rows in the configured
// database, so it is kept separate from demo and human test students.
export const E2E_STUDENT = {
  email: process.env.E2E_STUDENT_EMAIL || "e2e.regression.student@example.com",
  password: process.env.E2E_STUDENT_PASSWORD || "E2eRegression123!",
  first_name: "E2E",
  last_name: "Regression",
};

// A Prasolov problem with published solution steps and a parsed diagram.
export const IMAGE_PROBLEM = process.env.E2E_IMAGE_PROBLEM || "PRASOLOV_PGV1_CH21_P024";
// A Power-of-a-Point problem (radical-axis section) used for the guided walkthrough.
export const POWER_POINT_PROBLEM = process.env.E2E_POWER_POINT_PROBLEM || "PRASOLOV_PGV1_CH03_P050";

function readDotEnv(key) {
  try {
    const text = fs.readFileSync(path.join(here, "..", ".env"), "utf8");
    const line = text.split(/\r?\n/).find((l) => l.startsWith(`${key}=`));
    return line ? line.slice(key.length + 1).trim().replace(/^["']|["']$/g, "") : undefined;
  } catch {
    return undefined;
  }
}

export function adminCredentials() {
  return {
    username: process.env.E2E_ADMIN_USERNAME || readDotEnv("ADMIN_LOGIN_USERNAME") || "admin",
    password: process.env.E2E_ADMIN_PASSWORD || readDotEnv("ADMIN_LOGIN_PASSWORD") || "",
  };
}

/** Collect hydration/runtime errors; call `assertClean()` at the end of a test. */
export function watchPageErrors(page) {
  const errors = [];
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    // Aborted fetches during navigation and expected 401 probes are not application defects.
    if (/net::ERR_ABORTED|favicon|status of 401/.test(text)) return;
    errors.push(`console: ${text}`);
  });
  return {
    errors,
    assertClean() {
      expect(errors.filter((e) => /hydrat|did not match|Unhandled|TypeError|ReferenceError|pageerror/i.test(e))).toEqual([]);
    },
  };
}

/** Register (idempotent) and sign in the regression learner; cookies land in the page context. */
export async function loginStudent(page) {
  const register = await page.request.post("/api/auth/student-register", { data: E2E_STUDENT });
  if (register.status() !== 201) {
    const login = await page.request.post("/api/auth/student-login", {
      data: { email: E2E_STUDENT.email, password: E2E_STUDENT.password },
    });
    expect(login.status(), "student login").toBe(200);
  }
}

export async function loginAdmin(page) {
  const creds = adminCredentials();
  expect(creds.password, "set E2E_ADMIN_PASSWORD or ADMIN_LOGIN_PASSWORD in mathbank-web/.env").not.toBe("");
  const res = await page.request.post("/api/auth/admin-login", { data: creds });
  expect(res.status(), "admin login").toBe(200);
}
