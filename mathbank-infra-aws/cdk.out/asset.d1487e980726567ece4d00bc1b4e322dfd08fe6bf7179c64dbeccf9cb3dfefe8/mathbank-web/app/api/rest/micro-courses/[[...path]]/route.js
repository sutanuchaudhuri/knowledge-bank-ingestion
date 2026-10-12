import { restAuthGet, restAuthPost, restGet, restRaw } from "../../../../../lib/restClient.js";
import { getStudentToken } from "../../../../../lib/session.js";

function errorResponse(error) {
  return Response.json(
    { error: error.message || "Micro-course request failed." },
    { status: error.status || 502 },
  );
}

function unauthorized() {
  return Response.json({ error: "Student login is required." }, { status: 401 });
}

export async function GET(request, context) {
  try {
    const { path = [] } = await context.params;
    const suffix = path.map(segment => encodeURIComponent(segment)).join("/");
    // Enrollment reads are student-scoped: the student's own in-progress position and
    // recorded quiz attempts, never another learner's. Everything else (catalog, a
    // published course, its public/private assets) stays anonymous/public.
    if (path[0] === "enrollments") {
      const token = await getStudentToken();
      if (!token) return unauthorized();
      return Response.json(await restAuthGet(`/v1/micro-courses/${suffix}`, token));
    }
    if (path.at(-1) === "content") {
      return await restRaw(`/v1/micro-courses${suffix ? `/${suffix}` : ""}`);
    }
    const query = Object.fromEntries(new URL(request.url).searchParams);
    return Response.json(await restGet(`/v1/micro-courses${suffix ? `/${suffix}` : ""}`, query));
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request, context) {
  try {
    const { path = [] } = await context.params;
    const suffix = path.map(segment => encodeURIComponent(segment)).join("/");
    // Every POST on this route is a student-authenticated enrollment action
    // (enroll / advance / record a quiz attempt); there is no anonymous write path.
    const token = await getStudentToken();
    if (!token) return unauthorized();
    const body = await request.json().catch(() => ({}));
    return Response.json(await restAuthPost(`/v1/micro-courses/${suffix}`, token, body));
  } catch (error) {
    return errorResponse(error);
  }
}
