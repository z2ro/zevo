import type { ApiErrorBody } from "../types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "/api";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Accept: "application/json", ...init.headers },
  });
  if (!response.ok) {
    let body: ApiErrorBody | undefined;
    try { body = await response.json() as ApiErrorBody; } catch { /* non-JSON upstream error */ }
    throw new ApiError(response.status, body?.error.code ?? "HTTP_ERROR", body?.error.message ?? `Request failed (${response.status})`, body?.error.details);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
