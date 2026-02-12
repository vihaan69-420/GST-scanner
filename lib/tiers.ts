/**
 * Tier and pricing data for GST Scanner landing and /pricing.
 * Aligned with MicroSaaS tiered feature plan: Free bucket, Starter, Pro, Power.
 */

export type TierId = "free" | "starter" | "pro" | "power";

export type FeatureCellValue = boolean | "limited" | string;

export interface TierPlan {
  id: TierId;
  name: string;
  monthlyPrice: number;
  annualPrice: number;
  invoiceLimit: number;
  invoiceLimitLabel: string;
  features: string[];
  recommended?: boolean;
}

/** Free bucket (pre-tier): trust + habit. Starter = try & trust, Pro = daily ops, Power = scale & compliance. */
export const TIER_PLANS: TierPlan[] = [
  {
    id: "free",
    name: "Free",
    monthlyPrice: 0,
    annualPrice: 0,
    invoiceLimit: 3,
    invoiceLimitLabel: "3 invoices / month",
    features: [
      "Core GST extraction",
      "Google Sheets sync",
      "1 user",
      "Multipage (max 3 pages)",
      "No exports, history, bulk, or corrections",
    ],
  },
  {
    id: "starter",
    name: "Starter",
    monthlyPrice: 299,
    annualPrice: 2990,
    invoiceLimit: 10,
    invoiceLimitLabel: "10 invoices / month",
    features: [
      "GST OCR & field extraction",
      "Line item parsing",
      "Basic GST validation",
      "Google Sheets sync",
      "Invoice history (30 days)",
      "Up to 10 orders, max 5 pages/invoice",
      "Single workspace, manual upload only",
    ],
    recommended: true,
  },
  {
    id: "pro",
    name: "Pro",
    monthlyPrice: 799,
    annualPrice: 7990,
    invoiceLimit: 100,
    invoiceLimitLabel: "100 invoices / month",
    features: [
      "Everything in Starter",
      "Bulk uploads (limited)",
      "Duplicate detection",
      "Confidence scoring",
      "Manual corrections",
      "Invoice categorization",
      "Extended history (6 months)",
      "GSTR-1 export (basic), CSV download",
      "Up to 3 users, shared workspace",
    ],
  },
  {
    id: "power",
    name: "Power",
    monthlyPrice: 1999,
    annualPrice: 19990,
    invoiceLimit: -1,
    invoiceLimitLabel: "Unlimited",
    features: [
      "Everything in Pro",
      "Up to 10 users, multiple workspaces",
      "Unlimited invoices & orders",
      "Unlimited pages per invoice",
      "Advanced GST validation",
      "Auto-learning corrections",
      "Audit logs & version history",
      "Role-based access",
      "GSTR-1 & GSTR-3B summary",
      "Monthly & quarterly reports",
      "Accountant-ready formats",
      "Priority support",
    ],
  },
];

export interface DetailedFeatureRow {
  name: string;
  free: FeatureCellValue;
  starter: FeatureCellValue;
  pro: FeatureCellValue;
  power: FeatureCellValue;
  group?: string;
}

/** Detailed comparison for /pricing page. */
export const DETAILED_FEATURE_MATRIX: DetailedFeatureRow[] = [
  { name: "Invoices per month", free: "3", starter: "10", pro: "100", power: "Unlimited", group: "Limits" },
  { name: "Users", free: "1", starter: "1", pro: "3", power: "10", group: "Limits" },
  { name: "Workspace", free: "Single", starter: "Single", pro: "Shared", power: "Multiple", group: "Limits" },
  { name: "Orders (per month)", free: "3", starter: "10", pro: "100", power: "Unlimited", group: "Limits" },
  { name: "Max pages per invoice", free: "3", starter: "5", pro: "15", power: "Unlimited", group: "Limits" },
  { name: "Invoice history", free: "—", starter: "30 days", pro: "6 months", power: "Unlimited", group: "Limits" },
  { name: "Upload", free: "Manual", starter: "Manual only", pro: "Manual + batch (limited)", power: "ZIP batch, priority", group: "Limits" },
  { name: "GST OCR & extraction", free: true, starter: true, pro: true, power: true, group: "Features" },
  { name: "Line item parsing", free: true, starter: true, pro: true, power: true, group: "Features" },
  { name: "Basic GST validation", free: true, starter: true, pro: true, power: true, group: "Features" },
  { name: "Advanced GST validation", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "Google Sheets sync", free: true, starter: true, pro: true, power: true, group: "Features" },
  { name: "Duplicate detection", free: false, starter: false, pro: true, power: true, group: "Features" },
  { name: "Confidence scoring", free: false, starter: false, pro: true, power: true, group: "Features" },
  { name: "Manual corrections", free: false, starter: false, pro: true, power: true, group: "Features" },
  { name: "Auto-learning corrections", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "Invoice categorization", free: false, starter: false, pro: true, power: true, group: "Features" },
  { name: "GSTR-1 export", free: false, starter: false, pro: true, power: true, group: "Features" },
  { name: "GSTR-3B summary", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "CSV download", free: false, starter: false, pro: true, power: true, group: "Features" },
  { name: "Bulk / batch upload", free: false, starter: false, pro: "limited", power: true, group: "Features" },
  { name: "Audit logs", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "Version history", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "Role-based access", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "Monthly/quarterly reports", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "Accountant-ready formats", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "Priority support", free: false, starter: false, pro: false, power: true, group: "Features" },
  { name: "Upgrade trigger", free: "Invoice #4", starter: "Limit or exports", pro: "Scale or reporting", power: "—", group: "Upgrade" },
];

export interface FeatureRow {
  name: string;
  free: boolean | "limited";
  starter: boolean | "limited";
  pro: boolean | "limited";
  power: boolean | "limited";
}

export const FEATURE_MATRIX: FeatureRow[] = [
  { name: "OCR invoice extraction", free: true, starter: true, pro: true, power: true },
  { name: "GST validation", free: true, starter: true, pro: true, power: true },
  { name: "Duplicate detection", free: false, starter: false, pro: true, power: true },
  { name: "Google Sheets sync", free: true, starter: true, pro: true, power: true },
  { name: "GSTR exports", free: false, starter: false, pro: "limited", power: true },
  { name: "Audit logs", free: false, starter: false, pro: false, power: true },
];

export function formatPrice(amount: number): string {
  if (amount === 0) return "Free";
  return `₹${amount.toLocaleString("en-IN")}`;
}
