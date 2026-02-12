import { NextResponse } from "next/server";
import { getContent, setContent } from "@/lib/db";
import { generateOtp, sendEmailOtp, sendSmsOtp } from "@/lib/send-otp";

const PENDING_REG_KEY = "pending_registrations";
const PENDING_OTP_KEY = "pending_otps";
const USERS_KEY = "users";
const OTP_EXPIRY_MS = 10 * 60 * 1000; // 10 min

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

function getUsers(): { id: string; name: string; email: string; password: string }[] {
  const raw = getContent(USERS_KEY);
  if (!raw) return [];
  try {
    const a = JSON.parse(raw);
    return Array.isArray(a) ? a : [];
  } catch {
    return [];
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as {
      name?: string;
      email?: string;
      password?: string;
      phone?: string;
    };
    const name = (body.name ?? "").trim();
    const email = (body.email ?? "").trim().toLowerCase();
    const password = (body.password ?? "").trim();
    const phone = (body.phone ?? "").trim().replace(/\s/g, "");

    if (!name) {
      return NextResponse.json({ error: "Name is required" }, { status: 400 });
    }
    if (!email) {
      return NextResponse.json({ error: "Email is required" }, { status: 400 });
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return NextResponse.json({ error: "Enter a valid email" }, { status: 400 });
    }
    if (!password) {
      return NextResponse.json({ error: "Password is required" }, { status: 400 });
    }
    if (password.length < 8) {
      return NextResponse.json({ error: "Password must be at least 8 characters" }, { status: 400 });
    }
    if (!/[A-Z]/.test(password)) {
      return NextResponse.json({ error: "Password must include at least one uppercase letter" }, { status: 400 });
    }
    if (!/[0-9]/.test(password)) {
      return NextResponse.json({ error: "Password must include at least one number" }, { status: 400 });
    }

    const users = getUsers();
    if (users.some((u) => u.email.toLowerCase() === email)) {
      return NextResponse.json(
        { error: "An account with this email already exists" },
        { status: 409 }
      );
    }

    const otp = generateOtp();
    const expiresAt = Date.now() + OTP_EXPIRY_MS;

    const pendingReg = getPendingRegistrations();
    pendingReg[email] = { name, email, password, phone: phone || undefined, createdAt: Date.now() };
    setContent(PENDING_REG_KEY, JSON.stringify(pendingReg));

    const pendingOtps = getPendingOtps();
    pendingOtps[email] = { otp, expiresAt };
    setContent(PENDING_OTP_KEY, JSON.stringify(pendingOtps));

    const emailResult = await sendEmailOtp(email, otp);
    if (!emailResult.sent) {
      const isDev = process.env.NODE_ENV === "development";
      if (isDev) {
        console.log("[OTP] Email failed — use this code for", email, ":", otp);
        return NextResponse.json({ ok: true });
      }
      return NextResponse.json(
        {
          error:
            "Verification email could not be sent. If running locally, check the server terminal for the code.",
        },
        { status: 502 }
      );
    }

    if (phone) {
      await sendSmsOtp(phone, otp);
    }

    return NextResponse.json({ ok: true });
  } catch (e) {
    console.error("POST /api/auth/send-otp", e);
    return NextResponse.json({ error: "Failed to send code" }, { status: 500 });
  }
}
