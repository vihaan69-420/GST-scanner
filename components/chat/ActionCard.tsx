"use client";

import { motion } from "framer-motion";

interface ActionCardProps {
  title: string;
  description?: string;
  onClick?: () => void;
  children?: React.ReactNode;
  /** For chat action blocks: primary/secondary buttons with clear separation from bubbles */
  actions?: { label: string; action: string }[];
  onActionClick?: (action: string) => void;
}

export default function ActionCard({
  title,
  description,
  onClick,
  children,
  actions,
  onActionClick,
}: ActionCardProps) {
  const hasActions = actions && actions.length > 0;
  const isClickable = !!onClick && !hasActions;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={isClickable ? onClick : undefined}
      className={`rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] p-5 shadow-[var(--shadow-soft)] transition hover:border-[var(--primary)]/20 hover:shadow-md ${
        isClickable ? "cursor-pointer" : ""
      }`}
    >
      <h3 className="font-semibold text-[var(--foreground)]">{title}</h3>
      {description && (
        <div className="mt-2 text-sm text-[var(--muted)] leading-relaxed whitespace-pre-line">
          {description}
        </div>
      )}
      {children}
      {hasActions && (
        <div className="mt-4 flex flex-wrap gap-3">
          {actions.map((b) => (
            <button
              key={b.action}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onActionClick?.(b.action);
              }}
              className="min-h-[44px] rounded-xl px-5 py-2.5 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/50"
              style={
                b.action === "cancel-order" || b.label === "Cancel"
                  ? {
                      backgroundColor: "var(--background)",
                      color: "var(--foreground)",
                      border: "1px solid var(--glass-border)",
                    }
                  : {
                      backgroundColor: "var(--primary)",
                      color: "var(--primary-foreground)",
                    }
              }
            >
              {b.label}
            </button>
          ))}
        </div>
      )}
    </motion.div>
  );
}
