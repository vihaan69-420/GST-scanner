import { NextResponse } from "next/server";
import { getContent } from "@/lib/db";
import { ADMIN_EMAIL, ADMIN_PASSWORD } from "@/lib/auth";

interface StoredAdmin {
  id: string;
  email: string;
  password: string;
  role: string;
}

/** Check credentials against stored admin users or fallback to seed. Returns role. */
export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { email?: string; password?: string };
    const email = (body.email ?? "").trim().toLowerCase();
    const password = (body.password ?? "").trim();
    if (!email || !password) {
      return NextResponse.json(
        { error: "Email and password required" },
        { status: 400 }
      );
    }

    const raw = getContent("admin_users");
    let admins: StoredAdmin[] = [];
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as StoredAdmin[];
        if (Array.isArray(parsed)) admins = parsed;
      } catch {
        // ignore
      }
    }

    const match =
      admins.find(
        (a) =>
          a.email.toLowerCase() === email &&
          (password === a.password || password.toLowerCase() === a.password.toLowerCase())
      ) ?? null;

    if (match) {
      return NextResponse.json({ role: "admin" as const, email: match.email });
    }

    if (email === ADMIN_EMAIL && (password === ADMIN_PASSWORD || password.toLowerCase() === ADMIN_PASSWORD.toLowerCase())) {
      return NextResponse.json({ role: "admin" as const, email });
    }

    const usersRaw = getContent("users");
    let users: { email: string; password: string }[] = [];
    if (usersRaw) {
      try {
        const parsed = JSON.parse(usersRaw) as { email: string; password: string }[];
        if (Array.isArray(parsed)) users = parsed;
      } catch {
        // ignore
      }
    }
    const userMatch = users.find(
      (u) =>
        u.email.toLowerCase() === email &&
        (password === u.password || password.toLowerCase() === u.password.toLowerCase())
    );
    if (userMatch) {
      return NextResponse.json({ role: "user" as const, email });
    }

    return NextResponse.json(
      { error: "Invalid email or password. Register first if you don't have an account." },
      { status: 401 }
    );
  } catch (e) {
    console.error("POST /api/auth/login", e);
    return NextResponse.json({ error: "Login failed" }, { status: 500 });
  }
}
