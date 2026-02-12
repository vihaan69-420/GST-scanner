import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  getSessionCookieName,
  parseSessionCookie,
} from "@/lib/auth";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const cookieName = getSessionCookieName();
  const cookieValue = request.cookies.get(cookieName)?.value;
  const session = parseSessionCookie(cookieValue);

  if (pathname.startsWith("/dashboard")) {
    if (!session) {
      const login = new URL("/login", request.url);
      return NextResponse.redirect(login);
    }
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard", "/dashboard/:path*"],
};
