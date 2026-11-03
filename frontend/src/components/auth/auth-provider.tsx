"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  refreshCsrfToken,
} from "@/lib/api/client";

import {
  getCurrentUser,
  loginStaff,
  logoutStaff,
} from "@/lib/api/auth";

import type {
  AuthStatus,
  AuthUser,
} from "@/lib/types/auth";

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  error: string | null;
  login: (
    username: string,
    password: string
  ) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

export const AuthContext = createContext<
  AuthContextValue | undefined
>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);

  const [status, setStatus] = useState<AuthStatus>("loading");

  const [error, setError] = useState<string | null>(null);

  const refreshSession = useCallback(async () => {
  try {
    await refreshCsrfToken();

    const authenticatedUser = await getCurrentUser();

    setUser(authenticatedUser);
    setError(null);
    setStatus("authenticated");
  } catch (error) {
    setUser(null);

    if (error instanceof ApiError && error.status === 401) {
      setError(null);
      setStatus("unauthenticated");
      return;
    }

    setError(
      error instanceof Error
        ? error.message
        : "Unable to verify your session."
    );

    setStatus("error");
  }
}, []);

  const login = useCallback(
    async (username: string, password: string) => {
      setError(null);

      try {
        const authenticatedUser = await loginStaff(
          username,
          password
        );

        setUser(authenticatedUser);
        setStatus("authenticated");
      } catch (error) {
        setUser(null);

        setError(
          error instanceof Error
            ? error.message
            : "Login failed."
        );

        setStatus("unauthenticated");

        throw error;
      }
    },
    []
  );

  const logout = useCallback(async () => {
    await logoutStaff();

    setUser(null);
    setStatus("unauthenticated");
    setError(null);
    }, []);

  useEffect(() => {
  let cancelled = false;

  void Promise.resolve().then(() => {
    if (!cancelled) {
      void refreshSession();
    }
  });

  return () => {
    cancelled = true;
  };
}, [refreshSession]);

  return (
    <AuthContext.Provider
      value={{
        user,
        status,
        error,
        login,
        logout,
        refreshSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}