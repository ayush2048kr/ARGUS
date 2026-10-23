const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export function getAccessToken() {
  return sessionStorage.getItem("argus_access_token");
}

export function setAccessToken(token) {
  sessionStorage.setItem("argus_access_token", token);
}

export function clearAccessToken() {
  sessionStorage.removeItem("argus_access_token");
}

export async function apiRequest(path, options = {}) {
  const token = getAccessToken();
  const headers = new Headers(options.headers || {});

  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null
        ? payload.detail || payload.message
        : payload;

    if (response.status === 401) clearAccessToken();
    throw new Error(message || `Request failed (${response.status})`);
  }

  return payload;
}

export async function login(userId, password) {
  const result = await apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, password }),
  });

  if (!result.access_token) {
    throw new Error("The API did not return an access token.");
  }

  setAccessToken(result.access_token);
  return result;
}

export function getDashboardSummary() {
  return apiRequest("/dashboard/summary");
}

export function getAlerts() {
  return apiRequest("/alerts/");
}

export function getAlert(alertId) {
  return apiRequest(`/alerts/${encodeURIComponent(alertId)}`);
}

export function updateAlertStatus(alertId, status) {
  const query = new URLSearchParams({ new_status: status });

  return apiRequest(
    `/alerts/${encodeURIComponent(alertId)}/status?${query.toString()}`,
    { method: "PATCH" },
  );
}

export function getRisks() {
  return apiRequest("/risks/");
}

export function getRisksForUser(userId) {
  return apiRequest(`/risks/user/${encodeURIComponent(userId)}`);
}

export function getCurrentUser() {
  return apiRequest("/users/me");
}