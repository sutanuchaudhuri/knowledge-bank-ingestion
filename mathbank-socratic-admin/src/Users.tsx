import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, pathId } from "./api";
import type { AccessEvent, Role, Session, UserDetail, UserPage, UserSummary } from "./contracts";
import { actorName, roleLabels } from "./contracts";
import { Empty, Hero, Icon, IconButton, Pill, Segmented } from "./ui";

const when = (value: string | null) => value ? new Date(value).toLocaleString() : "—";
const actionLabels: Record<string, string> = {
  STUDIO_SIGN_IN_SUCCEEDED: "Signed in", STUDIO_SIGN_IN_FAILED: "Failed sign-in", STUDIO_SIGN_OUT: "Signed out",
  STUDIO_ROLE_SWITCHED: "Switched role", STUDIO_PASSWORD_CHANGED: "Changed password",
  ADMIN_PASSWORD_RESET: "Password reset by admin", ADMIN_GLOBAL_SIGN_OUT: "Signed out everywhere by admin",
  ADMIN_GROUP_ADDED: "Added to group", ADMIN_GROUP_REMOVED: "Removed from group",
  ADMIN_USER_DISABLED: "Disabled by admin", ADMIN_USER_ENABLED: "Enabled by admin",
};
function statusTone(user: UserSummary): "success" | "warning" | "neutral" {
  if (!user.enabled) return "warning";
  return user.status === "CONFIRMED" ? "success" : "warning";
}
const statusText = (user: UserSummary) => !user.enabled ? "Disabled" : user.status === "CONFIRMED" ? "Active"
  : user.status.replace(/_/g, " ").toLowerCase().replace(/^\w/, c => c.toUpperCase());

/** User management canvas: search the user pool and open a user in the drawer. */
export function Users({ selected, refresh, onOpen, onError, onGroups }: {
  selected: string | null; refresh: number; onOpen: (username: string) => void; onError: (error: unknown) => void;
  onGroups: (groups: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [tokens, setTokens] = useState<(string | null)[]>([null]);
  const [page, setPage] = useState<UserPage | null>(null);
  const [loading, setLoading] = useState(false);
  const token = tokens[tokens.length - 1];
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const params = new URLSearchParams({ limit: "25", ...(search ? { q: search } : {}), ...(token ? { next_token: token } : {}) });
    api.request<UserPage>(`/users?${params}`, { signal: controller.signal })
      .then(value => { setPage(value); onGroups(value.manageable_groups); })
      .catch(cause => { if (!controller.signal.aborted) onError(cause); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [search, token, refresh, onError, onGroups]);
  const submit = (event: FormEvent) => { event.preventDefault(); setTokens([null]); setSearch(query.trim()); };
  return <div className="sc-canvas-inner">
    <Hero kicker="Administration" title="Users & access" description="Search accounts, manage roles and secure access." />
    <form className="sc-search-box sc-search-wide" role="search" onSubmit={submit}>
      <Icon name="search" />
      <input aria-label="Search users by email or username" placeholder="Search by email or username…" value={query}
        onChange={event => setQuery(event.target.value)} />
    </form>
    {page && <details className="sc-more"><summary>What each role can do</summary>
      <div className="sc-stats">{Object.entries(page.role_matrix).map(([role, caps]) => <div key={role}>
        <span className="sc-sub">{roleLabels[role as Role] || role}</span>
        <div className="sc-chips">{caps.map(cap => <span key={cap} className="sc-chip-static">{cap.replace(/_/g, " ")}</span>)}</div>
      </div>)}</div>
      <p className="sc-tiny">Studio sign-in requires the admin group. Members of both groups can switch to Student to see the Studio with student access.</p>
    </details>}
    {loading && !page ? <p role="status" className="sc-sub">Loading users…</p>
      : !page?.users.length ? <Empty icon="people">{search ? "No users match this search." : "No users found."}</Empty>
        : <div className="sc-list" role="list" aria-label="Users">
          {page.users.map(user => <button type="button" role="listitem" key={user.username}
            className={`sc-list-row${selected === user.username ? " sc-active" : ""}`} onClick={() => onOpen(user.username)}>
            <span className="sc-avatar" aria-hidden="true">{(user.email || user.username).slice(0, 2).toUpperCase()}</span>
            <span className="sc-name"><strong>{user.email || user.username}</strong>
              <span className="sc-sub">Created {when(user.created_at)}</span></span>
            <span className="sc-chips">{user.groups.map(group => <span key={group} className="sc-chip-static">{group}</span>)}</span>
            <Pill tone={statusTone(user)}>{statusText(user)}</Pill>
          </button>)}
        </div>}
    <nav className="sc-row sc-pager" aria-label="Pagination">
      <IconButton icon="chevron-left" label="Previous page" disabled={loading || tokens.length === 1} onClick={() => setTokens(list => list.slice(0, -1))} />
      <span className="sc-tiny">Page {tokens.length}</span>
      <IconButton icon="chevron-right" label="Next page" disabled={loading || !page?.next_token} onClick={() => setTokens(list => [...list, page!.next_token])} />
    </nav>
  </div>;
}

/** Drawer body for one user: groups (roles), security actions and access history. */
export function UserPanel({ username, self, groups: manageable, disabled, onError, onChanged }: {
  username: string; self: boolean; groups: string[]; disabled: boolean;
  onError: (error: unknown) => void; onChanged: (message: string) => void;
}) {
  const [user, setUser] = useState<UserDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setUser(null);
    api.request<UserDetail>(`/users/${pathId(username)}`, { signal: controller.signal }).then(setUser)
      .catch(cause => { if (!controller.signal.aborted) onError(cause); });
    return () => controller.abort();
  }, [username, onError]);
  async function act(path: string, method: string, message: string, body?: unknown) {
    setBusy(true); setConfirm(null);
    try { setUser(await api.request<UserDetail>(`/users/${pathId(username)}${path}`, { method, body })); onChanged(message); }
    catch (cause) { onError(cause); } finally { setBusy(false); }
  }
  if (!user) return <p role="status" className="sc-sub">Loading user…</p>;
  const off = disabled || busy;
  const confirmable = (key: string, label: string, run: () => void, danger = false) => confirm === key
    ? <span className="sc-row"><button type="button" className={`sc-light${danger ? " sc-danger-text" : ""}`} disabled={off} onClick={run}>Confirm: {label}</button>
      <button type="button" className="sc-light" onClick={() => setConfirm(null)}>Cancel</button></span>
    : <button type="button" className={`sc-light${danger ? " sc-danger-text" : ""}`} disabled={off || self} onClick={() => setConfirm(key)}>{label}</button>;
  return <>
    <div className="sc-row sc-space"><strong>{user.email || user.username}</strong><Pill tone={statusTone(user)}>{statusText(user)}</Pill></div>
    <span className="sc-sub">{user.email_verified ? "Email verified" : "Email not verified"} · MFA {user.mfa.length ? user.mfa.join(", ") : "off"}{self ? " · This is you" : ""}</span>

    <div className="sc-section-title">Roles (groups)</div>
    <div className="sc-chips" role="group" aria-label="Groups">
      {manageable.map(group => {
        const member = user.groups.includes(group);
        return <button type="button" key={group} aria-pressed={member} className={`sc-chip${member ? " sc-active" : ""}`}
          disabled={off || (self && member && group === manageable[0])}
          onClick={() => void act(`/groups/${pathId(group)}`, member ? "DELETE" : "PUT", `${member ? "Removed from" : "Added to"} ${group}.`)}>
          <Icon name={member ? "check2" : "plus"} />{group}</button>;
      })}
    </div>

    <div className="sc-section-title">Access (last 30 days)</div>
    {user.access.audit_enabled ? <div className="sc-stats">
      <div><span className="sc-sub">Last sign-in</span><strong>{when(user.access.last_sign_in_at)}</strong></div>
      <div><span className="sc-sub">Sign-ins</span><strong>{user.access.sign_ins_30d}</strong></div>
      <div><span className="sc-sub">Failed sign-ins</span><strong>{user.access.failed_sign_ins_30d}</strong></div>
      <div><span className="sc-sub">Role switches</span><strong>{user.access.role_switches_30d}</strong></div>
    </div> : <p className="sc-tiny">Access history is recorded by the hosted Studio (not in this session).</p>}
    {user.events.length > 0 && <details className="sc-more"><summary>Recent activity ({user.events.length})</summary>
      <ul className="sc-trace">{user.events.map((event: AccessEvent, index) => <li key={index}>
        <strong>{actionLabels[event.action] || event.action}</strong>
        <span className="sc-sub"> · {when(event.occurred_at)}{typeof event.detail.role === "string" ? ` · ${event.detail.role}` : ""}
          {typeof event.detail.group === "string" ? ` · ${event.detail.group}` : ""}{typeof event.detail.ip_prefix === "string" ? ` · ${event.detail.ip_prefix}` : ""}</span>
      </li>)}</ul>
    </details>}

    <div className="sc-section-title">Security</div>
    {self ? <p className="sc-tiny">Use your account menu to change your own password. Admins can't reset, sign out or disable themselves here.</p> : <>
      <div className="sc-row">{confirmable("reset", "Reset password", () => void act("/password-reset", "POST", "Password reset. Cognito emailed a code to the user."))}
        {confirmable("signout", "Sign out everywhere", () => void act("/sign-out", "POST", "All sessions signed out."))}</div>
      <div className="sc-row">{user.enabled
        ? confirmable("disable", "Disable account", () => void act("/enabled", "PUT", "Account disabled.", { enabled: false }), true)
        : confirmable("enable", "Enable account", () => void act("/enabled", "PUT", "Account enabled.", { enabled: true }))}</div>
    </>}
  </>;
}

/** Account drawer: who you are, the active role (switchable) and self-service password change. */
export function AccountPanel({ session, disabled, onSwitch, onError, onChanged }: {
  session: Session; disabled: boolean; onSwitch: (role: Role) => void;
  onError: (error: unknown) => void; onChanged: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const roles = session.roles || ["admin"];
  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (data.get("new_password") !== data.get("confirm_password")) { onError(new Error("The new passwords do not match.")); return; }
    setBusy(true);
    try {
      await api.request<void>("/session/password", { method: "POST", body: {
        current_password: data.get("current_password"), new_password: data.get("new_password") } });
      form.reset(); onChanged("Password changed.");
    } catch (cause) { onError(cause); } finally { setBusy(false); }
  }
  return <>
    <div className="sc-row"><span className="sc-avatar" aria-hidden="true">{actorName(session.actor).slice(0, 2).toUpperCase()}</span>
      <span className="sc-name"><strong>{actorName(session.actor)}</strong><span className="sc-sub">{session.auth_mode === "local" ? "Local test session" : "Cognito account"}</span></span></div>
    <div className="sc-section-title">Role</div>
    {roles.length > 1
      ? <Segmented label="Active role" value={session.role || "admin"} onChange={role => { if (role !== session.role) onSwitch(role); }}
        options={roles.map(role => ({ value: role, label: roleLabels[role], icon: role === "admin" ? "shield-check" : "mortarboard" }))} />
      : <Pill tone="primary">{roleLabels[session.role || "admin"]}</Pill>}
    <p className="sc-tiny">{session.role === "student"
      ? "Student role: run the student simulator only. Editing and user management are switched off until you switch back."
      : "Admin role: design workflows, preview as a student and manage users."}</p>
    {session.auth_mode !== "local" && <>
      <div className="sc-section-title">Change password</div>
      <form className="sc-form" onSubmit={changePassword}>
        <label>Current password<input name="current_password" type="password" autoComplete="current-password" required disabled={disabled || busy} /></label>
        <label>New password<input name="new_password" type="password" autoComplete="new-password" minLength={8} required disabled={disabled || busy} /></label>
        <label>Confirm new password<input name="confirm_password" type="password" autoComplete="new-password" minLength={8} required disabled={disabled || busy} /></label>
        <button className="sc-primary" disabled={disabled || busy}>Change password</button>
      </form>
    </>}
  </>;
}
