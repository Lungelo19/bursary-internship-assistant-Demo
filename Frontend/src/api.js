const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

async function handleResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function searchBursaries(course, includeExpired = false) {
  const params = new URLSearchParams({
    course,
    include_expired: includeExpired,
  });
  const res = await fetch(`${API_BASE}/bursaries?${params.toString()}`);
  return handleResponse(res);
}

export async function getBursaryDetail(id) {
  const res = await fetch(`${API_BASE}/bursaries/${id}`);
  return handleResponse(res);
}

export async function getFields() {
  const res = await fetch(`${API_BASE}/fields`);
  return handleResponse(res);
}

export async function sendChatMessage(course, message, sessionId) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ course, message, session_id: sessionId }),
  });
  return handleResponse(res);
}