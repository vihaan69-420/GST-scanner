"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";

interface FilePreviewCardsProps {
  files: File[];
  onRemove?: (index: number) => void;
}

export default function FilePreviewCards({ files, onRemove }: FilePreviewCardsProps) {
  return (
    <div className="flex flex-wrap gap-3">
      {files.map((file, i) => (
        <FileCard key={i} file={file} onRemove={onRemove ? () => onRemove(i) : undefined} />
      ))}
    </div>
  );
}

function FileCard({ file, onRemove }: { file: File; onRemove?: () => void }) {
  const [preview, setPreview] = useState<string | null>(null);
  const isImage = file.type.startsWith("image/");

  useEffect(() => {
    if (!isImage) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file, isImage]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex overflow-hidden rounded-xl border border-[var(--glass-border)] bg-[var(--card)] shadow-[var(--shadow-soft)]"
    >
      <div className="h-20 w-20 shrink-0 bg-[var(--background)]">
        {preview ? (
          <img src={preview} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[var(--muted)]">
            <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col justify-center px-3 py-2">
        <p className="truncate text-sm font-medium text-[var(--foreground)]">{file.name}</p>
        <p className="text-xs text-[var(--muted)]">{(file.size / 1024).toFixed(1)} KB</p>
      </div>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="shrink-0 p-2 text-[var(--muted)] hover:text-[var(--foreground)]"
          aria-label="Remove"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </motion.div>
  );
}
