"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye, EyeOff, Workflow } from "lucide-react";

import { useAuth } from "@/hooks/use-auth";

export function LoginForm() {
  const router = useRouter();

  const { login, status, error } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setSubmitting(true);

    try {
      await login(username.trim(), password);

      router.replace("/dashboard");
      router.refresh();
    } catch {
      // The AuthProvider exposes the error to the form.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-md">
      <div className="mb-9 flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#294b76] text-white">
          <Workflow size={24} strokeWidth={1.8} />
        </div>

        <div>
          <p className="text-base font-semibold text-[#263750]">
            Software Triage
          </p>

          <p className="mt-0.5 text-[10px] tracking-[0.17em] text-slate-400 uppercase">
            Team workspace
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-[#e9edf3] bg-white p-7 shadow-[0_8px_35px_rgba(30,50,80,0.04)] sm:p-9">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.16em] text-[#6687b5] uppercase">
            Staff access
          </p>

          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#263750]">
            Welcome back
          </h1>

          <p className="mt-2 text-sm leading-6 text-slate-500">
            Sign in to access your triage workspace.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <div>
            <label
              htmlFor="username"
              className="mb-2 block text-xs font-medium text-[#34465f]"
            >
              Username
            </label>

            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Enter your username"
              className="h-12 w-full rounded-xl border border-[#e2e8f0] bg-[#fafbfd] px-4 text-sm text-[#263750] outline-none transition-colors placeholder:text-slate-400 focus:border-[#829cbe] focus:bg-white"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-2 block text-xs font-medium text-[#34465f]"
            >
              Password
            </label>

            <div className="relative">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                className="h-12 w-full rounded-xl border border-[#e2e8f0] bg-[#fafbfd] px-4 pr-12 text-sm text-[#263750] outline-none transition-colors placeholder:text-slate-400 focus:border-[#829cbe] focus:bg-white"
              />

              <button
                type="button"
                aria-label={
                  showPassword ? "Hide password" : "Show password"
                }
                onClick={() => setShowPassword((value) => !value)}
                className="absolute top-1/2 right-3 -translate-y-1/2 rounded-md p-1 text-slate-400 hover:text-slate-700"
              >
                {showPassword ? (
                  <EyeOff size={17} />
                ) : (
                  <Eye size={17} />
                )}
              </button>
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-xs leading-5 text-red-700"
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !username.trim() || !password}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#294b76] text-sm font-medium text-white transition-colors hover:bg-[#203d62] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Signing in..." : "Sign in"}

            {!submitting && <ArrowRight size={16} />}
          </button>
        </form>

        <p className="mt-7 text-center text-[10px] leading-5 text-slate-400">
          Access is restricted to authorized staff accounts.
        </p>
      </div>
    </div>
  );
}