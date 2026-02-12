"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { Role, Session } from "@/lib/auth";
import {
  getSessionCookieName,
  getSessionCookieAttributes,
  parseSessionCookie,
  serializeSession,
} from "@/lib/auth";
import { clearTokens } from "@/services/api";

interface AuthContextValue {
  session: Session | null;
  setSession: (email: string, role: Role) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readSessionFromCookie(): Session | null {
  if (typeof document === "undefined") return null;
  const name = getSessionCookieName();
  const match = document.cookie.match(
    new RegExp("(?:^|; )" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "=([^;]*)")
  );
  return parseSessionCookie(match ? match[1] : undefined);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(null);

  useEffect(() => {
    const fromCookie = readSessionFromCookie();
    if (fromCookie?.email) {
      setSessionState(fromCookie);
      return;
    }
    // Sync from server (e.g. after OAuth redirect or when client cookie wasn't set yet)
    fetch("/api/auth/session")
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { session?: Session | null }) => {
        if (data?.session?.email) {
          setSessionState({ email: data.session.email, role: data.session.role });
        } else if (fromCookie) {
          setSessionState(fromCookie);
        }
      })
      .catch(() => {
        if (fromCookie) setSessionState(fromCookie);
      });
  }, []);

  const setSession = useCallback((email: string, role: Role) => {
    const s: Session = { email, role };
    setSessionState(s);
    const name = getSessionCookieName();
    document.cookie = `${name}=${serializeSession(s)}; ${getSessionCookieAttributes()}`;
  }, []);

  const logout = useCallback(() => {
    setSessionState(null);
    const name = getSessionCookieName();
    document.cookie = `${name}=; path=/; max-age=0`;
    // Clear FastAPI JWT tokens
    clearTokens();
  }, []);

  const value: AuthContextValue = { session, setSession, logout };

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
