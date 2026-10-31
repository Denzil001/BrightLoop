export interface ApiErrorDetail {
  code: string;
  message: string;
  fields?: Array<{ path: string; message: string }>;
  request_id?: string;
}

export class ApiError extends Error {
  public code: string;
  public fields?: Array<{ path: string; message: string }>;
  public requestId?: string;
  public status: number;

  constructor(status: number, error: ApiErrorDetail) {
    super(error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = error.code || "UNKNOWN_ERROR";
    this.fields = error.fields;
    this.requestId = error.request_id;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

function getCsrfTokenFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith("brightloop_csrf="));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // Inject CSRF token for mutating requests if available
  const method = (options.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && !headers.has("X-CSRF-Token")) {
    const csrf = getCsrfTokenFromCookie();
    if (csrf) {
      headers.set("X-CSRF-Token", csrf);
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include", // For session cookies
  });

  if (!response.ok) {
    let errorDetail: ApiErrorDetail;
    try {
      const data = await response.json();
      errorDetail = data.error || {
        code: "HTTP_ERROR",
        message: data.message || data.detail || `Request failed with status ${response.status}`,
      };
    } catch {
      errorDetail = {
        code: "HTTP_ERROR",
        message: `HTTP error ${response.status}: ${response.statusText}`,
      };
    }
    throw new ApiError(response.status, errorDetail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}
