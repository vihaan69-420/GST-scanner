/**
 * Admin Plans CMS — data model and seed.
 * In-memory only. Exact tier specification.
 */

export interface PlanLimits {
  invoices_per_month?: number;
  users?: number;
  max_pages?: number;
  workspace?: string;
  upload?: string;
  history_days?: number;
  history?: string;
  batch_upload?: string;
}

export interface Plan {
  id: string;
  name: string;
  limits: PlanLimits;
  features: string[];
  locked: string[];
  conversion_trigger?: string;
  upgrade_trigger?: string;
}

export const INITIAL_PLANS: Plan[] = [
  {
    id: "free",
    name: "Free Bucket (Pre-Tier)",
    limits: {
      invoices_per_month: 3,
      users: 1,
      max_pages: 3,
    },
    features: ["core extraction", "sheets sync"],
    locked: ["exports", "history", "bulk upload", "corrections"],
    conversion_trigger: "invoice #4",
  },
  {
    id: "starter",
    name: "Tier 1 — Starter",
    limits: {
      users: 1,
      workspace: "single",
      invoices_per_month: 10,
      max_pages: 5,
      upload: "manual only",
      history_days: 30,
    },
    features: ["OCR", "line items", "GST validation", "Sheets sync"],
    locked: ["bulk upload", "exports", "corrections", "audit logs"],
    upgrade_trigger: "limit reached",
  },
  {
    id: "pro",
    name: "Tier 2 — Pro",
    limits: {
      users: 3,
      workspace: "shared",
      invoices_per_month: 100,
      batch_upload: "limited",
      max_pages: 15,
      history: "6 months",
    },
    features: [
      "duplicate detection",
      "confidence scoring",
      "manual corrections",
      "categorization",
      "GSTR-1 export",
      "CSV download",
    ],
    locked: [],
    upgrade_trigger: undefined,
  },
];
