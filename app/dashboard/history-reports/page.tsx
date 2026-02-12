"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { fetchHistory, generateReport, getUsageStats } from "@/services/api";
import { useAppStore } from "@/store/appStore";
import { TIER_PLANS } from "@/lib/tiers";
import WizardModal from "@/components/modals/WizardModal";
import UpgradePlanModal from "@/components/modals/UpgradePlanModal";

export default function HistoryReportsPage() {
  const [historyItems, setHistoryItems] = useState<Awaited<ReturnType<typeof fetchHistory>>>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "invoice" | "order">("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "Processed" | "Completed" | "Failed">("all");
  const [dateFilter, setDateFilter] = useState<"all" | "7d" | "30d">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());
  const [type, setType] = useState("GSTR-1");
  const [reportFormat, setReportFormat] = useState<"PDF" | "CSV">("PDF");
  const [reportLoading, setReportLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [reportResult, setReportResult] = useState<{ name: string; url: string; format: "PDF" | "CSV" } | null>(null);
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);

  const { usageStats, setUsageStats, userTier, setUserTier } = useAppStore();

  useEffect(() => {
    fetchHistory(filter === "all" ? undefined : filter).then((data) => {
      setHistoryItems(data);
      setHistoryLoading(false);
    });
  }, [filter]);

  const filteredItems = historyItems.filter((row) => {
    if (statusFilter !== "all" && row.status !== statusFilter) return false;
    if (dateFilter !== "all") {
      const rowDate = new Date(row.date).getTime();
      const now = Date.now();
      const cut = dateFilter === "7d" ? now - 7 * 24 * 60 * 60 * 1000 : now - 30 * 24 * 60 * 60 * 1000;
      if (rowDate < cut) return false;
    }
    return true;
  });

  useEffect(() => {
    getUsageStats().then((s) => {
      setUsageStats(s);
      setUserTier(s.tier);
    });
  }, [setUsageStats, setUserTier]);

  const handleGenerateReport = async () => {
    setReportLoading(true);
    setProgress(0);
    const id = setInterval(() => setProgress((p) => Math.min(p + 10, 100)), 200);
    const res = await generateReport(month, year, type);
    clearInterval(id);
    setProgress(100);
    setReportResult({ ...res, format: reportFormat });
    setReportLoading(false);
  };

  const tierPlan = TIER_PLANS.find((p) => p.id === userTier) ?? TIER_PLANS[1];
  const limitStr = usageStats?.invoicesLimit != null && usageStats.invoicesLimit < 0 ? "Unlimited" : String(usageStats?.invoicesLimit ?? tierPlan.invoiceLimit);

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-4xl space-y-8">
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-lg font-semibold text-[var(--foreground)]"
        >
          History & Reports
        </motion.h2>

        {/* View Usage Stats + View Reports */}
        <div className="grid gap-4 sm:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] p-4 shadow-[var(--shadow-soft)]"
          >
            <h3 className="font-semibold text-[var(--foreground)]">View Usage Stats</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Your current usage and plan limits.
            </p>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-[var(--muted)]">Invoices</dt>
                <dd className="font-medium text-[var(--foreground)]">
                  {usageStats?.invoicesUsed ?? 0} / {limitStr}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--muted)]">Orders</dt>
                <dd className="font-medium text-[var(--foreground)]">{usageStats?.ordersUsed ?? 0}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--muted)]">Plan</dt>
                <dd className="font-medium text-[var(--foreground)]">{tierPlan.name}</dd>
              </div>
            </dl>
            <button
              type="button"
              onClick={() => setUpgradeModalOpen(true)}
              className="mt-4 rounded-full bg-[var(--primary)]/15 px-4 py-2 text-sm font-medium text-[var(--primary)] hover:bg-[var(--primary)]/25"
            >
              Upgrade plan
            </button>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] p-4 shadow-[var(--shadow-soft)]"
          >
            <h3 className="font-semibold text-[var(--foreground)]">View Reports</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Generate GSTR-1 or GSTR-3B by month and year.
            </p>
            <button
              type="button"
              onClick={() => setReportModalOpen(true)}
              className="mt-4 rounded-full bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] shadow-sm transition hover:opacity-90"
            >
              Generate report
            </button>
          </motion.div>
        </div>

        {reportResult && (
          <div className="rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] p-4 shadow-[var(--shadow-soft)]">
            <h3 className="font-medium text-[var(--foreground)]">Report ready</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">{reportResult.name}</p>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={() => {}}
                className="rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] shadow-sm hover:opacity-90"
              >
                Download PDF
              </button>
              <button
                type="button"
                onClick={() => {}}
                className="rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-2 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--card)]"
              >
                Download CSV
              </button>
            </div>
          </div>
        )}

        {/* History table */}
        <section>
          <h3 className="mb-3 font-semibold text-[var(--foreground)]">Past orders & invoices</h3>
          <div className="space-y-4 rounded-xl border border-[var(--glass-border)] bg-[var(--card)] p-4">
            <div className="grid gap-2 sm:grid-cols-[100px_1fr]">
              <label htmlFor="filter-type" className="text-sm font-medium text-[var(--muted)]">
                Type
              </label>
              <select
                id="filter-type"
                value={filter}
                onChange={(e) => setFilter(e.target.value as "all" | "invoice" | "order")}
                className="rounded-lg border border-[var(--glass-border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:border-[var(--primary)]/50 focus:outline-none focus:ring-1 focus:ring-[var(--primary)]/30"
              >
                <option value="all">All</option>
                <option value="invoice">Invoices</option>
                <option value="order">Orders</option>
              </select>
            </div>
            <div className="grid gap-2 sm:grid-cols-[100px_1fr]">
              <label htmlFor="filter-date" className="text-sm font-medium text-[var(--muted)]">
                Date
              </label>
              <select
                id="filter-date"
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value as "all" | "7d" | "30d")}
                className="rounded-lg border border-[var(--glass-border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:border-[var(--primary)]/50 focus:outline-none focus:ring-1 focus:ring-[var(--primary)]/30"
              >
                <option value="all">All</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
              </select>
            </div>
            <div className="grid gap-2 sm:grid-cols-[100px_1fr]">
              <label htmlFor="filter-status" className="text-sm font-medium text-[var(--muted)]">
                Status
              </label>
              <select
                id="filter-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as "all" | "Processed" | "Completed" | "Failed")}
                className="rounded-lg border border-[var(--glass-border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:border-[var(--primary)]/50 focus:outline-none focus:ring-1 focus:ring-[var(--primary)]/30"
              >
                <option value="all">All</option>
                <option value="Processed">Processed</option>
                <option value="Completed">Completed</option>
                <option value="Failed">Failed</option>
              </select>
            </div>
          </div>
          <div className="mt-4 overflow-hidden rounded-xl border border-[var(--glass-border)] bg-[var(--card)]">
            {historyLoading ? (
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
                  {filteredItems.map((row) => (
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
                          className="text-[var(--primary)] hover:underline"
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
        </section>
      </div>

      <WizardModal open={reportModalOpen} onClose={() => setReportModalOpen(false)} title="Generate report">
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
              {[2025, 2024, 2023].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)]">Report type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--glass-border)] bg-[var(--background)] px-3 py-2"
            >
              <option value="GSTR-1">GSTR-1</option>
              <option value="GSTR-3B">GSTR-3B</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--foreground)]">Download format</label>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => setReportFormat("PDF")}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                  reportFormat === "PDF"
                    ? "border-[var(--primary)] bg-[var(--primary)]/15 text-[var(--primary)]"
                    : "border-[var(--glass-border)] bg-[var(--background)] text-[var(--muted)]"
                }`}
              >
                PDF
              </button>
              <button
                type="button"
                onClick={() => setReportFormat("CSV")}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                  reportFormat === "CSV"
                    ? "border-[var(--primary)] bg-[var(--primary)]/15 text-[var(--primary)]"
                    : "border-[var(--glass-border)] bg-[var(--background)] text-[var(--muted)]"
                }`}
              >
                CSV
              </button>
            </div>
          </div>
          {reportLoading && (
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
              onClick={() => setReportModalOpen(false)}
              className="flex-1 rounded-full border border-[var(--glass-border)] py-2 text-sm"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleGenerateReport}
              disabled={reportLoading}
              className="flex-1 rounded-full bg-[var(--primary)] py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50"
            >
              Generate
            </button>
          </div>
        </div>
      </WizardModal>
      <UpgradePlanModal open={upgradeModalOpen} onClose={() => setUpgradeModalOpen(false)} />
    </div>
  );
}
