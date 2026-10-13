// Bridges a verified Cognito identity to a mathbank-rest learner.student_profile row
// and a real mathbank-rest JWT (requirements/64's onboard/mint-session-token pattern,
// originally built for mathbank-exam-agent, reused here unchanged). Cognito replaces
// the password check and the login screen; mathbank-rest's own JWT/authorization stays
// the ongoing API session token, completely unchanged downstream.
import { restAdminGet, restAdminPost } from "./restClient.js";

/** Looks up (or, on first-ever login for this identity, creates) the student_id for a
 * Cognito sub, then mints a mathbank-rest JWT for it. Returns the same shape
 * /v1/learner/login already returns (access_token + profile fields), so every existing
 * caller of setStudentSession(result.access_token) keeps working unchanged. */
export async function resolveStudentSession({ cognitoSub, firstName, lastName, grade, email, phone }) {
  let student;
  try {
    student = await restAdminGet(`/v1/quiz-integration/students/by-cognito-sub/${encodeURIComponent(cognitoSub)}`);
  } catch (err) {
    if (err.status !== 404) throw err;
    student = await restAdminPost("/v1/quiz-integration/students/onboard", {
      cognito_sub: cognitoSub, first_name: firstName, last_name: lastName,
      grade: grade || null, email: email || null, phone: phone || null, is_anonymous: false,
    });
  }
  return restAdminPost(`/v1/quiz-integration/students/${student.student_id}/mint-session-token`, {});
}
