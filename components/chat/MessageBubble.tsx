"use client";

import { motion } from "framer-motion";
import type { ChatMessageRole } from "@/store/appStore";
import ResultCard from "./ResultCard";
import ActionCard from "./ActionCard";
import type { MockInvoice, MockOrder } from "@/services/mockApi";

export interface MessageBubbleProps {
  role: ChatMessageRole;
  content: string;
  type?: string;
  buttons?: { label: string; action: string }[];
  onButtonClick?: (action: string) => void;
  payload?: unknown;
}

export default function MessageBubble({
  role,
  content,
  type,
  buttons,
  onButtonClick,
  payload,
}: MessageBubbleProps) {
  const isBot = role === "bot";

  // Bot message with buttons → render as action card (rounded container, clear separation from bubbles)
  if (isBot && buttons && buttons.length > 0 && type !== "result") {
    const firstLine = content.indexOf("\n") >= 0 ? content.slice(0, content.indexOf("\n")) : content;
    const rest = content.indexOf("\n") >= 0 ? content.slice(content.indexOf("\n") + 1).trim() : "";
    return (
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start">
        <div className="max-w-[85%] w-full">
          <ActionCard
            title={firstLine}
            description={rest || undefined}
            actions={buttons}
            onActionClick={onButtonClick}
          />
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isBot ? "justify-start" : "justify-end"}`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
          isBot
            ? "rounded-tl-md border border-[var(--glass-border)] bg-[var(--card)] text-[var(--foreground)] shadow-[var(--shadow-soft)]"
            : "rounded-tr-md bg-[var(--primary)] text-[var(--primary-foreground)]"
        }`}
      >
        <p className="text-sm whitespace-pre-line">{content}</p>
        {buttons && buttons.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {buttons.map((b) => (
              <button
                key={b.action}
                type="button"
                onClick={() => onButtonClick?.(b.action)}
                className="rounded-full bg-[var(--primary)]/20 px-4 py-2 text-sm font-medium text-[var(--primary)] hover:bg-[var(--primary)]/30 transition"
              >
                {b.label}
              </button>
            ))}
          </div>
        )}
        {type === "result" && payload ? (
          <div className="mt-3">
            {isInvoicePayload(payload) ? (
              <ResultCard
                title="Invoice result"
                fields={[
                  { label: "Invoice #", value: payload.invoiceNumber },
                  { label: "Seller", value: payload.seller },
                  { label: "GST amount", value: `₹${payload.gstAmount}` },
                  { label: "Total", value: `₹${payload.total}` },
                ]}
                status={payload.validationStatus}
              />
            ) : isOrderPayload(payload) ? (
              <ResultCard
                title="Order summary"
                fields={[
                  { label: "Order ID", value: payload.orderId },
                  { label: "Date", value: payload.date },
                  { label: "Total items", value: payload.items },
                  { label: "Total quantity", value: payload.totalQuantity },
                  { label: "Subtotal", value: `₹${payload.subtotal}` },
                  { label: "Total", value: `₹${payload.total}` },
                  { label: "Format", value: payload.format },
                ]}
                onDownload={() => {}}
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}

function isInvoicePayload(p: unknown): p is MockInvoice {
  return typeof p === "object" && p !== null && "invoiceNumber" in p && "seller" in p;
}

function isOrderPayload(p: unknown): p is MockOrder {
  return typeof p === "object" && p !== null && "orderId" in p && "items" in p;
}
