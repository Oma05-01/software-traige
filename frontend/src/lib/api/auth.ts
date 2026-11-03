import { apiRequest, setCsrfToken } from "./client";

import type {
  AuthUser,
  LoginResponse,
  LogoutResponse,
  SessionResponse,
} from "@/lib/types/auth";

export async function loginStaff(
  username: string,
  password: string
): Promise<AuthUser> {
  const result = await apiRequest<LoginResponse>(
    "/auth/login/",
    {
      method: "POST",
      body: JSON.stringify({
        username,
        password,
      }),
    }
  );

  // Django rotates the CSRF token after login.
  setCsrfToken(result.csrfToken);

  return result.user;
}

export async function getCurrentUser(): Promise<AuthUser> {
  const result = await apiRequest<SessionResponse>(
    "/auth/me/"
  );

  return result.user;
}

export async function logoutStaff(): Promise<void> {
  const result = await apiRequest<LogoutResponse>(
    "/auth/logout/",
    {
      method: "POST",
    }
  );

  // Django generates a new CSRF token after logout.
  setCsrfToken(result.csrfToken);
}