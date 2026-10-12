import fs from "node:fs";
import crypto from "node:crypto";

/** Synthetic local session for mocked tests: no login calls or database writes. */
export async function mockAdminSession(page, baseURL) {
  let file = "";
  try { file = fs.readFileSync(new URL("../.env", import.meta.url), "utf8"); } catch {}
  const configured = file.split(/\r?\n/).find((line) => line.startsWith("ADMIN_SESSION_SECRET="))?.slice("ADMIN_SESSION_SECRET=".length).trim().replace(/^["']|["']$/g, "");
  const secret = process.env.ADMIN_SESSION_SECRET || configured || "dev-only-insecure-admin-session-secret-change-me";
  const payload = "admin:frontend-mock";
  const marker = `${payload}:${crypto.createHmac("sha256", secret).update(payload).digest("hex")}`;
  await page.context().addCookies([{ name: "mb_admin_session", value: marker, url: baseURL }]);
}
