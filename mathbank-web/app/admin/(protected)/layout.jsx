import { redirect } from "next/navigation";
import { hasValidAdminSession } from "../../../lib/session.js";

// Route-group layout (URL stays /admin) — gates the admin UI behind the
// predefined-credential login at /admin/login until real OAuth lands.
export default async function ProtectedAdminLayout({ children }) {
  const authed = await hasValidAdminSession();
  if (!authed) redirect("/admin/login");
  return children;
}
