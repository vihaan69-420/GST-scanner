import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getSessionCookieName, parseSessionCookie } from "@/lib/auth";

/** GET /api/auth/session — return current session from cookie (server-side). */
export async function GET() {
  const cookieStore = await cookies();
  const name = getSessionCookieName();
  const value = cookieStore.get(name)?.value;
  const session = parseSessionCookie(value);
  if (!session) {
    return NextResponse.json({ session: null });
  }
  return NextResponse.json({ session: { email: session.email, role: session.role } });
}
