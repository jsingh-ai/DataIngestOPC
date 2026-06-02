const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export function getToken(): string | null {
  return localStorage.getItem("opc-platform-token");
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem("opc-platform-token", token);
  } else {
    localStorage.removeItem("opc-platform-token");
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function login(username: string, password: string): Promise<string> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!response.ok) {
    throw new Error("Invalid credentials");
  }
  const json = (await response.json()) as { access_token: string };
  return json.access_token;
}
