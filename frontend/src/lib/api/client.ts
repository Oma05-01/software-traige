import type { CsrfResponse } from "@/lib/types/auth";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(
    status: number,
    message: string,
    data?: unknown
  ) {
    super(message);

    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string) {
  csrfToken = token;
}

export async function refreshCsrfToken(): Promise<string> {
  const response = await fetch("/api/auth/csrf/", {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
  });

  const data = (await response.json()) as CsrfResponse;

  if (!response.ok) {
    throw new ApiError(
      response.status,
      "Unable to initialize CSRF protection.",
      data
    );
  }

  csrfToken = data.csrfToken;

  return csrfToken;
}

function isUnsafeMethod(method: string) {
  return !["GET", "HEAD", "OPTIONS", "TRACE"].includes(
    method.toUpperCase()
  );
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();

  const headers = new Headers(options.headers);

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (isUnsafeMethod(method)) {
    if (!csrfToken) {
      await refreshCsrfToken();
    }

    headers.set("X-CSRFToken", csrfToken!);
  }

  const response = await fetch(`/api${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  const responseText = await response.text();

  let data: unknown = null;

  if (responseText) {
    try {
      data = JSON.parse(responseText);
    } catch {
      data = responseText;
    }
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;

    if (typeof data === "object" && data !== null) {
      const payload = data as Record<string, unknown>;

      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else {
        message = Object.entries(payload)
          .map(([key, value]) => {
            return `${key}: ${
              typeof value === "string"
                ? value
                : JSON.stringify(value)
            }`;
          })
          .join(" ");
      }
    } else if (typeof data === "string" && data.length < 300) {
      message = data;
    }

    throw new ApiError(response.status, message, data);
  }

  return data as T;
}