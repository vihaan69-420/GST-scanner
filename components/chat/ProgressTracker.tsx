"use client";

import { motion } from "framer-motion";
import type { ProgressStep } from "@/store/appStore";

interface ProgressTrackerProps {
  steps: ProgressStep[];
}

export default function ProgressTracker({ steps }: ProgressTrackerProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] p-4"
    >
      <div className="flex items-center justify-between gap-2">
        {steps.map((step, i) => (
          <div key={i} className="flex flex-1 flex-col items-center">
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium ${
                step.status === "done"
                  ? "bg-emerald-500 text-white"
                  : step.status === "active"
                    ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                    : "bg-[var(--background)] text-[var(--muted)]"
              }`}
            >
              {step.status === "done" ? "✓" : i + 1}
            </div>
            <p
              className={`mt-1 text-center text-xs ${
                step.status === "active" ? "font-medium text-[var(--foreground)]" : "text-[var(--muted)]"
              }`}
            >
              {step.label}
            </p>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
