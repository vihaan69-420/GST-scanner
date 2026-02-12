"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const GOOGLE_ERROR_MESSAGES: Record<string, string> = {
  config: "Google sign-in is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
  missing_code: "Google did not return a code. Try again.",
  token_exchange: "Google sign-in failed. Try again.",
  no_token: "Google did not return a token. Try again.",
  userinfo: "Could not load your Google profile. Try again.",
  no_email: "Your Google account has no email. Use email/password instead.",
  access_denied: "You denied access. Try again if you want to sign up.",
};

function validatePassword(password: string): string | null {
  if (password.length < 8) return "Password must be at least 8 characters";
  if (!/[A-Z]/.test(password)) return "Password must include at least one uppercase letter";
  if (!/[0-9]/.test(password)) return "Password must include at least one number";
  return null;
}

function RegisterContent() {
  const searchParams = useSearchParams();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<{
    name?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [step, setStep] = useState<"form" | "otp">("form");
  const [otp, setOtp] = useState("");
  const [otpError, setOtpError] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    const err = searchParams.get("error");
    if (err) setGoogleError(GOOGLE_ERROR_MESSAGES[err] ?? "Google sign-up failed. Try again.");
  }, [searchParams]);

  useEffect(() => {
    if (step !== "otp" || resendCooldown <= 0) return;
    const id = setInterval(() => setResendCooldown((c) => (c <= 1 ? 0 : c - 1)), 1000);
    return () => clearInterval(id);
  }, [step, resendCooldown]);

  const validate = () => {
    const next: typeof errors = {};
    if (!name.trim()) next.name = "Name is required";
    if (!email.trim()) next.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) next.email = "Enter a valid email";
    const pwdErr = validatePassword(password);
    if (pwdErr) next.password = pwdErr;
    if (password && !confirmPassword) next.confirmPassword = "Confirm your password";
    else if (password !== confirmPassword) next.confirmPassword = "Passwords do not match";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const sendOtp = async () => {
    const res = await fetch("/api/auth/send-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
      }),
    });
    const data = (await res.json()) as { error?: string };
    if (!res.ok) throw new Error(data.error ?? "Failed to send code");
    return data;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);
    if (!validate()) return;
    setLoading(true);
    try {
      await sendOtp();
      setStep("otp");
      setOtp("");
      setOtpError(null);
      setResendCooldown(60);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Failed to send verification code. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setOtpError(null);
    const code = otp.trim();
    if (!code || code.length !== 6) {
      setOtpError("Enter the 6-digit code");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/auth/verify-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), otp: code }),
      });
      let data: { error?: string };
      try {
        data = (await res.json()) as { error?: string };
      } catch {
        setOtpError("Invalid response from server. Try again.");
        setLoading(false);
        return;
      }
      if (!res.ok) {
        setOtpError(data.error ?? "Verification failed.");
        setLoading(false);
        return;
      }
      window.location.href = "/login?registered=1";
    } catch (err) {
      const isNetworkError =
        err instanceof TypeError ||
        (err instanceof Error && (
          err.message.includes("fetch") ||
          err.message.includes("Failed to fetch") ||
          err.message.includes("could not be resolved") ||
          err.message.includes("NetworkError")
        ));
      setOtpError(
        isNetworkError
          ? "Unable to reach the server. Check your connection and that the app is running, then try again."
          : "Verification failed. Try again."
      );
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (resendCooldown > 0) return;
    setOtpError(null);
    try {
      await sendOtp();
      setResendCooldown(60);
    } catch (err) {
      setOtpError(err instanceof Error ? err.message : "Failed to resend code.");
    }
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
            Create account
          </h1>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Start free. No credit card required.
          </p>
          {apiError && (
            <p className="mt-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-600 dark:text-red-400">
              {apiError}
            </p>
          )}
          {googleError && (
            <p className="mt-4 rounded-lg bg-amber-500/10 px-4 py-2 text-sm text-amber-600 dark:text-amber-400">
              {googleError}
            </p>
          )}
          {step === "otp" ? (
            <div className="mt-8">
              <p className="text-sm font-medium text-[var(--foreground)]">Verify your email</p>
              <p className="mt-1 text-sm text-[var(--muted)]">
                We sent a 6-digit code to <strong>{email}</strong>
                Enter it below.
              </p>
              {otpError && (
                <p className="mt-2 text-sm text-red-500">{otpError}</p>
              )}
              <form onSubmit={handleVerifyOtp} className="mt-4 space-y-4">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  placeholder="000000"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  className="block w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-center text-lg tracking-[0.5em] text-[var(--foreground)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-full bg-[var(--primary)] py-3 text-sm font-semibold text-[var(--primary-foreground)] transition-opacity hover:opacity-95 disabled:opacity-50"
                >
                  {loading ? "Verifying…" : "Verify and create account"}
                </button>
              </form>
              <p className="mt-3 text-center text-sm text-[var(--muted)]">
                Didn&apos;t receive the email? Check spam.
              </p>
              <p className="mt-1 text-center text-sm text-[var(--muted)]">
                In development, the code is also printed in the <strong>terminal where you ran <code>npm run dev</code></strong> — look for a line like <code>[OTP] … code for … : 123456</code> and enter that 6-digit number.
              </p>
              <p className="mt-1 text-center text-sm text-[var(--muted)]">
                {resendCooldown > 0 ? (
                  <>Resend code in {resendCooldown}s</>
                ) : (
                  <button
                    type="button"
                    onClick={handleResendOtp}
                    className="font-medium text-[var(--primary)] hover:underline"
                  >
                    Resend code
                  </button>
                )}
              </p>
              <button
                type="button"
                onClick={() => { setStep("form"); setOtpError(null); setOtp(""); }}
                className="mt-2 w-full text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                ← Back to form
              </button>
            </div>
          ) : (
          <form onSubmit={handleSubmit} className="mt-8 space-y-6">
            <div>
              <label
                htmlFor="register-name"
                className="block text-sm font-medium text-[var(--foreground)]"
              >
                Name
              </label>
              <input
                id="register-name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-2 block w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-[var(--foreground)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                placeholder="Your name"
              />
              {errors.name && (
                <p className="mt-1 text-sm text-red-500">{errors.name}</p>
              )}
            </div>
            <div>
              <label
                htmlFor="register-email"
                className="block text-sm font-medium text-[var(--foreground)]"
              >
                Email
              </label>
              <input
                id="register-email"
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
                htmlFor="register-password"
                className="block text-sm font-medium text-[var(--foreground)]"
              >
                Password
              </label>
              <div className="relative mt-2">
                <input
                  id="register-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 pr-10 text-[var(--foreground)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                  placeholder="Min. 8 characters, 1 uppercase, 1 number"
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
            <div>
              <label
                htmlFor="register-confirm-password"
                className="block text-sm font-medium text-[var(--foreground)]"
              >
                Confirm password
              </label>
              <div className="relative mt-2">
                <input
                  id="register-confirm-password"
                  type={showConfirmPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="block w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 pr-10 text-[var(--foreground)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                  placeholder="Re-enter password"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-[var(--muted)] hover:bg-[var(--background)] hover:text-[var(--foreground)]"
                  aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                >
                  {showConfirmPassword ? (
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
              {errors.confirmPassword && (
                <p className="mt-1 text-sm text-red-500">{errors.confirmPassword}</p>
              )}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-full bg-[var(--primary)] py-3 text-sm font-semibold text-[var(--primary-foreground)] transition-opacity hover:opacity-95 disabled:opacity-50"
            >
              {loading ? "Sending code…" : "Send verification code"}
            </button>
          </form>
          )}
          <div className="mt-6 flex flex-col gap-4">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[var(--glass-border)]" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-[var(--card)] px-2 text-[var(--muted)]">
                  Or sign up with
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
              Sign up with Google
            </a>
          </div>
          <p className="mt-8 text-center text-sm text-[var(--muted)]">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-medium text-[var(--primary)] hover:underline"
            >
              Log in
            </Link>
          </p>
        </motion.div>
      </main>
      <Footer />
    </>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center">Loading…</div>}>
      <RegisterContent />
    </Suspense>
  );
}
