"use client";

import { useState } from "react";
import { useAppStore } from "@/store/appStore";
import { processOrder } from "@/services/mockApi";
import MessageBubble from "@/components/chat/MessageBubble";
import UploadZone from "@/components/chat/UploadZone";
import ProgressTracker from "@/components/chat/ProgressTracker";
import ResultCard from "@/components/chat/ResultCard";

const ORDER_STEPS = [
  { label: "Upload", status: "pending" as const },
  { label: "Parse", status: "pending" as const },
  { label: "Validate", status: "pending" as const },
  { label: "Format", status: "pending" as const },
  { label: "Export", status: "pending" as const },
  { label: "Done", status: "pending" as const },
];

export default function UploadOrderPage() {
  const { addMessage, setProgressSteps, progressSteps, setStepStatus, setHasActiveSession } = useAppStore();
  const [format, setFormat] = useState<"PDF" | "CSV">("PDF");
  const [result, setResult] = useState<Awaited<ReturnType<typeof processOrder>> | null>(null);

  const handleFilesSelected = async (files: File[]) => {
    addMessage({ role: "user", type: "text", content: `Uploaded ${files.length} file(s) as ${format}.` });
    setProgressSteps(ORDER_STEPS);
    for (let i = 0; i < 6; i++) {
      setStepStatus(i, "active");
      await new Promise((r) => setTimeout(r, 400));
      setStepStatus(i, "done");
    }
    setHasActiveSession(true);
    const order = await processOrder();
    setResult(order);
    addMessage({ role: "bot", type: "text", content: "Order processed. Download summary below." });
  };

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-4">
      <div className="mx-auto w-full max-w-2xl space-y-4">
        <MessageBubble
          role="bot"
          content="Upload order photos or documents. Choose format (PDF or CSV) then drop files."
        />
        <div className="flex gap-2">
          {(["PDF", "CSV"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFormat(f)}
              className={`rounded-full px-4 py-2 text-sm font-medium ${
                format === f ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--card)] text-[var(--muted)]"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <UploadZone onFilesSelected={handleFilesSelected} accept="image/*,.pdf" />
        {progressSteps.length > 0 && <ProgressTracker steps={progressSteps} />}
        {result && (
          <ResultCard
            title="Order summary"
            fields={[
              { label: "Order ID", value: result.orderId },
              { label: "Items", value: result.items },
              { label: "Total", value: `₹${result.total}` },
              { label: "Format", value: result.format },
            ]}
            onDownload={() => {}}
          />
        )}
      </div>
    </div>
  );
}
