import { ApiError } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const TOKEN_STORAGE_KEY = "ccp_access_token";

export class ApiClientError extends Error {
  status: number;
  code?: string;
  detail: string;

  constructor(status: number, detail: string, code?: string) {
    super(detail);
    this.name = "ApiClientError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

export function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredAuthToken(token: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Ignore storage quota or access errors
  }
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, headers = {}, ...customConfig } = options;

  let url = `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const token = getStoredAuthToken();
  const requestHeaders = new Headers(headers);

  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  if (!requestHeaders.has("Content-Type") && !(customConfig.body instanceof FormData)) {
    requestHeaders.set("Content-Type", "application/json");
  }

  const config: RequestInit = {
    ...customConfig,
    headers: requestHeaders,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let detail = `Request failed with status ${response.status}`;
      let code: string | undefined;

      try {
        const errorData: ApiError = await response.json();
        if (errorData.detail) {
          detail = errorData.detail;
        }
        if (errorData.code) {
          code = errorData.code;
        }
      } catch {
        detail = response.statusText || detail;
      }

      throw new ApiClientError(response.status, detail, code);
    }

    if (response.status === 204) {
      return {} as T;
    }

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return await response.json();
    }

    return (await response.text()) as unknown as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    throw new ApiClientError(500, (error as Error).message || "Network error occurred");
  }
}

export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { method: "GET", ...options }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
      ...options,
    }),

  patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: "PATCH",
      body: body instanceof FormData ? body : JSON.stringify(body),
      ...options,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { method: "DELETE", ...options }),

  upload: <T>(
    endpoint: string,
    formData: FormData,
    options?: Omit<RequestOptions, "body">
  ) =>
    request<T>(endpoint, {
      method: "POST",
      body: formData,
      ...options,
    }),
};
