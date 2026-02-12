"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { getUsageStats } from "@/services/mockApi";
import UpgradePlanModal from "@/components/modals/UpgradePlanModal";

const TABS = ["Subscription", "Profile", "Usage", "Preferences"] as const;

export default function SettingsPage() {
  const { session } = useAuth();
  const { theme, setTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>("Profile");
  const [usage, setUsage] = useState<Awaited<ReturnType<typeof getUsageStats>> | null>(null);
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);

  useEffect(() => {
    getUsageStats().then(setUsage);
  }, []);

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-2xl">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Settings</h2>
        <div className="mt-4 flex gap-2 border-b border-[var(--glass-border)]">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`border-b-2 px-3 py-2 text-sm font-medium transition ${
                activeTab === tab
                  ? "border-[var(--primary)] text-[var(--primary)]"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 rounded-xl border border-[var(--glass-border)] bg-[var(--card)] p-6 shadow-[var(--shadow-soft)]"
        >
          {activeTab === "Subscription" && (
            <>
              <h3 className="font-medium text-[var(--foreground)]">Subscription</h3>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Current plan: {usage?.tier ? String(usage.tier).charAt(0).toUpperCase() + String(usage.tier).slice(1) : "Starter"}
              </p>
              <p className="mt-1 text-sm text-[var(--muted)]">Renewal: —</p>
              <button
                type="button"
                onClick={() => setUpgradeModalOpen(true)}
                className="mt-4 rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] shadow-sm transition hover:opacity-90"
              >
                Upgrade plan
              </button>
            </>
          )}
          {activeTab === "Profile" && (
            <>
              <h3 className="font-medium text-[var(--foreground)]">Profile</h3>
              <p className="mt-2 text-sm text-[var(--muted)]">Email: {session?.email ?? "—"}</p>
            </>
          )}
          {activeTab === "Usage" && (
            <>
              <h3 className="font-medium text-[var(--foreground)]">Usage</h3>
              {usage && (
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Invoices: {usage.invoicesUsed} / {usage.invoicesLimit}
                </p>
              )}
              <p className="mt-1 text-sm text-[var(--muted)]">Orders: {usage?.ordersUsed ?? 0}</p>
            </>
          )}
          {activeTab === "Preferences" && (
            <>
              <h3 className="font-medium text-[var(--foreground)]">Preferences</h3>
              <div className="mt-4">
                <p className="text-sm text-[var(--muted)]">Theme</p>
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={() => setTheme("light")}
                    className={`rounded-xl border px-4 py-2 text-sm font-medium transition ${
                      theme === "light"
                        ? "border-[var(--primary)] bg-[var(--primary)]/15 text-[var(--primary)]"
                        : "border-[var(--glass-border)] bg-[var(--background)] text-[var(--muted)] hover:border-[var(--primary)]/30 hover:text-[var(--foreground)]"
                    }`}
                  >
                    Light Mode
                  </button>
                  <button
                    type="button"
                    onClick={() => setTheme("dark")}
                    className={`rounded-xl border px-4 py-2 text-sm font-medium transition ${
                      theme === "dark"
                        ? "border-[var(--primary)] bg-[var(--primary)]/15 text-[var(--primary)]"
                        : "border-[var(--glass-border)] bg-[var(--background)] text-[var(--muted)] hover:border-[var(--primary)]/30 hover:text-[var(--foreground)]"
                    }`}
                  >
                    Dark Mode
                  </button>
                </div>
              </div>
            </>
          )}
        </motion.div>
      </div>
      <UpgradePlanModal open={upgradeModalOpen} onClose={() => setUpgradeModalOpen(false)} />
    </div>
  );
}
