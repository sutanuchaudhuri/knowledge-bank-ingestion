export const endpoint = "/api/rest/admin/micro-courses";

export async function request(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(body.error || body.detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}
