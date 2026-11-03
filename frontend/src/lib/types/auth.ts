export interface AuthUser {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
}

export interface CsrfResponse {
  csrfToken: string;
}

export interface LoginResponse {
  detail: string;
  user: AuthUser;
  csrfToken: string;
}

export interface SessionResponse {
  authenticated: boolean;
  user: AuthUser;
}

export interface LogoutResponse {
  detail: string;
  csrfToken: string;
}

export type AuthStatus =
  | "loading"
  | "authenticated"
  | "unauthenticated"
  | "error";