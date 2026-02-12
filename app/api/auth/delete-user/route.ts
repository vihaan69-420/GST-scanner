import { NextResponse } from "next/server";
import { getContent, setContent } from "@/lib/db";

const USERS_KEY = "users";
const PENDING_OTP_KEY = "pending_otps";
const PENDING_REG_KEY = "pending_registrations";

/**
 * DELETE a user by email. For development/testing only — allows re-registering with the same email.
 * Only works when NODE_ENV=development. Also clears any pending OTP/registration for that email.
 */
export async function DELETE(request: Request) {
  if (process.env.NODE_ENV === "production") {
    return NextResponse.json({ error: "Not available in production" }, { status: 404 });
  }

  const url = new URL(request.url);
  const email = (url.searchParams.get("email") ?? "").trim().toLowerCase();
  if (!email) {
    return NextResponse.json({ error: "Query param email is required" }, { status: 400 });
  }

  const raw = getContent(USERS_KEY);
  let users: { id: string; name: string; email: string; password: string }[] = [];
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) users = parsed;
    } catch {
      return NextResponse.json({ error: "Failed to read users" }, { status: 500 });
    }
  }

  const before = users.length;
  users = users.filter((u) => u.email.toLowerCase() !== email);
  if (users.length === before) {
    return NextResponse.json({ error: "No user found with that email" }, { status: 404 });
  }

  setContent(USERS_KEY, JSON.stringify(users));

  // Clear pending OTP and registration for this email so signup is clean
  const otpRaw = getContent(PENDING_OTP_KEY);
  if (otpRaw) {
    try {
      const otps = JSON.parse(otpRaw) as Record<string, unknown>;
      if (typeof otps === "object" && otps !== null && email in otps) {
        delete otps[email];
        setContent(PENDING_OTP_KEY, JSON.stringify(otps));
      }
    } catch {
      // ignore
    }
  }
  const regRaw = getContent(PENDING_REG_KEY);
  if (regRaw) {
    try {
      const regs = JSON.parse(regRaw) as Record<string, unknown>;
      if (typeof regs === "object" && regs !== null && email in regs) {
        delete regs[email];
        setContent(PENDING_REG_KEY, JSON.stringify(regs));
      }
    } catch {
      // ignore
    }
  }

  return NextResponse.json({ ok: true, message: "User deleted. You can register again with this email." });
}
