"use client";

import { useAppStore } from "@/store/appStore";
import { motion, AnimatePresence } from "framer-motion";

export default function ContextPanel() {
  const { contextPanelOpen, setContextPanelOpen, uploadedFiles, hasActiveSession, progressSteps, usageStats } =
    useAppStore();

  return (
    <>
      {!contextPanelOpen && (
        <button
          type="button"
          onClick={() => setContextPanelOpen(true)}
          className="absolute right-2 top-2 z-10 rounded-lg border border-[var(--glass-border)] bg-[var(--card)] px-3 py-2 text-xs font-medium text-[var(--muted)] shadow-sm hover:bg-[var(--background)] hover:text-[var(--foreground)]"
        >
          Open context
        </button>
      )}
      <AnimatePresence>
        {contextPanelOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="flex shrink-0 flex-col border-l border-[var(--glass-border)] bg-[var(--card)]/80 backdrop-blur-sm"
          >
            <div className="flex h-14 items-center justify-between border-b border-[var(--glass-border)] px-4">
              <span className="text-sm font-medium text-[var(--foreground)]">Context</span>
              <button
                type="button"
                onClick={() => setContextPanelOpen(false)}
                className="text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
              {hasActiveSession && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                    Session
                  </h3>
                  <p className="mt-1 text-sm text-[var(--foreground)]">Active</p>
                </section>
              )}
              {progressSteps.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                    Progress
                  </h3>
                  <ul className="mt-2 space-y-1">
                    {progressSteps.map((step, i) => (
                      <li
                        key={i}
                        className={`text-sm ${
                          step.status === "done"
                            ? "text-emerald-600"
                            : step.status === "active"
                              ? "text-[var(--primary)]"
                              : "text-[var(--muted)]"
                        }`}
                      >
                        {step.status === "done" && "✓ "}
                        {step.label}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {uploadedFiles.length > 0 && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                    Uploaded files
                  </h3>
                  <ul className="mt-2 space-y-1">
                    {uploadedFiles.map((f) => (
                      <li key={f.id} className="truncate text-sm text-[var(--foreground)]">
                        {f.name}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {usageStats && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
                    Usage
                  </h3>
                  <p className="mt-1 text-sm text-[var(--foreground)]">
                    Invoices: {usageStats.invoicesUsed} / {usageStats.invoicesLimit}
                  </p>
                  <p className="text-sm text-[var(--foreground)]">Orders: {usageStats.ordersUsed}</p>
                </section>
              )}
              {!hasActiveSession && progressSteps.length === 0 && uploadedFiles.length === 0 && !usageStats && (
                <p className="text-sm text-[var(--muted)]">No active session. Start an upload or report.</p>
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
