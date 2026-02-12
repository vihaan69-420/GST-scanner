"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { generateReport } from "@/services/api";
import WizardModal from "@/components/modals/WizardModal";
import ResultCard from "@/components/chat/ResultCard";

export default function ReportsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());
  const [type, setType] = useState("GSTR-1");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{ name: string; url: string } | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setProgress(0);
    const id = setInterval(() => setProgress((p) => Math.min(p + 10, 100)), 200);
    const res = await generateReport(month, year, type);
    clearInterval(id);
    setProgress(100);
    setResult(res);
    setLoading(false);
  };

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-2xl space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] p-4"
        >
          <h2 className="font-semibold text-[var(--foreground)]">Reports</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Generate GST reports by month and type.
          </p>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="mt-4 rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)]"
          >
            Generate report
          </button>
        </motion.div>
        {result && (
          <ResultCard
            title="Report ready"
            fields={[{ label: "File", value: result.name }]}
            onDownload={() => {}}
          />
        )}
      </div>

      <WizardModal open={modalOpen} onClose={() => setModalOpen(false)} title="Generate report">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)]">Month</label>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-[var(--glass-border)] bg-[var(--background)] px-3 py-2"
            >
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i} value={i + 1}>{i + 1}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)]">Year</label>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-[var(--glass-border)] bg-[var(--background)] px-3 py-2"
            >
              {[2024, 2023].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)]">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--glass-border)] bg-[var(--background)] px-3 py-2"
            >
              <option value="GSTR-1">GSTR-1</option>
              <option value="GSTR-3B">GSTR-3B</option>
            </select>
          </div>
          {loading && (
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--background)]">
              <motion.div
                className="h-full bg-[var(--primary)]"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.2 }}
              />
            </div>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="flex-1 rounded-full border border-[var(--glass-border)] py-2 text-sm"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={loading}
              className="flex-1 rounded-full bg-[var(--primary)] py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
            >
              Generate
            </button>
          </div>
        </div>
      </WizardModal>
    </div>
  );
}
