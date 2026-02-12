"use client";

import { useRouter } from "next/navigation";
import { useRef, useEffect, useState } from "react";
import Sidebar from "./Sidebar";
import ContextPanel from "./ContextPanel";
import { useAuth } from "@/context/AuthContext";
import { useAppStore } from "@/store/appStore";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { session, logout } = useAuth();
  const router = useRouter();
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    setDropdownOpen(false);
    logout();
    router.push("/login");
  };

  return (
    <div className="flex h-screen bg-[var(--background)]">
      <Sidebar />
      <div className="relative flex flex-1 flex-col overflow-hidden">
        <header className="relative z-30 flex h-14 shrink-0 items-center justify-between border-b border-[var(--glass-border)] bg-[var(--card)]/95 px-4 shadow-sm backdrop-blur-sm">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-2.5 text-[var(--muted)] hover:bg-[var(--background)] hover:text-[var(--foreground)] transition lg:hidden"
            aria-label="Open menu"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="ml-2 hidden text-sm font-medium text-[var(--foreground)] lg:block">Chat</span>
          <div className="ml-auto" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setDropdownOpen((o) => !o)}
                className="flex items-center gap-2 rounded-xl border border-[var(--glass-border)] bg-[var(--background)]/80 px-3 py-2 text-sm text-[var(--foreground)] transition hover:border-[var(--primary)]/20 hover:bg-[var(--background)]"
                aria-expanded={dropdownOpen}
                aria-haspopup="true"
                aria-label="Account menu"
              >
                <span className="max-w-[160px] truncate sm:max-w-[220px]">{session?.email ?? ""}</span>
                <svg
                  className={`h-4 w-4 shrink-0 text-[var(--muted)] transition ${dropdownOpen ? "rotate-180" : ""}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            {dropdownOpen && (
              <div className="absolute right-0 top-full z-[100] mt-2 min-w-[180px] rounded-xl border border-[var(--glass-border)] bg-[var(--card)] py-1.5 shadow-xl">
                <div className="border-b border-[var(--glass-border)] px-4 py-2">
                  <p className="truncate text-xs font-medium text-[var(--muted)]">Signed in as</p>
                  <p className="truncate text-sm text-[var(--foreground)]">{session?.email}</p>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full px-4 py-2.5 text-left text-sm font-medium text-[var(--foreground)] hover:bg-[var(--background)] transition"
                >
                  Log out
                </button>
              </div>
            )}
          </div>
        </header>
        <main className="relative flex flex-1 overflow-hidden bg-gradient-to-b from-[var(--background)] to-[var(--background)]/80">
          {children}
          <ContextPanel />
        </main>
      </div>
    </div>
  );
}
