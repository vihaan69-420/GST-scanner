/**
 * CMS content — home, features, about. Admin edits in /admin/cms; pages read from API/db.
 */

export type CmsFeatureItem = { icon: string; title: string; description: string };
export type CmsAboutCard = { title: string; desc: string };

export type CmsContent = {
  // Home
  heroHeadline: string;
  heroSubheadline: string;
  ctaPrimary: string;
  ctaSecondary: string;
  finalHeadline: string;
  finalSubtext: string;
  finalCtaPrimary: string;
  finalCtaSecondary: string;
  // Features page
  featuresSectionHeadline: string;
  featuresSectionSubtext: string;
  featuresList: CmsFeatureItem[];
  // About page
  aboutHeroTitle: string;
  aboutHeroSubtext: string;
  aboutWhyHeadline: string;
  aboutWhySubtext: string;
  aboutWhyCards: CmsAboutCard[];
  aboutWhyTagline: string;
  aboutWhyTaglineSubtext: string;
  aboutWorkflowsHeadline: string;
  aboutWorkflowItems: string[];
  aboutPhilosophyTitle: string;
  aboutPhilosophyItems: string[];
  aboutPhilosophySubtext: string;
  aboutLookingHeadline: string;
  aboutLookingText: string;
  aboutLookingQuestion: string;
  aboutLookingAnswer: string;
  aboutCtaLabel: string;
};

const STORAGE_KEY = "gst_cms_content";

const DEFAULT_FEATURES: CmsFeatureItem[] = [
  { icon: "📄", title: "OCR invoice extraction", description: "Extract line items, GSTINs, and totals from images or PDFs." },
  { icon: "✓", title: "GST validation", description: "Validate GST numbers and tax calculations automatically." },
  { icon: "🔍", title: "Duplicate detection", description: "Avoid double-counting with smart duplicate detection." },
  { icon: "📊", title: "Google Sheets sync", description: "Auto-sync extracted data to your Google Sheets." },
  { icon: "📤", title: "GSTR exports", description: "Generate GSTR-1 and GSTR-3B–ready exports." },
  { icon: "📋", title: "Audit logs", description: "Full audit trail for compliance and corrections." },
];

const DEFAULT_ABOUT_CARDS: CmsAboutCard[] = [
  { title: "Businesses lose time", desc: "Hours spent on data entry instead of growth." },
  { title: "Teams lose margins", desc: "Accounting overhead eats into profitability." },
  { title: "Focus is lost", desc: "High-value work gets delayed by repetitive tasks." },
];

const DEFAULT_WORKFLOW_ITEMS = [
  "Mobile-first document sharing",
  "Simple upload flows",
  "Spreadsheet-ready output",
  "Structured invoice fields",
  "Compliance-friendly exports",
];

const DEFAULT_PHILOSOPHY_ITEMS = [
  "Save hours, not minutes",
  "Reduce errors, not create new ones",
  "Feel invisible once running",
  "Scale without hiring more staff",
];

const DEFAULT: CmsContent = {
  heroHeadline: "Turn GST invoices into structured data instantly",
  heroSubheadline: "Zero manual entry. Zero hassle.",
  ctaPrimary: "Start Free",
  ctaSecondary: "View Plans",
  finalHeadline: "Stop manual GST entry forever",
  finalSubtext:
    "Join businesses that switched to automated GST extraction. No credit card required — start in under a minute.",
  finalCtaPrimary: "Start Free",
  finalCtaSecondary: "Contact Sales",
  featuresSectionHeadline: "Everything you need for GST compliance",
  featuresSectionSubtext: "From upload to export—streamlined for Indian GST workflows.",
  featuresList: DEFAULT_FEATURES.map((f) => ({ ...f })),
  aboutHeroTitle: "We're building the fastest way to process invoices.",
  aboutHeroSubtext:
    "GST Scanner eliminates manual invoice entry by turning invoice images into structured, ready-to-use financial data instantly.",
  aboutWhyHeadline: "Why we built GST Scanner",
  aboutWhySubtext:
    "Manual invoice processing doesn't scale. Teams spend hours typing, reconciling, and correcting data that should be automated.",
  aboutWhyCards: DEFAULT_ABOUT_CARDS.map((c) => ({ ...c })),
  aboutWhyTagline: "Invoice → Data → Done.",
  aboutWhyTaglineSubtext: "No heavy systems. No complex setup. Just automation that works.",
  aboutWorkflowsHeadline: "Built for real workflows",
  aboutWorkflowItems: [...DEFAULT_WORKFLOW_ITEMS],
  aboutPhilosophyTitle: "Our philosophy",
  aboutPhilosophyItems: [...DEFAULT_PHILOSOPHY_ITEMS],
  aboutPhilosophySubtext: "We don't replace your tools. We remove the friction around them.",
  aboutLookingHeadline: "Looking ahead",
  aboutLookingText:
    "Our roadmap is focused on deeper automation, smarter validation, and faster processing.",
  aboutLookingQuestion: "Does this save meaningful time?",
  aboutLookingAnswer: "If the answer is yes, we build it.",
  aboutCtaLabel: "Get started free",
};

export function getDefaultCmsContent(): CmsContent {
  return JSON.parse(JSON.stringify(DEFAULT));
}

/** Merge parsed (e.g. from API/db) with defaults so all keys exist. */
export function getMergedCmsContent(parsed: Partial<CmsContent> | null): CmsContent {
  const def = getDefaultCmsContent();
  if (!parsed) return def;
  const merged = { ...def };
  for (const k of Object.keys(def) as (keyof CmsContent)[]) {
    const v = (parsed as Record<string, unknown>)[k];
    if (v !== undefined && v !== null) {
      if (k === "featuresList" && Array.isArray(v)) {
        merged.featuresList = v.map((item) => ({
          icon: typeof item?.icon === "string" ? item.icon : "",
          title: typeof item?.title === "string" ? item.title : "",
          description: typeof item?.description === "string" ? item.description : "",
        }));
        if (merged.featuresList.length < 6) {
          while (merged.featuresList.length < 6) {
            merged.featuresList.push({ icon: "", title: "", description: "" });
          }
        }
      } else if (k === "aboutWhyCards" && Array.isArray(v)) {
        merged.aboutWhyCards = v.map((item) => ({
          title: typeof item?.title === "string" ? item.title : "",
          desc: typeof item?.desc === "string" ? item.desc : "",
        }));
        while (merged.aboutWhyCards.length < 3) {
          merged.aboutWhyCards.push({ title: "", desc: "" });
        }
      } else if (k === "aboutWorkflowItems" && Array.isArray(v)) {
        merged.aboutWorkflowItems = v.filter((x): x is string => typeof x === "string");
      } else if (k === "aboutPhilosophyItems" && Array.isArray(v)) {
        merged.aboutPhilosophyItems = v.filter((x): x is string => typeof x === "string");
      } else if (typeof v === "string") {
        (merged as Record<string, unknown>)[k] = v;
      }
    }
  }
  return merged;
}

export function getCmsContent(): CmsContent {
  if (typeof window === "undefined") return getDefaultCmsContent();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return getDefaultCmsContent();
    const parsed = JSON.parse(raw) as Partial<CmsContent>;
    return getMergedCmsContent(parsed);
  } catch {
    // ignore
  }
  return getDefaultCmsContent();
}

export function setCmsContent(content: CmsContent): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(content));
}
