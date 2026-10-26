import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { api } from "../src/api";
import { workflow } from "./fixtures";

type Call = { path: string; method: string; body?: Record<string, unknown> };
let calls: Call[];
let role: "admin" | "student";
let disabled: boolean;
const adminCaps = ["author", "manage_users", "preview"];
const session = () => ({
  actor: { actor_id: "sub-1", username: "admin@example.test", capabilities: role === "admin" ? adminCaps : ["preview"] },
  csrf_token: "csrf", auth_mode: "cognito", role, roles: ["admin", "student"],
});
const other = { username: "student@example.test", email: "student@example.test", email_verified: true, name: null,
  status: "CONFIRMED", created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-02T00:00:00Z" };

beforeEach(() => {
  calls = []; role = "admin"; disabled = false;
  window.location.hash = "";
  api.setSession(null);
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.replace("/v1/admin/socratic", "");
    const method = init?.method || "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) as Record<string, unknown> : undefined;
    calls.push({ path, method, body });
    let result: unknown;
    if (path === "/session") result = session();
    else if (path === "/session/role") { role = body!.role as "admin" | "student"; result = session(); }
    else if (path === "/session/password") return new Response(null, { status: 204 });
    else if (path === "/strategies") result = { strategies: [] };
    else if (path.startsWith("/workflows?")) result = { workflows: [workflow], has_more: false };
    else if (path.startsWith("/users?")) result = {
      users: [{ ...other, enabled: !disabled, groups: ["Students"] }], next_token: null,
      manageable_groups: ["Admins", "Students"], role_matrix: { admin: adminCaps, student: ["preview"] },
    };
    else if (path.startsWith("/users/student%40example.test")) {
      if (path.endsWith("/enabled")) disabled = !(body!.enabled as boolean);
      result = { ...other, enabled: !disabled, groups: ["Students"], mfa: [], events: [
        { action: "STUDIO_SIGN_IN_SUCCEEDED", actor_type: "ADMIN", actor_id: "sub-2", occurred_at: "2026-10-20T10:00:00Z", detail: { ip_prefix: "203.0.113.0/24" } },
      ], access: { last_sign_in_at: "2026-10-20T10:00:00Z", sign_ins_30d: 4, failed_sign_ins_30d: 1, role_switches_30d: 0, admin_actions_30d: 0, audit_enabled: true } };
    } else return new Response(JSON.stringify({ message: `unexpected ${path}` }), { status: 404 });
    return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
});

describe("roles and user management", () => {
  it("shows the active role and switching to Student narrows the Studio", async () => {
    const user = userEvent.setup();
    render(<App />);
    const rail = await screen.findByRole("navigation", { name: "Studio navigation" });
    expect(within(rail).getByLabelText("Users & access")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Active role/i })).toHaveTextContent("Admin");
    await user.click(screen.getByRole("button", { name: /Account: admin@example.test, Admin role/ }));
    const drawer = screen.getByRole("complementary", { name: "Your account" });
    await user.click(within(drawer).getByRole("button", { name: /Student/ }));
    await waitFor(() => expect(calls.some(call => call.path === "/session/role" && call.body?.role === "student")).toBe(true));
    await waitFor(() => expect(within(rail).queryByLabelText("Users & access")).not.toBeInTheDocument());
    expect(within(rail).queryByLabelText("Workflow designer")).not.toBeInTheDocument();
    expect(within(rail).getByLabelText("Student simulator")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Active role/i })).toHaveTextContent("Student");
    expect(screen.queryByText("New workflow")).not.toBeInTheDocument();
    // Student role never asks for authoring-only data.
    const afterSwitch = calls.slice(calls.findIndex(call => call.path === "/session/role"));
    expect(afterSwitch.some(call => call.path === "/strategies")).toBe(false);
  });

  it("lists users, opens a user with access history and disables after confirmation", async () => {
    const user = userEvent.setup();
    window.location.hash = "users";
    render(<App />);
    const row = await screen.findByRole("listitem");
    expect(row).toHaveTextContent("student@example.test");
    expect(row).toHaveTextContent("Students");
    await user.click(row);
    const drawer = await screen.findByRole("complementary", { name: "User" });
    expect(await within(drawer).findByText("Failed sign-ins")).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: /Admins/ })).toHaveAttribute("aria-pressed", "false");
    await user.click(within(drawer).getByRole("button", { name: "Disable account" }));
    await user.click(within(drawer).getByRole("button", { name: "Confirm: Disable account" }));
    await waitFor(() => expect(calls.some(call => call.path.endsWith("/enabled") && call.method === "PUT" && call.body?.enabled === false)).toBe(true));
    expect(await within(drawer).findByText("Disabled")).toBeInTheDocument();
  });

  it("searches users by prefix and adds a group", async () => {
    const user = userEvent.setup();
    window.location.hash = "users";
    render(<App />);
    await screen.findByRole("listitem");
    await user.type(screen.getByLabelText("Search users by email or username"), "stud{Enter}");
    await waitFor(() => expect(calls.some(call => call.path.includes("q=stud"))).toBe(true));
    await user.click(screen.getByRole("listitem"));
    const drawer = await screen.findByRole("complementary", { name: "User" });
    await user.click(await within(drawer).findByRole("button", { name: /Admins/ }));
    await waitFor(() => expect(calls.some(call => call.path.endsWith("/groups/Admins") && call.method === "PUT")).toBe(true));
  });

  it("changes your own password with confirmation matching", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /Account: admin@example.test/ }));
    const drawer = screen.getByRole("complementary", { name: "Your account" });
    await user.type(within(drawer).getByLabelText("Current password"), "old-password");
    await user.type(within(drawer).getByLabelText("New password"), "new-password-1");
    await user.type(within(drawer).getByLabelText("Confirm new password"), "different-pass");
    await user.click(within(drawer).getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("do not match");
    expect(calls.some(call => call.path === "/session/password")).toBe(false);
    await user.clear(within(drawer).getByLabelText("Confirm new password"));
    await user.type(within(drawer).getByLabelText("Confirm new password"), "new-password-1");
    await user.click(within(drawer).getByRole("button", { name: "Change password" }));
    await waitFor(() => expect(calls.find(call => call.path === "/session/password")?.body).toEqual({
      current_password: "old-password", new_password: "new-password-1" }));
  });
});
