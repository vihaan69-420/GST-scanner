/**
 * Real API client for GST Scanner.
 * Replaces mockApi.ts with actual HTTP calls to the FastAPI backend.
 * Maintains the same interface so existing components work without changes.
 *
 * The FastAPI backend URL is configured via NEXT_PUBLIC_API_URL env var.
 * Default: http://localhost:8000
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Token management ─────────────────────────────────────────────

let _accessToken: string | null = null;
let _refreshToken: string | null = null;

const TOKEN_STORAGE_KEY = "gst_api_tokens";

function loadTokens(): void {
  if (typeof window === "undefined") return;
  try {
    const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      _accessToken = parsed.access_token || null;
      _refreshToken = parsed.refresh_token || null;
    }
  } catch {
    // ignore
  }
}

function saveTokens(access: string, refresh: string): void {
  _accessToken = access;
  _refreshToken = refresh;
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify({ access_token: access, refresh_token: refresh }));
  }
}

export function clearTokens(): void {
  _accessToken = null;
  _refreshToken = null;
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export function getAccessToken(): string | null {
  if (!_accessToken) loadTokens();
  return _accessToken;
}

// ── HTTP helper ──────────────────────────────────────────────────

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  if (!_accessToken) loadTokens();

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (_accessToken) {
    headers["Authorization"] = `Bearer ${_accessToken}`;
  }

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // Auto-refresh on 401
  if (res.status === 401 && _refreshToken) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${_accessToken}`;
      return fetch(`${API_BASE}${path}`, { ...options, headers });
    }
  }

  return res;
}

async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.detail || err.error || `API error ${res.status}`);
  }
  return res.json();
}

// ── Auth functions ───────────────────────────────────────────────

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  role: "user" | "admin";
}

export async function apiRegister(email: string, password: string, fullName: string): Promise<{ message: string }> {
  return apiJson("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
}

export async function apiLogin(email: string, password: string): Promise<AuthTokens> {
  const tokens = await apiJson<AuthTokens>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  saveTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
}

export async function apiLogout(): Promise<void> {
  clearTokens();
}

async function refreshAccessToken(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: _refreshToken }),
    });
    if (!res.ok) {
      clearTokens();
      return false;
    }
    const tokens: AuthTokens = await res.json();
    saveTokens(tokens.access_token, tokens.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

export async function apiGetProfile(): Promise<{
  id: string;
  email: string;
  full_name: string;
  role: "user" | "admin";
  created_at: string;
  invoice_count: number;
  order_count: number;
}> {
  return apiJson("/auth/me");
}

// ── Types (compatible with MockInvoice / MockOrder) ──────────────

export interface MockInvoice {
  id: string;
  session_id: string;
  invoiceNumber: string;
  seller: string;
  gstAmount: number;
  total: number;
  validationStatus: "valid" | "warning" | "error";
  date: string;
  invoice_data: Record<string, unknown>;
  line_items: Record<string, unknown>[];
  confidence_scores?: Record<string, number>;
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
  line_items: Record<string, unknown>[];
}

export interface MockHistoryItem {
  id: string;
  type: "invoice" | "order";
  reference: string;
  date: string;
  status: string;
  amount?: number;
}

// ── Invoice functions (same interface as mockApi) ────────────────

export async function uploadInvoice(files: File[]): Promise<MockInvoice> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  const result = await apiJson<{
    session_id: string;
    invoice_data: Record<string, unknown>;
    line_items: Record<string, unknown>[];
    validation_result: { status?: string };
    confidence_scores?: Record<string, number>;
    processing_time_seconds: number;
  }>("/invoices/upload", {
    method: "POST",
    body: formData,
  });

  // Map validation status
  let validationStatus: "valid" | "warning" | "error" = "valid";
  const vs = (result.validation_result?.status || "").toString().toUpperCase();
  if (vs.includes("ERROR") || vs.includes("FAIL")) validationStatus = "error";
  else if (vs.includes("WARN")) validationStatus = "warning";

  return {
    id: result.session_id,
    session_id: result.session_id,
    invoiceNumber: String(result.invoice_data?.Invoice_No || ""),
    seller: String(result.invoice_data?.Seller_Name || ""),
    gstAmount: Number(result.invoice_data?.Total_GST || 0),
    total: Number(result.invoice_data?.Invoice_Value || 0),
    validationStatus,
    date: String(result.invoice_data?.Invoice_Date || new Date().toISOString().slice(0, 10)),
    invoice_data: result.invoice_data,
    line_items: result.line_items,
    confidence_scores: result.confidence_scores || undefined,
  };
}

/**
 * processInvoice is no longer needed as a separate step.
 * The upload endpoint does OCR + parsing in one call.
 * Kept for backward compatibility - returns the last upload result.
 */
export async function processInvoice(): Promise<MockInvoice> {
  // In the real API, processing happens during upload.
  // This is a no-op that returns a placeholder.
  // The dashboard should use the result from uploadInvoice directly.
  return {
    id: "pending",
    session_id: "pending",
    invoiceNumber: "",
    seller: "",
    gstAmount: 0,
    total: 0,
    validationStatus: "valid",
    date: new Date().toISOString().slice(0, 10),
    invoice_data: {},
    line_items: [],
  };
}

export async function confirmInvoice(sessionId: string): Promise<{ message: string; invoice_no: string }> {
  return apiJson(`/invoices/${sessionId}/confirm`, { method: "POST" });
}

export async function correctInvoice(
  sessionId: string,
  corrections: Record<string, string>
): Promise<MockInvoice> {
  const result = await apiJson<{
    session_id: string;
    invoice_data: Record<string, unknown>;
    line_items: Record<string, unknown>[];
    validation_result: { status?: string };
  }>(`/invoices/${sessionId}/correct`, {
    method: "POST",
    body: JSON.stringify({ corrections }),
  });

  return {
    id: result.session_id,
    session_id: result.session_id,
    invoiceNumber: String(result.invoice_data?.Invoice_No || ""),
    seller: String(result.invoice_data?.Seller_Name || ""),
    gstAmount: Number(result.invoice_data?.Total_GST || 0),
    total: Number(result.invoice_data?.Invoice_Value || 0),
    validationStatus: "valid",
    date: String(result.invoice_data?.Invoice_Date || ""),
    invoice_data: result.invoice_data,
    line_items: result.line_items,
  };
}

// ── Order functions (same interface as mockApi) ──────────────────

let _currentOrderId: string | null = null;

export async function uploadOrder(files: File[], format: "PDF" | "CSV"): Promise<{ success: boolean }> {
  _currentOrderFormat = format;

  // Step 1: Create order session
  const session = await apiJson<{ order_id: string }>("/orders", { method: "POST" });
  _currentOrderId = session.order_id;

  // Step 2: Add pages
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  await apiJson(`/orders/${_currentOrderId}/pages`, {
    method: "POST",
    body: formData,
  });

  return { success: true };
}

let _currentOrderFormat: "PDF" | "CSV" = "PDF";

export async function processOrder(format?: "PDF" | "CSV"): Promise<MockOrder> {
  if (!_currentOrderId) throw new Error("No active order session");

  const fmt = format || _currentOrderFormat;

  const result = await apiJson<{
    order_id: string;
    status: string;
    customer_name?: string;
    order_date?: string;
    total_items: number;
    total_quantity: number;
    subtotal: number;
    unmatched_count: number;
    line_items: Record<string, unknown>[];
    pdf_available: boolean;
    processing_time_seconds: number;
  }>(`/orders/${_currentOrderId}/submit?output_format=${fmt.toLowerCase()}`, { method: "POST" });

  const orderId = _currentOrderId;
  _currentOrderId = null;

  return {
    id: orderId,
    orderId: result.order_id.slice(0, 8).toUpperCase(),
    items: result.total_items,
    totalQuantity: result.total_quantity,
    subtotal: result.subtotal,
    total: result.subtotal,
    format: fmt,
    date: result.order_date || new Date().toISOString().slice(0, 10),
    line_items: result.line_items,
  };
}

export function getOrderPdfUrl(orderId: string): string {
  return `${API_BASE}/orders/${orderId}/pdf`;
}

/**
 * Download an order output file (PDF or CSV) via authenticated fetch,
 * then trigger a browser download dialog.
 */
export async function downloadOrderFile(orderId: string): Promise<void> {
  const res = await apiFetch(`/orders/${orderId}/download`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.detail || err.error || `Download failed (${res.status})`);
  }

  const blob = await res.blob();

  // Extract filename from Content-Disposition header
  const disposition = res.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/);

  // Determine file extension from Content-Type if Content-Disposition is unavailable
  let filename = filenameMatch?.[1];
  if (!filename) {
    const contentType = res.headers.get("Content-Type") || "";
    const ext = contentType.includes("csv") ? "csv" : "pdf";
    filename = `order_${orderId.slice(0, 8)}.${ext}`;
  }

  // Trigger browser download
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Report functions ─────────────────────────────────────────────

export async function generateReport(
  month: number,
  year: number,
  type: string
): Promise<{ url: string; name: string }> {
  const isGstr3b = type.toLowerCase().includes("3b");
  const endpoint = isGstr3b ? "/exports/gstr3b" : "/exports/gstr1";
  const ext = isGstr3b ? "txt" : "json";
  const name = `GST_Report_${type}_${month}_${year}.${ext}`;

  try {
    await apiJson(`${endpoint}?month=${month}&year=${year}`);
    return {
      url: `${endpoint}/download?month=${month}&year=${year}`,
      name,
    };
  } catch {
    return { url: "#", name };
  }
}

/**
 * Download a generated report (GSTR-1 or GSTR-3B) via authenticated fetch.
 */
export async function downloadReport(downloadPath: string, filename: string): Promise<void> {
  const res = await apiFetch(downloadPath);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.detail || err.error || `Download failed (${res.status})`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── History functions ────────────────────────────────────────────

export async function fetchHistory(type?: "invoice" | "order"): Promise<MockHistoryItem[]> {
  try {
    // Fetch invoices for current month
    const now = new Date();
    const invoices = await apiJson<{
      invoices: Record<string, unknown>[];
    }>(`/invoices?month=${now.getMonth() + 1}&year=${now.getFullYear()}`);

    const items: MockHistoryItem[] = invoices.invoices.map((inv, i) => ({
      id: String(i),
      type: "invoice" as const,
      reference: String(inv.Invoice_No || `INV-${i}`),
      date: String(inv.Invoice_Date || ""),
      status: String(inv.Validation_Status || "Processed"),
      amount: Number(inv.Invoice_Value || 0),
    }));

    if (type === "invoice") return items;
    if (type === "order") return []; // Orders are session-based, not persisted in query yet
    return items;
  } catch {
    return [];
  }
}

// ── Usage stats ──────────────────────────────────────────────────

export type TierId = "free" | "starter" | "pro" | "power";

export async function getUsageStats(): Promise<{
  invoicesUsed: number;
  invoicesLimit: number;
  ordersUsed: number;
  tier: TierId;
}> {
  try {
    const profile = await apiGetProfile();
    return {
      invoicesUsed: profile.invoice_count,
      invoicesLimit: 50, // Default limit - can be made dynamic later
      ordersUsed: profile.order_count,
      tier: "starter" as TierId, // Can be mapped from subscription tier later
    };
  } catch {
    // Fallback if not authenticated
    return {
      invoicesUsed: 0,
      invoicesLimit: 50,
      ordersUsed: 0,
      tier: "free",
    };
  }
}

// ── Order processing step labels (same as mockApi) ───────────────

export const ORDER_PROCESS_STEPS = [
  "Extracting order",
  "Normalizing part names and colors",
  "Processing all items",
  "Matching prices",
  "Computing totals",
  "Generating file",
] as const;
