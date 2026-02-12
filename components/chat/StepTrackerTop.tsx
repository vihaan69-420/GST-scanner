"use client";

import { motion } from "framer-motion";

const DEFAULT_STEPS = [
  "Select Action",
  "Upload File",
  "Process File",
  "Confirm / Preview",
  "Format Selection",
  "Generate Output",
  "Completed / Download",
];

interface StepTrackerTopProps {
  steps?: string[];
  currentIndex: number;
}

export default function StepTrackerTop({ steps = DEFAULT_STEPS, currentIndex }: StepTrackerTopProps) {
  return (
    <div className="shrink-0 border-b border-[var(--glass-border)] bg-[var(--card)]/80 px-4 py-3">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-center gap-1 sm:gap-2">
        {steps.map((label, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;
          return (
            <div key={i} className="flex items-center">
              <motion.div
                initial={false}
                animate={{
                  backgroundColor: active
                    ? "var(--primary)"
                    : done
                      ? "rgb(16, 185, 129)"
                      : "var(--background)",
                  color: active || done ? "#fff" : "var(--muted)",
                }}
                className="flex h-8 min-w-[2rem] items-center justify-center rounded-lg px-2 text-xs font-medium sm:min-w-[2.5rem]"
              >
                {done ? "✓" : i + 1}
              </motion.div>
              <span
                className={`ml-1 hidden max-w-[4rem] truncate text-xs sm:inline ${
                  active ? "font-medium text-[var(--primary)]" : "text-[var(--muted)]"
                }`}
              >
                {label}
              </span>
              {i < steps.length - 1 && (
                <span className="mx-1 text-[var(--muted)]/50">/</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
