/**
 * Default subscription tier content (tier names, descriptions, feature toggles).
 * Shared by admin subscription page and API for DB persistence.
 */

export type TierId = "tier1" | "tier2" | "tier3";

export interface SubscriptionContent {
  tierNames: Record<TierId, string>;
  tierDescriptions: Record<TierId, string>;
  features: Record<TierId, Record<string, boolean>>;
}

export const DEFAULT_SUBSCRIPTION: SubscriptionContent = {
  tierNames: {
    tier1: "Starter",
    tier2: "Pro",
    tier3: "Power",
  },
  tierDescriptions: {
    tier1: "Try & trust — small business owners",
    tier2: "Daily operations — accountants / growing firms",
    tier3: "Scale & compliance — high-volume GST filers",
  },
  features: {
    tier1: {
      "GST OCR & extraction": true,
      "Line item parsing": true,
      "Basic GST validation": true,
      "Google Sheets sync": true,
      "Invoice history (30 days)": true,
      "Bulk upload": false,
      "GSTR-1 export": false,
      "Manual corrections": false,
      "Audit logs": false,
    },
    tier2: {
      "GST OCR & extraction": true,
      "Line item parsing": true,
      "Basic GST validation": true,
      "Google Sheets sync": true,
      "Invoice history (30 days)": true,
      "Bulk upload": true,
      "GSTR-1 export": true,
      "Manual corrections": true,
      "Audit logs": false,
      "Duplicate detection": true,
      "Confidence scoring": true,
    },
    tier3: {
      "GST OCR & extraction": true,
      "Line item parsing": true,
      "Basic GST validation": true,
      "Google Sheets sync": true,
      "Invoice history (30 days)": true,
      "Bulk upload": true,
      "GSTR-1 export": true,
      "Manual corrections": true,
      "Audit logs": true,
      "Duplicate detection": true,
      "Confidence scoring": true,
      "Advanced GST validation": true,
      "Role-based access": true,
      "GSTR-3B summary": true,
      "Priority support": true,
    },
  },
};
