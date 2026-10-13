// Bridges a verified Cognito identity to a mathbank-rest learner.student_profile row
// and a real mathbank-rest JWT — identical bridge pattern to mathbank-web's
// lib/cognitoBridge.js (requirements/64's onboard/mint-session-token endpoints),
// adapted to this app's own rest()/authHeaders() calling convention (lib/server.js,
// lib/gateway.mjs) instead of mathbank-web's restClient.js helpers.
import { rest } from "./server.js";
import { authHeaders, systemActor } from "./gateway.mjs";

async function adminRest({ method, path, body }) {
  return rest({ method, path, body, headers: authHeaders(systemActor()) });
}

export async function resolveStudentSession({ cognitoSub, firstName, lastName, grade, email, phone }) {
  let student;
  try {
    student = await adminRest({
      method: "GET",
      path: `/v1/quiz-integration/students/by-cognito-sub/${encodeURIComponent(cognitoSub)}`,
    });
  } catch (err) {
    if (err.status !== 404) throw err;
    student = await adminRest({
      method: "POST", path: "/v1/quiz-integration/students/onboard",
      body: {
        cognito_sub: cognitoSub, first_name: firstName, last_name: lastName,
        grade: grade || null, email: email || null, phone: phone || null, is_anonymous: false,
      },
    });
  }
  return adminRest({ method: "POST", path: `/v1/quiz-integration/students/${student.student_id}/mint-session-token` });
}
