/**
 * Plans content management — single source for what users see on dashboard/plans.
 * Admin edits in /admin/plans and saves here; user dashboard reads read-only.
 * Persisted in localStorage (no backend).
 */

import { TIER_PLANS } from "@/lib/tiers";
import type { TierPlan } from "@/lib/tiers";

export type UserFacingPlan = {
  id: string;
  name: string;
  description?: string;
  monthlyPrice: number;
  annualPrice: number;
  invoiceLimitLabel: string;
  features: string[];
  recommended?: boolean;
};

const STORAGE_KEY = "gst_plans_content";

function tierToUserFacing(t: TierPlan): UserFacingPlan {
  return {
    id: t.id,
    name: t.name,
    monthlyPrice: t.monthlyPrice,
    annualPrice: t.annualPrice,
    invoiceLimitLabel: t.invoiceLimitLabel,
    features: [...t.features],
    recommended: t.recommended,
  };
}

/** Default plans from app tiers (Starter, Pro, Power, etc.). */
export function getDefaultPlansContent(): UserFacingPlan[] {
  return TIER_PLANS.map(tierToUserFacing);
}

/** Read plans content for user display. From localStorage or default. */
export function getPlansContent(): UserFacingPlan[] {
  if (typeof window === "undefined") return getDefaultPlansContent();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return getDefaultPlansContent();
    const parsed = JSON.parse(raw) as UserFacingPlan[];
    if (Array.isArray(parsed) && parsed.length > 0) return parsed;
  } catch {
    // ignore
  }
  return getDefaultPlansContent();
}

/** Save plans content (admin only). Persists what users will see. */
export function setPlansContent(plans: UserFacingPlan[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(plans));
}
