/**
 * Role-based auth constants and helpers.
 * Default admin credentials (hardcoded for now).
 */

export const ADMIN_EMAIL = "chrizelf@amdocs.com";
export const ADMIN_PASSWORD = "Admin@123";

export type Role = "user" | "admin";

export interface Session {
  email: string;
  role: Role;
}

const SESSION_COOKIE = "gst_session";
const COOKIE_MAX_AGE_DAYS = 1;

export function getRoleFromCredentials(email: string, password: string): Role {
  const emailMatch = email.trim().toLowerCase() === ADMIN_EMAIL;
  const passwordMatch =
    password.trim() === ADMIN_PASSWORD ||
    password.trim().toLowerCase() === ADMIN_PASSWORD.toLowerCase();
  if (emailMatch && passwordMatch) {
    return "admin";
  }
  return "user";
}

export function getSessionCookieName(): string {
  return SESSION_COOKIE;
}

/** Serialize session for cookie (client or server). */
export function serializeSession(session: Session): string {
  return encodeURIComponent(JSON.stringify(session));
}

/** Parse session from cookie value. Returns null if invalid. */
export function parseSessionCookie(cookieValue: string | undefined): Session | null {
  if (!cookieValue) return null;
  try {
    let decoded = cookieValue;
    try {
      decoded = decodeURIComponent(cookieValue);
    } catch {
      // already decoded
    }
    const parsed = JSON.parse(decoded) as Session;
    if (parsed?.email && (parsed.role === "admin" || parsed.role === "user")) {
      return parsed;
    }
  } catch {
    // ignore
  }
  return null;
}

/** Cookie string to set from client: path=/; max-age=... */
export function getSessionCookieAttributes(): string {
  const maxAge = COOKIE_MAX_AGE_DAYS * 24 * 60 * 60;
  return `path=/; max-age=${maxAge}; samesite=lax`;
}

/** Max age in seconds for server-set session cookie (e.g. OAuth callback). */
export function getSessionCookieMaxAgeSeconds(): number {
  return COOKIE_MAX_AGE_DAYS * 24 * 60 * 60;
}
