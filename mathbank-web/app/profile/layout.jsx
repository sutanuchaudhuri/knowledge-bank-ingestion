import { redirect } from "next/navigation";
import { getStudentToken } from "../../lib/session.js";

export default async function ProfileLayout({ children }) {
  const token = await getStudentToken();
  if (!token) redirect("/login");
  return children;
}
