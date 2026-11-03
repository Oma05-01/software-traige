"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/use-auth";

interface StaffAuthGuardProps {
  children: ReactNode;
}

export function StaffAuthGuard({
  children,
}: StaffAuthGuardProps) {
  const router = useRouter();

  const { status, error, refreshSession } = useAuth();

  const isAuthenticated = status === "authenticated";

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  return (
    <>
      {/* Always keep the route in the render tree. */}
      <div className={isAuthenticated ? "block" : "hidden"}>
        {children}
      </div>

      {/* Display authentication state separately. */}
      {!isAuthenticated && (
        <div className="flex min-h-[calc(100vh-76px)] items-center justify-center px-6">
          <div className="w-full max-w-sm text-center">

            {status === "loading" && (
              <>
                <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-[#365a88]" />

                <p className="text-sm font-medium text-slate-700">
                  Verifying staff session...
                </p>
              </>
            )}

            {status === "unauthenticated" && (
              <p className="text-sm text-slate-500">
                Redirecting to login...
              </p>
            )}

            {status === "error" && (
              <>
                <p className="text-sm font-semibold text-slate-700">
                  Unable to verify your session.
                </p>

                <p className="mt-2 text-xs text-slate-500">
                  {error}
                </p>

                <button
                  type="button"
                  onClick={() => void refreshSession()}
                  className="mt-5 rounded-lg bg-[#294b76] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#203d61]"
                >
                  Try again
                </button>
              </>
            )}

          </div>
        </div>
      )}
    </>
  );
}