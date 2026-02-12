"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { fetchHistory } from "@/services/api";

export default function HistoryPage() {
  const [items, setItems] = useState<Awaited<ReturnType<typeof fetchHistory>>>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "invoice" | "order">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    fetchHistory(filter === "all" ? undefined : filter).then((data) => {
      setItems(data);
      setLoading(false);
    });
  }, [filter]);

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-4xl">
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-lg font-semibold text-[var(--foreground)]"
        >
          History
        </motion.h2>
        <div className="mt-4 flex gap-2">
          {(["all", "invoice", "order"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`rounded-full px-3 py-1.5 text-sm ${
                filter === f ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--card)] text-[var(--muted)]"
              }`}
            >
              {f === "all" ? "All" : f === "invoice" ? "Invoices" : "Orders"}
            </button>
          ))}
        </div>
        <div className="mt-4 overflow-hidden rounded-xl border border-[var(--glass-border)] bg-[var(--card)]">
          {loading ? (
            <div className="p-8 text-center text-[var(--muted)]">Loading…</div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--glass-border)] bg-[var(--background)]/50">
                  <th className="px-4 py-3 font-medium text-[var(--foreground)]">Type</th>
                  <th className="px-4 py-3 font-medium text-[var(--foreground)]">Reference</th>
                  <th className="px-4 py-3 font-medium text-[var(--foreground)]">Date</th>
                  <th className="px-4 py-3 font-medium text-[var(--foreground)]">Status</th>
                  <th className="px-4 py-3 font-medium text-[var(--foreground)]"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-[var(--glass-border)] last:border-b-0 hover:bg-[var(--background)]/30"
                  >
                    <td className="px-4 py-3 capitalize text-[var(--foreground)]">{row.type}</td>
                    <td className="px-4 py-3 text-[var(--foreground)]">{row.reference}</td>
                    <td className="px-4 py-3 text-[var(--muted)]">{row.date}</td>
                    <td className="px-4 py-3 text-[var(--muted)]">{row.status}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setExpandedId(expandedId === row.id ? null : row.id)}
                        className="text-[var(--primary)]"
                      >
                        {expandedId === row.id ? "Less" : "More"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
