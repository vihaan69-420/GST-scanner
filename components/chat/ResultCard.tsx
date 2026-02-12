"use client";

import { motion } from "framer-motion";

interface ResultCardProps {
  title: string;
  fields: { label: string; value: string | number }[];
  status?: "valid" | "warning" | "error";
  onDownload?: () => void;
}

export default function ResultCard({ title, fields, status = "valid", onDownload }: ResultCardProps) {
  const statusColor =
    status === "valid" ? "text-emerald-600" : status === "warning" ? "text-amber-600" : "text-red-600";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] p-4 shadow-[var(--shadow-soft)]"
    >
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-[var(--foreground)]">{title}</h3>
        {status && <span className={`text-xs font-medium ${statusColor}`}>{status}</span>}
      </div>
      <dl className="mt-3 space-y-1">
        {fields.map(({ label, value }) => (
          <div key={label} className="flex justify-between text-sm">
            <dt className="text-[var(--muted)]">{label}</dt>
            <dd className="text-[var(--foreground)]">{value}</dd>
          </div>
        ))}
      </dl>
      {onDownload && (
        <button
          type="button"
          onClick={onDownload}
          className="mt-4 w-full rounded-full bg-[var(--primary)] py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          Download
        </button>
      )}
    </motion.div>
  );
}
