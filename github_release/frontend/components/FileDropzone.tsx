"use client";

import { useRef, useState } from "react";

export function FileDropzone({
  accept,
  label,
  hint,
  busy,
  onFile,
}: {
  accept: string;
  label: string;
  hint: string;
  busy?: boolean;
  onFile: (file: File) => Promise<void> | void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  return (
    <div
      className={`dropzone${dragging ? " is-dragging" : ""}${busy ? " is-loading" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        if (busy) return;
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        if (busy) return;
        const file = event.dataTransfer.files[0];
        if (file) void onFile(file);
      }}
      onClick={() => { if (!busy) inputRef.current?.click(); }}
      onKeyDown={(event) => {
        if (!busy && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
      role="button"
      tabIndex={busy ? -1 : 0}
      aria-busy={busy}
      aria-disabled={busy}
    >
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept={accept}
        disabled={busy}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void onFile(file);
          event.currentTarget.value = "";
        }}
      />
      <span className="dropzone-title">{busy ? "正在读取文件…" : label}</span>
      <span className="dropzone-hint">{hint}</span>
    </div>
  );
}
