import { restAdminGet, restAdminSend, restAdminUpload } from "../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../lib/session.js";

function errorResponse(error) {
  return Response.json(
    { error: error.message || "Micro-course request failed." },
    { status: error.status || 502 },
  );
}

async function upstreamPath(context) {
  const { path = [] } = await context.params;
  const suffix = path.map(segment => encodeURIComponent(segment)).join("/");
  return `/v1/admin/micro-courses${suffix ? `/${suffix}` : ""}`;
}

export async function GET(request, context) {
  if (!(await hasValidAdminSession())) {
    return Response.json({ error: "not authorized" }, { status: 401 });
  }
  try {
    const query = Object.fromEntries(new URL(request.url).searchParams);
    return Response.json(await restAdminGet(await upstreamPath(context), query));
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request, context) {
  if (!(await hasValidAdminSession())) {
    return Response.json({ error: "not authorized" }, { status: 401 });
  }
  try {
    const path = await upstreamPath(context);
    if (request.headers.get("content-type")?.includes("multipart/form-data")) {
      const form = await request.formData();
      const file = form.get("file");
      if (!file || typeof file.arrayBuffer !== "function" || !file.size) {
        return Response.json({ error: "Choose a non-empty asset file." }, { status: 400 });
      }
      if (file.size > 25 * 1024 * 1024) {
        return Response.json({ error: "The uploaded asset exceeds 25 MB." }, { status: 413 });
      }
      const metadata = {
        title: String(form.get("title") || file.name || "Course asset"),
        presentation_role: String(form.get("presentation_role") || "SUPPORT"),
        reviewed_by: String(form.get("reviewed_by") || ""),
        admin_confirmed: String(form.get("admin_confirmed") || "false"),
      };
      if (!metadata.reviewed_by || metadata.admin_confirmed !== "true") {
        return Response.json({ error: "Record the reviewer and confirm the asset review." }, { status: 422 });
      }
      const rightsNote = String(form.get("rights_note") || "");
      if (rightsNote) metadata.rights_note = rightsNote;
      const response = await restAdminUpload(
        path,
        new Uint8Array(await file.arrayBuffer()),
        file.type || "application/octet-stream",
        metadata,
      );
      return Response.json(response, { status: 201 });
    }
    const body = await request.json();
    return Response.json(
      await restAdminSend("POST", path, body),
      { status: 200 },
    );
  } catch (error) {
    return errorResponse(error);
  }
}
