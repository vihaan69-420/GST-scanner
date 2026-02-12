import { NextResponse } from "next/server";
import { getContent, setContent } from "@/lib/db";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const PENDING_REG_KEY = "pending_registrations";
const PENDING_OTP_KEY = "pending_otps";
const USERS_KEY = "users";

interface PendingRegistration {
  name: string;
  email: string;
  password: string;
  phone?: string;
  createdAt: number;
}

interface PendingOtp {
  otp: string;
  expiresAt: number;
}

function getPendingRegistrations(): Record<string, PendingRegistration> {
  const raw = getContent(PENDING_REG_KEY);
  if (!raw) return {};
  try {
    const o = JSON.parse(raw) as Record<string, PendingRegistration>;
    return typeof o === "object" && o !== null ? o : {};
  } catch {
    return {};
  }
}

function getPendingOtps(): Record<string, PendingOtp> {
  const raw = getContent(PENDING_OTP_KEY);
  if (!raw) return {};
  try {
    const o = JSON.parse(raw) as Record<string, PendingOtp>;
    return typeof o === "object" && o !== null ? o : {};
  } catch {
    return {};
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { email?: string; otp?: string };
    const email = (body.email ?? "").trim().toLowerCase();
    const otp = (body.otp ?? "").trim();

    if (!email) {
      return NextResponse.json({ error: "Email is required" }, { status: 400 });
    }
    if (!otp) {
      return NextResponse.json({ error: "Verification code is required" }, { status: 400 });
    }

    const pendingOtps = getPendingOtps();
    const record = pendingOtps[email];
    if (!record) {
      return NextResponse.json(
        { error: "No code found for this email. Request a new code." },
        { status: 400 }
      );
    }
    if (Date.now() > record.expiresAt) {
      delete pendingOtps[email];
      setContent(PENDING_OTP_KEY, JSON.stringify(pendingOtps));
      return NextResponse.json(
        { error: "Verification code expired. Request a new code." },
        { status: 400 }
      );
    }
    if (record.otp !== otp) {
      return NextResponse.json(
        { error: "Invalid verification code." },
        { status: 400 }
      );
    }

    const pendingReg = getPendingRegistrations();
    const reg = pendingReg[email];
    if (!reg) {
      delete pendingOtps[email];
      setContent(PENDING_OTP_KEY, JSON.stringify(pendingOtps));
      return NextResponse.json(
        { error: "Registration expired. Please sign up again." },
        { status: 400 }
      );
    }

    const usersRaw = getContent(USERS_KEY);
    let users: { id: string; name: string; email: string; password: string }[] = [];
    if (usersRaw) {
      try {
        const parsed = JSON.parse(usersRaw);
        if (Array.isArray(parsed)) users = parsed;
      } catch {
        // ignore
      }
    }
    const newUser = {
      id: String(Date.now()),
      name: reg.name,
      email: reg.email,
      password: reg.password,
    };
    users.push(newUser);
    setContent(USERS_KEY, JSON.stringify(users));

    // Also register on FastAPI backend (for JWT-based API access)
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    try {
      await fetch(`${apiUrl}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: reg.email,
          password: reg.password,
          full_name: reg.name,
        }),
      });
    } catch {
      // FastAPI registration is best-effort; user can still login later
      // and the FastAPI login will fail gracefully
    }

    delete pendingOtps[email];
    delete pendingReg[email];
    setContent(PENDING_OTP_KEY, JSON.stringify(pendingOtps));
    setContent(PENDING_REG_KEY, JSON.stringify(pendingReg));

    return NextResponse.json({ ok: true });
  } catch (e) {
    console.error("POST /api/auth/verify-otp", e);
    return NextResponse.json({ error: "Verification failed" }, { status: 500 });
  }
}
