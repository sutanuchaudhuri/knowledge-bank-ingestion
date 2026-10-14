// API client for mathbank-exam-agent (requirements/64). Token is stored in
// localStorage (either a real Cognito access token or an `anon.<student_id>`
// session token — both are just opaque bearer values to this client).
const BASE_URL = import.meta.env.VITE_EXAM_AGENT_BASE_URL || "http://localhost:8030";
const TOKEN_KEY = "mathbank_exam_token";
const STUDENT_KEY = "mathbank_exam_student_id";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStudentId() {
  return localStorage.getItem(STUDENT_KEY);
}

export function setSession(token, studentId) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(STUDENT_KEY, studentId);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(STUDENT_KEY);
}

export function isLoggedIn() {
  return Boolean(getToken());
}

class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request(method, path, { json, params, auth = true } = {}) {
  const url = new URL(BASE_URL + path);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, value);
    }
  }
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(url, {
    method,
    headers,
    body: json !== undefined ? JSON.stringify(json) : undefined,
  });
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    if (auth && response.status === 401) {
      clearSession();
      window.dispatchEvent(new Event("mathbank:auth-expired"));
    }
    const detail = body && body.detail;
    const code = (detail && detail.code) || "UNKNOWN";
    const message = (detail && detail.message) || (typeof detail === "string" ? detail : response.statusText);
    throw new ApiError(response.status, code, message);
  }
  return body;
}

export const api = {
  // auth
  signup: (payload) => request("POST", "/v1/auth/signup", { json: payload, auth: false }),
  login: (payload) => request("POST", "/v1/auth/login", { json: payload, auth: false }),
  anonymous: () => request("POST", "/v1/auth/anonymous", { auth: false }),
  forgotPassword: (payload) => request("POST", "/v1/auth/forgot-password", { json: payload, auth: false }),
  confirmForgotPassword: (payload) =>
    request("POST", "/v1/auth/confirm-forgot-password", { json: payload, auth: false }),
  me: () => request("GET", "/v1/auth/me"),

  // papers
  startPaper: (nlRequest, examMode = true) =>
    request("POST", "/v1/exam-papers", { json: { nl_request: nlRequest, exam_mode: examMode } }),
  runPaperGeneration: (quizId, nlRequest) =>
    request("POST", `/v1/exam-papers/${quizId}/run`, { json: { nl_request: nlRequest } }),
  generationProgress: (quizId, sinceOrdinal = 0) =>
    request("GET", `/v1/exam-papers/${quizId}/generation-progress`, { params: { since_ordinal: sinceOrdinal } }),
  myPapers: () => request("GET", "/v1/exam-papers/mine"),
  getPaper: (quizId) => request("GET", `/v1/exam-papers/${quizId}`),
  saveExamProgress: (quizId, payload) =>
    request("PUT", `/v1/exam-papers/${quizId}/progress`, { json: payload }),
  logEvent: (quizId, questionId, payload) =>
    request("POST", `/v1/exam-papers/${quizId}/questions/${questionId}/events`, { json: payload }),
  getEvents: (quizId) => request("GET", `/v1/exam-papers/${quizId}/events`),
  respond: (quizId, questionId, payload) =>
    request("POST", `/v1/exam-papers/${quizId}/questions/${questionId}/respond`, { json: payload }),
  submitExam: (quizId) => request("POST", `/v1/exam-papers/${quizId}/submit`),
  review: (quizId) => request("GET", `/v1/exam-papers/${quizId}/review`),
  diagnose: (quizId) => request("POST", `/v1/exam-papers/${quizId}/diagnosis`),
  getDiagnosis: (quizId) => request("GET", `/v1/exam-papers/${quizId}/diagnosis`),
};

export { ApiError };
