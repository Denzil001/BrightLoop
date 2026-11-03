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
    super(error.fields?.length
      ? error.fields.map(({ path, message }) => {
          const label = path.replace(/^(body|query|path)\./, "").replace(/_/g, " ");
          return label ? `${label}: ${message}` : message;
        }).join("; ")
      : error.message);
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
  options: RequestInit & { _retried?: boolean; responseType?: "json" | "blob" } = {}
): Promise<T> {
  let url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  // Table controls own URL sort state. Apply it only to the matching page's
  // collection GET, never to nested records, writes or unrelated form lookups.
  if (typeof window !== "undefined" && (options.method || "GET").toUpperCase() === "GET") {
    const page = window.location.pathname.match(/^\/(?:app|portal)\/([^/]+)$/)?.[1];
    if (page && endpoint.split("?")[0] === `/${page}`) {
      const source = new URLSearchParams(window.location.search); const target = new URL(url, window.location.origin);
      for (const key of ["sort", "descending"]) if (source.has(key) && !target.searchParams.has(key)) target.searchParams.set(key, source.get(key) || "");
      url = target.toString();
    }
  }

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // Inject CSRF token for mutating requests
  const method = (options.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && !headers.has("X-CSRF-Token")) {
    let csrf = getCsrfTokenFromCookie();
    if (!csrf && typeof window !== "undefined") {
      try {
        const csrfRes = await fetch(`${API_BASE_URL}/auth/csrf`, {
          credentials: "include",
        });
        if (csrfRes.ok) {
          const csrfData = await csrfRes.json();
          csrf = csrfData.csrf_token || getCsrfTokenFromCookie();
        }
      } catch {
        // Fallback
      }
    }
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
    // If request failed with 403 CSRF error on a mutating call, automatically refresh pre-auth CSRF once and retry
    if (response.status === 403 && typeof window !== "undefined" && !options._retried) {
      try {
        const errorData = await response.clone().json();
        if (errorData?.error?.message?.toLowerCase().includes("csrf")) {
          const csrfRes = await fetch(`${API_BASE_URL}/auth/csrf`, {
            credentials: "include",
          });
          if (csrfRes.ok) {
            const csrfData = await csrfRes.json();
            const freshCsrf = csrfData.csrf_token;
            if (freshCsrf) {
              const retryHeaders = new Headers(options.headers || {});
              retryHeaders.set("X-CSRF-Token", freshCsrf);
              return apiClient<T>(endpoint, {
                ...options,
                headers: retryHeaders,
                _retried: true,
              });
            }
          }
        }
      } catch {
        // Continue to normal error handling
      }
    }

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

  if (options.responseType === "blob") return (await response.blob()) as T;
  return response.json();
}

export async function downloadFile(endpoint: string, filename: string): Promise<void> {
  const blob = await apiClient<Blob>(endpoint, {responseType: "blob"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
