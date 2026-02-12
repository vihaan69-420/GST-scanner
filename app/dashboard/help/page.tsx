"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const HELP_SECTIONS = [
  { id: "start", title: "Getting started", content: "Create an account, then use Upload Invoice or Upload Order from the sidebar. Drop files or click to upload. Process to extract data." },
  { id: "upload", title: "Upload guide", content: "Supported formats: images (JPEG, PNG) and PDF. For orders, you can export as PDF or CSV. Keep file sizes under 10MB for best performance." },
  { id: "corrections", title: "Corrections", content: "After processing, review the extracted data. Use the Edit option on any field to correct GSTIN, amounts, or line items. Changes sync to your connected sheet." },
  { id: "exports", title: "Exports", content: "Generate GSTR-1 and GSTR-3B reports from the Reports section. Select month, year, and report type. Download the generated file when ready." },
  { id: "trouble", title: "Troubleshooting", content: "If upload fails, check file format and size. For validation errors, ensure GSTIN format is correct. Contact support from Settings if issues persist." },
];

export default function HelpPage() {
  const [openId, setOpenId] = useState<string | null>("start");

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-2xl">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Help</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          FAQ, instructions, and examples. Clear steps for uploading orders, invoices, and generating GST inputs.
        </p>
        <div className="mt-6 space-y-2">
          {HELP_SECTIONS.map((section) => (
            <motion.div
              key={section.id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl border border-[var(--glass-border)] bg-[var(--card)] overflow-hidden"
            >
              <button
                type="button"
                onClick={() => setOpenId(openId === section.id ? null : section.id)}
                className="flex w-full items-center justify-between px-4 py-3 text-left font-medium text-[var(--foreground)]"
              >
                {section.title}
                <span className="text-[var(--muted)]">{openId === section.id ? "−" : "+"}</span>
              </button>
              <AnimatePresence>
                {openId === section.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="border-t border-[var(--glass-border)]"
                  >
                    <p className="px-4 py-3 text-sm text-[var(--muted)]">{section.content}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
