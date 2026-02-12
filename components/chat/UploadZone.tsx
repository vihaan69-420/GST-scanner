"use client";

import { useCallback, useRef } from "react";
import { motion } from "framer-motion";
import { useAppStore } from "@/store/appStore";

interface UploadZoneProps {
  onFilesSelected?: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
}

export default function UploadZone({
  onFilesSelected,
  accept = "image/*,.pdf",
  multiple = true,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const addUploadedFile = useAppStore((s) => s.addUploadedFile);
  const setHasActiveSession = useAppStore((s) => s.setHasActiveSession);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const files = Array.from(e.dataTransfer.files);
      if (files.length) {
        setHasActiveSession(true);
        files.forEach((f) =>
          addUploadedFile({
            id: "f-" + Date.now() + "-" + Math.random().toString(36).slice(2),
            name: f.name,
            size: f.size,
            type: f.type,
          })
        );
        onFilesSelected?.(files);
      }
    },
    [addUploadedFile, setHasActiveSession, onFilesSelected]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      if (files.length) {
        setHasActiveSession(true);
        files.forEach((f) =>
          addUploadedFile({
            id: "f-" + Date.now() + "-" + Math.random().toString(36).slice(2),
            name: f.name,
            size: f.size,
            type: f.type,
          })
        );
        onFilesSelected?.(files);
      }
      e.target.value = "";
    },
    [addUploadedFile, setHasActiveSession, onFilesSelected]
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className="cursor-pointer rounded-2xl border-2 border-dashed border-[var(--primary)]/30 bg-[var(--primary)]/5 p-8 text-center transition hover:border-[var(--primary)]/50 hover:bg-[var(--primary)]/10"
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleChange}
        className="hidden"
      />
      <p className="text-sm font-medium text-[var(--foreground)]">Drop files here or click to upload</p>
      <p className="mt-1 text-xs text-[var(--muted)]">Images or PDF</p>
    </motion.div>
  );
}
