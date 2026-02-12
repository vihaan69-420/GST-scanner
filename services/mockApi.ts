/**
 * Mock backend layer for GST Scanner app.
 * Simulates API behavior with fake delays and data.
 * Replace with real API calls later.
 */

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface MockInvoice {
  id: string;
  invoiceNumber: string;
  seller: string;
  gstAmount: number;
  total: number;
  validationStatus: "valid" | "warning" | "error";
  date: string;
}

export interface MockOrder {
  id: string;
  orderId: string;
  items: number;
  totalQuantity: number;
  subtotal: number;
  total: number;
  format: "PDF" | "CSV";
  date: string;
}

export interface MockHistoryItem {
  id: string;
  type: "invoice" | "order";
  reference: string;
  date: string;
  status: string;
  amount?: number;
}

export async function uploadInvoice(files: File[]): Promise<{ success: boolean; count: number }> {
  await delay(800);
  return { success: true, count: files.length };
}

export async function processInvoice(): Promise<MockInvoice> {
  await delay(1500);
  return {
    id: "inv-" + Date.now(),
    invoiceNumber: "INV/2024/001",
    seller: "Acme Goods Pvt Ltd",
    gstAmount: 1800,
    total: 11800,
    validationStatus: "valid",
    date: new Date().toISOString().slice(0, 10),
  };
}

export async function uploadOrder(files: File[], format: "PDF" | "CSV"): Promise<{ success: boolean }> {
  await delay(1000);
  return { success: true };
}

export async function processOrder(): Promise<MockOrder> {
  await delay(1800);
  return {
    id: "ord-" + Date.now(),
    orderId: "ORD-2024-042",
    items: 12,
    totalQuantity: 24,
    subtotal: 43200,
    total: 45600,
    format: "PDF",
    date: new Date().toISOString().slice(0, 10),
  };
}

export async function generateReport(month: number, year: number, type: string): Promise<{ url: string; name: string }> {
  await delay(2000);
  return {
    url: "#",
    name: `GST_Report_${type}_${month}_${year}.pdf`,
  };
}

export async function fetchHistory(type?: "invoice" | "order"): Promise<MockHistoryItem[]> {
  await delay(600);
  const items: MockHistoryItem[] = [
    { id: "1", type: "invoice", reference: "INV/2024/001", date: "2024-02-10", status: "Processed", amount: 11800 },
    { id: "2", type: "order", reference: "ORD-2024-042", date: "2024-02-09", status: "Completed" },
    { id: "3", type: "invoice", reference: "INV/2024/002", date: "2024-02-08", status: "Processed", amount: 5900 },
    { id: "4", type: "invoice", reference: "INV/2024/003", date: "2024-02-07", status: "Failed" },
    { id: "5", type: "order", reference: "ORD-2024-041", date: "2024-02-06", status: "Completed" },
  ];
  if (type) return items.filter((i) => i.type === type);
  return items;
}

export type TierId = "free" | "starter" | "pro" | "power";

export async function getUsageStats(): Promise<{
  invoicesUsed: number;
  invoicesLimit: number;
  ordersUsed: number;
  tier: TierId;
}> {
  await delay(400);
  return {
    invoicesUsed: 12,
    invoicesLimit: 50,
    ordersUsed: 5,
    tier: "starter",
  };
}

/** Order processing step labels for chat progress (6 steps). */
export const ORDER_PROCESS_STEPS = [
  "Extracting order",
  "Normalizing part names and colors",
  "Processing all items",
  "Matching prices",
  "Computing totals",
  "Generating file",
] as const;
