"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";
import { getRoleFromCredentials } from "@/lib/auth";
import { apiLogin, clearTokens } from "@/services/api";

const GOOGLE_ERROR_MESSAGES: Record<string, string> = {
  config: "Google sign-in is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
  missing_code: "Google did not return a code. Try again.",
  token_exchange: "Google sign-in failed. Try again.",
  no_token: "Google did not return a token. Try again.",
  userinfo: "Could not load your Google profile. Try again.",
  no_email: "Your Google account has no email. Use email/password instead.",
  access_denied: "You denied access. Try again if you want to sign in.",
};

function LoginContent() {
  const { setSession } = useAuth();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [loading, setLoading] = useState(false);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginSuccess, setLoginSuccess] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const err = searchParams.get("error");
    const registered = searchParams.get("registered");
    if (err) setGoogleError(GOOGLE_ERROR_MESSAGES[err] ?? "Google sign-in failed. Try again.");
    if (registered === "1") setLoginSuccess("Account created. Log in with your email and password.");
  }, [searchParams]);

  const validate = () => {
    const next: { email?: string; password?: string } = {};
    if (!email.trim()) next.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) next.email = "Enter a valid email";
    if (!password) next.password = "Password is required";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoginError(null);
    setLoading(true);
    const trimmedEmail = email.trim().toLowerCase();
    let role: "admin" | "user" | null = null;

    // Try FastAPI backend first (issues JWT tokens for API access)
    try {
      const tokens = await apiLogin(trimmedEmail, password);
      role = tokens.role === "admin" ? "admin" : "user";
    } catch {
      // FastAPI unavailable - fall back to Next.js local auth
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: trimmedEmail, password }),
        });
        const data = (await res.json()) as { role?: "admin" | "user"; error?: string };
        if (res.ok && data.role) {
          role = data.role === "admin" ? "admin" : "user";
        } else if (!res.ok && data.error) {
          setLoginError(data.error);
        }
      } catch {
        role = getRoleFromCredentials(trimmedEmail, password);
      }
    }

    setLoading(false);
    if (role === null) return;
    setSession(trimmedEmail, role);
    const path = role === "admin" ? "/admin/dashboard" : "/dashboard";
    window.location.href = `/auth/redirect?to=${encodeURIComponent(path)}`;
  };

  return (
    <>
      <Navbar />
      <main className="flex min-h-[calc(100vh-8rem)] flex-col items-center justify-center px-4 pb-16 pt-24">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] p-8 shadow-[var(--shadow-soft)]"
        >
          <h1 className="text-2xl font-semibold text-[var(--foreground)]">
            Log in
          </h1>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Enter your credentials or sign in with a provider.
          </p>
          {loginSuccess && (
            <p className="mt-4 rounded-lg bg-emerald-500/10 px-4 py-2 text-sm text-emerald-600 dark:text-emerald-400">
              {loginSuccess}
            </p>
          )}
          {loginError && (
            <p className="mt-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-600 dark:text-red-400">
              {loginError}
            </p>
          )}
          {googleError && (
            <p className="mt-4 rounded-lg bg-amber-500/10 px-4 py-2 text-sm text-amber-600 dark:text-amber-400">
              {googleError}
            </p>
          )}
          <form onSubmit={handleSubmit} className="mt-8 space-y-6">
            <div>
              <label
                htmlFor="login-email"
                className="block text-sm font-medium text-[var(--foreground)]"
              >
                Email
              </label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-2 block w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-[var(--foreground)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                placeholder="you@company.com"
              />
              {errors.email && (
                <p className="mt-1 text-sm text-red-500">{errors.email}</p>
              )}
            </div>
            <div>
              <label
                htmlFor="login-password"
                className="block text-sm font-medium text-[var(--foreground)]"
              >
                Password
              </label>
              <div className="relative mt-2">
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 pr-10 text-[var(--foreground)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-[var(--muted)] hover:bg-[var(--background)] hover:text-[var(--foreground)]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-sm text-red-500">{errors.password}</p>
              )}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-full bg-[var(--primary)] py-3 text-sm font-semibold text-[var(--primary-foreground)] transition-opacity hover:opacity-95 disabled:opacity-50"
            >
              {loading ? "Signing in…" : "Log in"}
            </button>
          </form>
          <div className="mt-6 flex flex-col gap-4">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[var(--glass-border)]" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-[var(--card)] px-2 text-[var(--muted)]">
                  Or continue with
                </span>
              </div>
            </div>
            <a
              href="/api/auth/google"
              className="flex items-center justify-center gap-2 rounded-xl border border-[var(--glass-border)] py-3 text-sm font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--background)]"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Sign in with Google
            </a>
          </div>
          <p className="mt-8 text-center text-sm text-[var(--muted)]">
            Don&apos;t have an account?{" "}
            <Link
              href="/register"
              className="font-medium text-[var(--primary)] hover:underline"
            >
              Register
            </Link>
          </p>
        </motion.div>
      </main>
      <Footer />
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center">Loading…</div>}>
      <LoginContent />
    </Suspense>
  );
}
