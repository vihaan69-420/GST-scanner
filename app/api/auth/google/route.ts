import { NextResponse } from "next/server";

const GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth";

export async function GET(request: Request) {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  if (!clientId) {
    console.error("GOOGLE_CLIENT_ID is not set");
    return NextResponse.redirect(new URL("/login?error=config", request.url));
  }

  // Use GOOGLE_REDIRECT_URI if set (must match exactly what's in Google Cloud Console).
  // Otherwise: origin from request (e.g. http://localhost:3000 or https://yourdomain.com).
  const redirectUri =
    process.env.GOOGLE_REDIRECT_URI ||
    `${new URL(request.url).origin}/api/auth/google/callback`;

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid email profile",
    access_type: "offline",
    prompt: "consent",
  });

  const url = `${GOOGLE_AUTH_URL}?${params.toString()}`;
  return NextResponse.redirect(url);
}
