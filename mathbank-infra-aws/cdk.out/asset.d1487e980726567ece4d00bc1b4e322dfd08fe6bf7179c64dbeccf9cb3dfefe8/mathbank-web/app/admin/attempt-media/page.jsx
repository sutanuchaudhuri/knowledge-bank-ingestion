import { redirect } from "next/navigation";
import { hasValidAdminSession } from "../../../lib/session.js";
import AttemptMediaWorkspace from "../../_components/AttemptMediaWorkspace.jsx";

export default async function InstructorAttemptMediaPage() {
  if (!(await hasValidAdminSession())) redirect("/admin/login?next=%2Fadmin%2Fattempt-media");
  return <AttemptMediaWorkspace instructor />;
}
