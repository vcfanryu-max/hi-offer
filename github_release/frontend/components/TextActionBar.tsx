"use client";

import { useState } from "react";

function downloadText(text: string, filename: string, mime: string) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

async function copyText(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const input = document.createElement("textarea");
  input.value = text;
  input.setAttribute("readonly", "");
  input.style.position = "fixed";
  input.style.opacity = "0";
  document.body.appendChild(input);
  input.select();
  const copied = document.execCommand("copy");
  input.remove();
  if (!copied) throw new Error("copy unavailable");
}

export function TextActionBar({
  text,
  filename,
  mime = "text/plain;charset=utf-8",
}: {
  text: string;
  filename: string;
  mime?: string;
}) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

  async function copy() {
    try {
      await copyText(text);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 2500);
    } catch {
      setCopyState("error");
    }
  }

  return (
    <div className="action-bar" aria-live="polite">
      <button className="text-button" onClick={copy} disabled={!text}>
        {copyState === "copied" ? "✓ 已复制" : copyState === "error" ? "复制失败" : "复制"}
      </button>
      <button className="text-button" onClick={() => downloadText(text, filename, mime)} disabled={!text}>
        下载
      </button>
    </div>
  );
}
