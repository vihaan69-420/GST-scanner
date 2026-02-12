import { create } from "zustand";
import type { TierId } from "@/lib/tiers";

export type ChatMessageRole = "bot" | "user";
export type ChatMessageType = "text" | "action" | "upload" | "progress" | "result" | "menu";

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  type: ChatMessageType;
  content: string;
  payload?: unknown;
  /** For bot messages: action IDs for buttons e.g. "upload-invoice" | "upload-order" | "generate-report" | "help" | "usage" */
  buttons?: { label: string; action: string }[];
  timestamp: number;
}

export type SidebarSection = "chat" | "history-reports" | "help" | "settings";

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
}

export interface ProgressStep {
  label: string;
  status: "pending" | "active" | "done";
}

interface AppState {
  activeSection: SidebarSection;
  setActiveSection: (s: SidebarSection) => void;

  messages: ChatMessage[];
  addMessage: (msg: Omit<ChatMessage, "id" | "timestamp">) => void;
  clearMessages: () => void;

  uploadedFiles: UploadedFile[];
  setUploadedFiles: (files: UploadedFile[]) => void;
  addUploadedFile: (file: UploadedFile) => void;

  progressSteps: ProgressStep[];
  setProgressSteps: (steps: ProgressStep[]) => void;
  setStepStatus: (index: number, status: ProgressStep["status"]) => void;

  hasActiveSession: boolean;
  setHasActiveSession: (v: boolean) => void;

  usageStats: { invoicesUsed: number; invoicesLimit: number; ordersUsed: number; tier: TierId } | null;
  setUsageStats: (s: AppState["usageStats"]) => void;

  /** Current user tier for limit enforcement (mock; can be set from usageStats). */
  userTier: TierId;
  setUserTier: (t: TierId) => void;

  contextPanelOpen: boolean;
  setContextPanelOpen: (v: boolean) => void;

  /** Mobile: sidebar open/closed (hamburger). */
  sidebarOpen: boolean;
  setSidebarOpen: (v: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeSection: "chat",
  setActiveSection: (activeSection) => set({ activeSection }),

  messages: [],
  addMessage: (msg) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...msg,
          id: "msg-" + Date.now() + "-" + Math.random().toString(36).slice(2),
          timestamp: Date.now(),
        },
      ],
    })),
  clearMessages: () => set({ messages: [] }),

  uploadedFiles: [],
  setUploadedFiles: (uploadedFiles) => set({ uploadedFiles }),
  addUploadedFile: (file) =>
    set((state) => ({
      uploadedFiles: [...state.uploadedFiles, file],
    })),

  progressSteps: [],
  setProgressSteps: (progressSteps) => set({ progressSteps }),
  setStepStatus: (index, status) =>
    set((state) => ({
      progressSteps: state.progressSteps.map((s, i) =>
        i === index ? { ...s, status } : i < index ? { ...s, status: "done" as const } : s
      ),
    })),

  hasActiveSession: false,
  setHasActiveSession: (hasActiveSession) => set({ hasActiveSession }),

  usageStats: null,
  setUsageStats: (usageStats) => set({ usageStats }),

  userTier: "starter",
  setUserTier: (userTier) => set({ userTier }),

  contextPanelOpen: true,
  setContextPanelOpen: (contextPanelOpen) => set({ contextPanelOpen }),

  sidebarOpen: false,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
}));
