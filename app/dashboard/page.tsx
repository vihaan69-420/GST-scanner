"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAppStore } from "@/store/appStore";
import {
  uploadInvoice,
  confirmInvoice,
  uploadOrder,
  processOrder,
  getUsageStats,
  ORDER_PROCESS_STEPS,
  type MockInvoice,
} from "@/services/api";
import { TIER_PLANS } from "@/lib/tiers";
import MessageBubble from "@/components/chat/MessageBubble";
import UploadZone from "@/components/chat/UploadZone";
import ProgressTracker from "@/components/chat/ProgressTracker";
import FilePreviewCards from "@/components/chat/FilePreviewCards";
import ActionCard from "@/components/chat/ActionCard";
import UpgradePlanModal from "@/components/modals/UpgradePlanModal";

const WELCOME_CONTENT = `Welcome to GST Scanner! I help you extract GST invoice data and append it to Google Sheets automatically.

Here's what I can do:

• Extract invoice data from images
• Validate GST numbers and calculations
• Save to Google Sheets with line items
• Generate GSTR‑1 and GSTR‑3B exports
• Process multiple invoices in batch
• Provide detailed reports and statistics

Ready to get started? Select an option from the menu below:`;

const MENU_BUTTONS = [
  { label: "Upload Purchase Invoice", action: "upload-invoice" },
  { label: "Upload Order (handwritten notes)", action: "upload-order" },
  { label: "Generate GST Input", action: "generate-report" },
];

const INVOICE_STEPS = [
  { label: "Upload", status: "pending" as const },
  { label: "Parse", status: "pending" as const },
  { label: "Validate", status: "pending" as const },
  { label: "Done", status: "pending" as const },
];

const orderSteps = ORDER_PROCESS_STEPS.map((label) => ({ label, status: "pending" as const }));

type Flow = null | "invoice" | "order" | "report" | "help" | "usage";
type OrderPhase = "collecting" | "format" | "processing" | "done";

export default function DashboardPage() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const {
    messages,
    addMessage,
    setProgressSteps,
    progressSteps,
    setStepStatus,
    setHasActiveSession,
    uploadedFiles,
    setUploadedFiles,
    setUsageStats,
    userTier,
    setUserTier,
    usageStats,
  } = useAppStore();

  const [flow, setFlow] = useState<Flow>(null);
  const [orderPhase, setOrderPhase] = useState<OrderPhase>("collecting");
  const [orderPages, setOrderPages] = useState<File[]>([]);
  const [processing, setProcessing] = useState(false);
  const [invoiceResult, setInvoiceResult] = useState<MockInvoice | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);

  useEffect(() => {
    getUsageStats().then((s) => {
      setUsageStats(s);
      setUserTier(s.tier);
    });
  }, [setUsageStats, setUserTier]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, progressSteps, orderPhase]);

  const tierPlan = TIER_PLANS.find((p) => p.id === userTier) ?? TIER_PLANS[1];
  const invoiceLimit = tierPlan.invoiceLimit;
  const atInvoiceLimit = invoiceLimit >= 0 && (usageStats?.invoicesUsed ?? 0) >= invoiceLimit;

  const hasSeededWelcome = useRef(false);

  useEffect(() => {
    if (messages.length === 0) hasSeededWelcome.current = false;
  }, [messages.length]);

  useEffect(() => {
    if (hasSeededWelcome.current) return;
    const state = useAppStore.getState();
    if (state.messages.some((m) => m.type === "menu" && m.content.startsWith("Welcome to GST Scanner"))) {
      hasSeededWelcome.current = true;
      return;
    }
    if (state.messages.length > 0) return;
    hasSeededWelcome.current = true;
    addMessage({
      role: "bot",
      type: "menu",
      content: WELCOME_CONTENT,
      buttons: MENU_BUTTONS,
    });
  }, [messages.length, addMessage]);

  const handleConfirmInvoice = useCallback(async () => {
    if (!invoiceResult?.session_id) return;
    setProcessing(true);
    addMessage({ role: "bot", type: "text", content: "Saving invoice to Google Sheets..." });

    try {
      const result = await confirmInvoice(invoiceResult.session_id);
      addMessage({
        role: "bot",
        type: "text",
        content: `Invoice ${result.invoice_no} saved to Google Sheets successfully!\n\nTo view: Open Google Sheets > invoice_header tab > find your data.`,
        buttons: [
          { label: "Open Google Sheets", action: "open-sheets" },
          { label: "Upload Another", action: "upload-invoice" },
        ],
      });
    } catch (err) {
      addMessage({
        role: "bot",
        type: "text",
        content: `Failed to save: ${err instanceof Error ? err.message : "Unknown error"}. You can try again.`,
        buttons: [
          { label: "Retry Save", action: "confirm-invoice" },
          { label: "Start Over", action: "upload-invoice" },
        ],
      });
    } finally {
      setProcessing(false);
      setInvoiceResult(null);
      setFlow(null);
    }
  }, [invoiceResult, addMessage]);

  const runOrderProcessing = useCallback(
    async (format: "PDF" | "CSV", pages: File[]) => {
      setProcessing(true);
      for (let i = 0; i < 6; i++) {
        setStepStatus(i, "active");
        await new Promise((r) => setTimeout(r, 500));
        setStepStatus(i, "done");
      }
      await uploadOrder(pages, format);
      const order = await processOrder();
      addMessage({
        role: "bot",
        type: "result",
        content: "Order processed successfully!",
        payload: order,
      });
      addMessage({
        role: "bot",
        type: "text",
        content: "You can download your file below. To view in Google Sheets: Open Google Sheets → Check invoice_header tab → Find your username.",
        buttons: [
          { label: "Download", action: "download-order" },
          { label: "Open Google Sheets", action: "open-sheets" },
        ],
      });
      setProcessing(false);
      setOrderPhase("done");
    },
    [setStepStatus, addMessage, setOrderPhase]
  );

  const handleAction = useCallback(
    (action: string) => {
      if (action === "upload-invoice") {
        addMessage({ role: "user", type: "text", content: "Upload Purchase Invoice" });
        addMessage({
          role: "bot",
          type: "text",
          content:
            "Upload single or multipage invoice images or PDFs. I'll extract GST data, validate, and append to Google Sheets.",
        });
        setFlow("invoice");
        setInvoiceResult(null);
        setUploadedFiles([]);
        setProgressSteps([]);
        return;
      }
      if (action === "upload-order") {
        addMessage({ role: "user", type: "text", content: "Upload Order" });
        addMessage({
          role: "bot",
          type: "text",
          content:
            "Ready to receive order pages. Send photos of handwritten note orders. You can send multiple pages. Click Submit Order when finished or Cancel to abort.",
         
        });
        setFlow("order");
        setOrderPhase("collecting");
        setOrderPages([]);
        setProgressSteps([]);
        return;
      }
      if (action === "generate-report") {
        addMessage({ role: "user", type: "text", content: "Generate GST Input" });
        addMessage({
          role: "bot",
          type: "text",
          content: "Open Reports to generate GSTR-1 or GSTR-3B by month and year.",
          buttons: [{ label: "Open Reports", action: "open-reports" }],
        });
        setFlow("report");
        return;
      }
      if (action === "open-reports") {
        window.location.href = "/dashboard/history-reports";
        return;
      }
      if (action === "help") {
        addMessage({ role: "user", type: "text", content: "Help" });
        addMessage({
          role: "bot",
          type: "text",
          content:
            "Getting started: Use the menu above to upload invoices or orders.\n\nUpload guide: Drop images or PDFs; we support multipage. For orders, send all pages then click Submit Order.\n\nNeed more? Visit the Help page for corrections, exports, and troubleshooting.",
          buttons: [{ label: "Open Help", action: "open-help" }],
        });
        setFlow("help");
        return;
      }
      if (action === "open-help") {
        window.location.href = "/dashboard/help";
        return;
      }
      if (action === "usage") {
        addMessage({ role: "user", type: "text", content: "Usage & Stats" });
        const used = usageStats?.invoicesUsed ?? 0;
        const limit = usageStats?.invoicesLimit ?? tierPlan.invoiceLimit;
        const limitStr = limit < 0 ? "Unlimited" : String(limit);
        addMessage({
          role: "bot",
          type: "text",
          content: `Your usage this month:\n\n• Invoices: ${used} / ${limitStr}\n• Orders: ${usageStats?.ordersUsed ?? 0}\n• Plan: ${tierPlan.name}\n\nUpgrade for higher limits and more features.`,
          buttons: [{ label: "View Plans", action: "view-plans" }],
        });
        setFlow("usage");
        return;
      }
      if (action === "view-plans") {
        setUpgradeModalOpen(true);
        return;
      }
      if (action === "submit-order") {
        if (orderPages.length === 0) return;
        addMessage({ role: "user", type: "text", content: "Submit Order" });
        addMessage({
          role: "bot",
          type: "text",
          content: "Choose output format:",
          buttons: [
            { label: "PDF", action: "format-pdf" },
            { label: "CSV", action: "format-csv" },
          ],
        });
        setOrderPhase("format");
        return;
      }
      if (action === "cancel-order") {
        addMessage({ role: "user", type: "text", content: "Cancel" });
        addMessage({ role: "bot", type: "text", content: "Order cancelled. What would you like to do next?" });
        setFlow(null);
        setOrderPhase("collecting");
        setOrderPages([]);
        return;
      }
      if (action === "format-pdf" || action === "format-csv") {
        const fmt = action === "format-pdf" ? "PDF" : "CSV";
        addMessage({ role: "user", type: "text", content: fmt });
        setOrderPhase("processing");
        setHasActiveSession(true);
        setProgressSteps(orderSteps.map((s, i) => ({ ...s, status: i === 0 ? "active" : "pending" })));
        addMessage({
          role: "bot",
          type: "text",
          content: "Processing your order…",
        });
        runOrderProcessing(fmt, orderPages);
        return;
      }
      if (action === "upgrade" || action === "view-plans") {
        setUpgradeModalOpen(true);
        return;
      }
      if (action === "confirm-invoice") {
        handleConfirmInvoice();
        return;
      }
      if (action === "cancel-invoice") {
        addMessage({ role: "user", type: "text", content: "Start Over" });
        addMessage({ role: "bot", type: "text", content: "Invoice discarded. Upload new files to try again." });
        setInvoiceResult(null);
        setUploadedFiles([]);
        setProgressSteps([]);
        setFlow("invoice");
        return;
      }
      if (action === "download-order") {
        addMessage({ role: "user", type: "text", content: "Download" });
        addMessage({ role: "bot", type: "text", content: "Download started. (This is a demo — no file is actually downloaded.)" });
        return;
      }
      if (action === "open-sheets") {
        addMessage({ role: "user", type: "text", content: "Open Google Sheets" });
        addMessage({ role: "bot", type: "text", content: "In Google Sheets, open your linked workbook → invoice_header tab → find your username to see the data." });
        window.open("https://sheets.google.com", "_blank");
        return;
      }
    },
    [
      addMessage,
      setFlow,
      setOrderPhase,
      setOrderPages,
      orderPages,
      setProgressSteps,
      setHasActiveSession,
      setUploadedFiles,
      usageStats,
      tierPlan,
      runOrderProcessing,
      handleConfirmInvoice,
      setUpgradeModalOpen,
    ]
  );

  const handleInvoiceFiles = useCallback(
    async (files: File[]) => {
      if (atInvoiceLimit) return;
      files.forEach((f) =>
        useAppStore.getState().addUploadedFile({
          id: "f-" + Date.now() + "-" + Math.random().toString(36).slice(2),
          name: f.name,
          size: f.size,
          type: f.type,
        })
      );
      addMessage({ role: "user", type: "text", content: `Uploaded ${files.length} file(s).` });
      setProgressSteps(INVOICE_STEPS);
      setHasActiveSession(true);
      setProcessing(true);

      // Step 1: Upload - OCR + Parse happens server-side in one call
      setStepStatus(0, "active");
      addMessage({ role: "bot", type: "text", content: "Uploading and running OCR..." });

      try {
        const invoice = await uploadInvoice(files);
        setStepStatus(0, "done");

        // Step 2: Parse complete
        setStepStatus(1, "active");
        await new Promise((r) => setTimeout(r, 300));
        setStepStatus(1, "done");

        // Step 3: Validate complete
        setStepStatus(2, "active");
        await new Promise((r) => setTimeout(r, 300));
        setStepStatus(2, "done");
        setStepStatus(3, "done");

        setInvoiceResult(invoice);
        setProcessing(false);

        // Show extracted data
        addMessage({
          role: "bot",
          type: "result",
          content: "Invoice extracted successfully! Review the data below.",
          payload: invoice,
        });

        // Show confirm/correct actions
        addMessage({
          role: "bot",
          type: "text",
          content: "Does this look correct? Confirm to save to Google Sheets, or start over.",
          buttons: [
            { label: "Confirm & Save to Sheets", action: "confirm-invoice" },
            { label: "Start Over", action: "cancel-invoice" },
          ],
        });
      } catch (err) {
        setProcessing(false);
        setStepStatus(0, "done");
        addMessage({
          role: "bot",
          type: "text",
          content: `Invoice processing failed: ${err instanceof Error ? err.message : "Unknown error"}. Please try again.`,
        });
        setFlow(null);
      }
    },
    [addMessage, setProgressSteps, setStepStatus, setHasActiveSession, atInvoiceLimit]
  );

  const handleOrderPageUpload = useCallback(
    (files: File[]) => {
      setOrderPages((prev) => [...prev, ...files]);
      files.forEach((_, i) => {
        const n = orderPages.length + i + 1;
        addMessage({ role: "bot", type: "text", content: `Page ${n} received ✅` });
      });
    },
    [orderPages.length, addMessage]
  );

  const handleSendMessage = useCallback(() => {
    const text = chatInput.trim();
    if (!text) return;
    addMessage({ role: "user", type: "text", content: text });
    setChatInput("");
    addMessage({
      role: "bot",
      type: "text",
      content: "Thanks for your message. Use the menu options above to upload invoices, orders, or generate reports. If you need help, choose Help from the menu.",
    });
  }, [chatInput, addMessage]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div ref={scrollRef} className="flex flex-1 flex-col overflow-y-auto p-4">
        <div className="mx-auto w-full max-w-2xl space-y-4">
          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              role={m.role}
              content={m.content}
              type={m.type}
              buttons={m.buttons}
              onButtonClick={handleAction}
              payload={m.payload}
            />
          ))}

          {flow === "invoice" && (
            <>
              {atInvoiceLimit && (
                <MessageBubble
                  role="bot"
                  content="You’ve reached your invoice limit for this month. Upgrade to process more invoices."
                  buttons={[{ label: "Upgrade plan", action: "upgrade" }]}
                  onButtonClick={handleAction}
                />
              )}
              {!atInvoiceLimit && (
                <>
                  {uploadedFiles.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-[var(--muted)]">Uploaded</p>
                      <div className="flex flex-wrap gap-2">
                        {uploadedFiles.map((f) => (
                          <div
                            key={f.id}
                            className="rounded-xl border border-[var(--glass-border)] bg-[var(--card)] px-3 py-2 text-sm shadow-sm"
                          >
                            <span className="font-medium text-[var(--foreground)]">{f.name}</span>
                            <span className="ml-2 text-xs text-[var(--muted)]">{(f.size / 1024).toFixed(1)} KB</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {!processing && !invoiceResult && (
                    <UploadZone onFilesSelected={handleInvoiceFiles} accept="image/*,.pdf" multiple={true} />
                  )}
                  {progressSteps.length > 0 && <ProgressTracker steps={progressSteps} />}
                  {processing && (
                    <div className="text-center text-sm text-[var(--muted)] py-2">Processing invoice...</div>
                  )}
                </>
              )}
            </>
          )}

          {flow === "order" && orderPhase === "collecting" && (
            <>
              {orderPages.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-[var(--muted)]">Order pages</p>
                  <FilePreviewCards files={orderPages} />
                </div>
              )}
              <UploadZone
                onFilesSelected={(files) => {
                  handleOrderPageUpload(files);
                  setHasActiveSession(true);
                }}
                accept="image/*"
                multiple={true}
              />
              <ActionCard
                title="Submit or cancel"
                description={orderPages.length > 0 ? `You have ${orderPages.length} page(s) ready. Submit when done or cancel to abort.` : "Add at least one page to submit."}
                actions={[
                  { label: "Submit Order", action: "submit-order" },
                  { label: "Cancel", action: "cancel-order" },
                ]}
                onActionClick={handleAction}
              />
            </>
          )}

          {flow === "order" && orderPhase === "processing" && progressSteps.length > 0 && (
            <ProgressTracker
              steps={progressSteps.map((s, i) => ({
                ...s,
                label: `Step ${i + 1}/6: ${ORDER_PROCESS_STEPS[i]}`,
              }))}
            />
          )}

        </div>
      </div>

      {/* Chat input — fixed at bottom, ChatGPT-style */}
      <div className="border-t border-[var(--glass-border)] bg-[var(--card)]/80 p-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-2xl gap-3">
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSendMessage()}
            placeholder="Type a message…"
            className="min-h-[48px] flex-1 rounded-xl border border-[var(--glass-border)] bg-[var(--background)] px-4 py-2.5 text-sm text-[var(--foreground)] placeholder:text-[var(--muted)] focus:border-[var(--primary)]/50 focus:outline-none focus:ring-1 focus:ring-[var(--primary)]/30"
            aria-label="Chat message"
          />
          <button
            type="button"
            onClick={handleSendMessage}
            disabled={!chatInput.trim()}
            className="shrink-0 rounded-xl bg-[var(--primary)] px-5 py-2.5 text-sm font-medium text-[var(--primary-foreground)] transition hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>

      <UpgradePlanModal open={upgradeModalOpen} onClose={() => setUpgradeModalOpen(false)} />
    </div>
  );
}
