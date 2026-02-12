"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TIER_PLANS, formatPrice, type TierId } from "@/lib/tiers";
import { useAppStore } from "@/store/appStore";

interface UpgradePlanModalProps {
  open: boolean;
  onClose: () => void;
}

const CHECKOUT_FEATURES: { icon: string; text: string }[] = [
  { icon: "✓", text: "Cancel anytime" },
  { icon: "○", text: "We'll remind you before your trial ends" },
  { icon: "○", text: "Expanded messaging and uploads" },
  { icon: "○", text: "More image creation, faster loading" },
  { icon: "○", text: "Expanded deep research and agent mode" },
];

export default function UpgradePlanModal({ open, onClose }: UpgradePlanModalProps) {
  const [annual, setAnnual] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<TierId | null>(null);
  const userTier = useAppStore((s) => s.userTier);

  const paidPlans = TIER_PLANS.filter((p) => p.id !== "free");
  const selectedPlan = selectedPlanId ? TIER_PLANS.find((p) => p.id === selectedPlanId) : null;

  const handleClose = () => {
    setSelectedPlanId(null);
    onClose();
  };

  const handleBack = () => setSelectedPlanId(null);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4"
            aria-hidden
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby={selectedPlanId ? "checkout-title" : "upgrade-modal-title"}
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              onClick={(e) => e.stopPropagation()}
              className="z-50 flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-[var(--glass-border)] bg-[var(--card)] shadow-xl sm:flex-row"
            >
              {selectedPlanId && selectedPlan ? (
                /* Checkout-style view: left form, right plan summary */
                <>
                  <div className="flex-1 overflow-y-auto p-6 sm:p-8">
                    <button
                      type="button"
                      onClick={handleBack}
                      className="mb-4 flex items-center gap-2 text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
                    >
                      <span aria-hidden>←</span>
                      Back to plans
                    </button>
                    <h2 id="checkout-title" className="text-lg font-semibold text-[var(--foreground)]">
                      Start your free {selectedPlan.name} trial
                    </h2>
                    <div className="mt-6 space-y-6">
                      <section>
                        <h3 className="text-sm font-semibold text-[var(--foreground)]">Payment method</h3>
                        <div className="mt-3 space-y-3">
                          <input
                            type="text"
                            placeholder="Card number"
                            className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                            readOnly
                            aria-label="Card number"
                          />
                          <div className="grid grid-cols-2 gap-3">
                            <input
                              type="text"
                              placeholder="Expiration date"
                              className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted)]"
                              readOnly
                              aria-label="Expiration date"
                            />
                            <input
                              type="text"
                              placeholder="Security code"
                              className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted)]"
                              readOnly
                              aria-label="Security code"
                            />
                          </div>
                        </div>
                      </section>
                      <section>
                        <h3 className="text-sm font-semibold text-[var(--foreground)]">Billing address</h3>
                        <div className="mt-3 space-y-3">
                          <input
                            type="text"
                            placeholder="Full name"
                            className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted)]"
                            readOnly
                            aria-label="Full name"
                          />
                          <input
                            type="text"
                            placeholder="Country or region"
                            defaultValue="India"
                            className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted)]"
                            readOnly
                            aria-label="Country or region"
                          />
                          <input
                            type="text"
                            placeholder="Address"
                            className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-3 text-sm text-[var(--foreground)] placeholder:text-[var(--muted)]"
                            readOnly
                            aria-label="Address"
                          />
                          <label className="flex items-center gap-2 text-sm text-[var(--foreground)]">
                            <input type="checkbox" className="rounded border-[var(--glass-border)]" readOnly />
                            I&apos;m purchasing as business
                          </label>
                        </div>
                      </section>
                    </div>
                  </div>
                  <div className="w-full border-t border-[var(--glass-border)] bg-[var(--background)]/50 p-6 sm:w-96 sm:border-t-0 sm:border-l">
                    <h3 className="text-xl font-semibold text-[var(--foreground)]">{selectedPlan.name} plan</h3>
                    <p className="mt-1 text-sm font-medium text-[var(--muted)]">Top features</p>
                    <ul className="mt-3 space-y-2 text-sm text-[var(--foreground)]">
                      {CHECKOUT_FEATURES.map((f, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <span className="text-[var(--primary)]">{f.icon}</span>
                          {f.text}
                        </li>
                      ))}
                    </ul>
                    <div className="mt-6 space-y-2 border-t border-[var(--glass-border)] pt-4 text-sm">
                      <div className="flex justify-between text-[var(--muted)]">
                        <span>Monthly subscription</span>
                        <span>{formatPrice(selectedPlan.monthlyPrice)}</span>
                      </div>
                      <div className="flex justify-between text-[var(--muted)]">
                        <span>Promotion</span>
                        <span className="text-emerald-600 dark:text-emerald-400">-{formatPrice(selectedPlan.monthlyPrice)}</span>
                      </div>
                      <p className="text-xs text-[var(--muted)]">100% off for first month</p>
                      <div className="flex justify-between text-[var(--muted)]">
                        <span>GST (18%)</span>
                        <span>₹0.00</span>
                      </div>
                      <div className="flex justify-between border-t border-[var(--glass-border)] pt-2 font-semibold text-[var(--foreground)]">
                        <span>Due today</span>
                        <span>₹0.00</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleClose}
                      className="mt-6 w-full rounded-xl bg-[var(--foreground)] py-3 text-sm font-medium text-[var(--background)] hover:opacity-90"
                    >
                      Subscribe
                    </button>
                    <p className="mt-4 text-xs text-[var(--muted)] leading-relaxed">
                      {formatPrice(selectedPlan.monthlyPrice)} for 1 month free, then {formatPrice(selectedPlan.monthlyPrice)}/month. Renews monthly until cancelled. Cancel anytime in Settings before your trial ends to avoid charges. By subscribing, you agree to the Terms of Use and authorize GST Scanner to store and charge your payment method.
                    </p>
                  </div>
                </>
              ) : (
                /* Plan selection */
                <div className="w-full overflow-y-auto p-6">
                  <div className="flex items-center justify-between">
                    <h2 id="upgrade-modal-title" className="text-xl font-semibold text-[var(--foreground)]">
                      Upgrade your plan
                    </h2>
                    <button
                      type="button"
                      onClick={handleClose}
                      className="rounded-lg p-1.5 text-[var(--muted)] hover:bg-[var(--background)] hover:text-[var(--foreground)]"
                      aria-label="Close"
                    >
                      ✕
                    </button>
                  </div>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Choose a plan that fits your usage. You can change or cancel anytime.
                  </p>
                  <div className="mt-4 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setAnnual(false)}
                      className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                        !annual ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "text-[var(--muted)] hover:bg-[var(--background)]"
                      }`}
                    >
                      Monthly
                    </button>
                    <button
                      type="button"
                      onClick={() => setAnnual(true)}
                      className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                        annual ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "text-[var(--muted)] hover:bg-[var(--background)]"
                      }`}
                    >
                      Annually
                    </button>
                    <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      Save 17%
                    </span>
                  </div>
                  <div className="mt-6 grid gap-4 sm:grid-cols-3">
                    {paidPlans.map((plan) => {
                      const isCurrent = userTier === plan.id;
                      const displayPrice =
                        annual && plan.annualPrice > 0
                          ? `${formatPrice(plan.annualPrice)}/yr`
                          : plan.monthlyPrice === 0
                            ? "Free"
                            : `${formatPrice(plan.monthlyPrice)}/mo`;
                      return (
                        <div
                          key={plan.id}
                          className={`rounded-xl border p-4 ${
                            plan.recommended
                              ? "border-[var(--primary)]/40 bg-[var(--primary)]/5"
                              : "border-[var(--glass-border)] bg-[var(--background)]/50"
                          }`}
                        >
                          {plan.recommended && (
                            <span className="rounded-full bg-[var(--primary)]/20 px-2 py-0.5 text-xs font-medium text-[var(--primary)]">
                              Recommended
                            </span>
                          )}
                          <h3 className="mt-2 font-semibold text-[var(--foreground)]">{plan.name}</h3>
                          <p className="mt-1 text-2xl font-bold text-[var(--foreground)]">{displayPrice}</p>
                          <p className="mt-1 text-xs text-[var(--muted)]">{plan.invoiceLimitLabel}</p>
                          <ul className="mt-3 space-y-1 text-xs text-[var(--muted)]">
                            {plan.features.slice(0, 3).map((f, i) => (
                              <li key={i}>{f}</li>
                            ))}
                          </ul>
                          <button
                            type="button"
                            onClick={() => setSelectedPlanId(plan.id)}
                            disabled={isCurrent}
                            className="mt-4 w-full rounded-xl bg-[var(--primary)] py-2.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {isCurrent ? "Current plan" : "Select"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
