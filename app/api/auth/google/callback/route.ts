import { NextResponse } from "next/server";
import { getContent } from "@/lib/db";
import { ADMIN_EMAIL } from "@/lib/auth";
import {
  getSessionCookieName,
  serializeSession,
  getSessionCookieMaxAgeSeconds,
} from "@/lib/auth";
import type { Session, Role } from "@/lib/auth";

interface StoredAdmin {
  id: string;
  email: string;
  password: string;
  role: string;
}

function getRoleForEmail(email: string): Role {
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
  const isAdmin =
    admins.some((a) => a.email.toLowerCase() === email.toLowerCase()) ||
    email.toLowerCase() === ADMIN_EMAIL.toLowerCase();
  return isAdmin ? "admin" : "user";
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const error = searchParams.get("error");

  const origin = new URL(request.url).origin;
  const loginUrl = new URL("/login", origin);

  if (error) {
    loginUrl.searchParams.set("error", error);
    return NextResponse.redirect(loginUrl);
  }

  if (!code) {
    loginUrl.searchParams.set("error", "missing_code");
    return NextResponse.redirect(loginUrl);
  }

  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    console.error("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is not set");
    loginUrl.searchParams.set("error", "config");
    return NextResponse.redirect(loginUrl);
  }

  const redirectUri =
    process.env.GOOGLE_REDIRECT_URI ||
    `${origin}/api/auth/google/callback`;

  let accessToken: string;
  try {
    const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: "authorization_code",
      }),
    });

    if (!tokenRes.ok) {
      const err = await tokenRes.text();
      console.error("Google token exchange failed:", err);
      loginUrl.searchParams.set("error", "token_exchange");
      return NextResponse.redirect(loginUrl);
    }

    const tokenData = (await tokenRes.json()) as { access_token?: string };
    const token = tokenData.access_token;
    if (!token) {
      loginUrl.searchParams.set("error", "no_token");
      return NextResponse.redirect(loginUrl);
    }
    accessToken = token;
  } catch (e) {
    console.error("Google OAuth token request error:", e);
    loginUrl.searchParams.set("error", "token_exchange");
    return NextResponse.redirect(loginUrl);
  }

  let email: string;
  try {
    const userRes = await fetch(
      "https://www.googleapis.com/oauth2/v2/userinfo",
      {
        headers: { Authorization: `Bearer ${accessToken}` },
      }
    );
    if (!userRes.ok) {
      loginUrl.searchParams.set("error", "userinfo");
      return NextResponse.redirect(loginUrl);
    }
    const userData = (await userRes.json()) as { email?: string };
    email = (userData.email ?? "").trim().toLowerCase();
    if (!email) {
      loginUrl.searchParams.set("error", "no_email");
      return NextResponse.redirect(loginUrl);
    }
  } catch (e) {
    console.error("Google userinfo request error:", e);
    loginUrl.searchParams.set("error", "userinfo");
    return NextResponse.redirect(loginUrl);
  }

  const role = getRoleForEmail(email);
  const session: Session = { email, role };
  const path = role === "admin" ? "/admin/dashboard" : "/dashboard";
  const redirectTo = new URL(`/auth/redirect?to=${encodeURIComponent(path)}`, origin);

  const response = NextResponse.redirect(redirectTo);
  const cookieName = getSessionCookieName();
  const cookieValue = serializeSession(session);
  response.cookies.set(cookieName, cookieValue, {
    path: "/",
    maxAge: getSessionCookieMaxAgeSeconds(),
    sameSite: "lax",
    httpOnly: false,
  });

  return response;
}
