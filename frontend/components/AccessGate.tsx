"use client";

import { FormEvent, ReactNode, useState } from "react";
import { BrandHeader } from "@/components/BrandHeader";
import { getAccessToken, setAccessToken } from "@/lib/api";

export function AccessGate({ children }: { children: ReactNode }) {
  const [unlocked, setUnlocked] = useState(() => Boolean(getAccessToken()));
  const [token, setToken] = useState("");

  function unlock(event: FormEvent) {
    event.preventDefault();
    const value = token.trim();
    if (!value) return;
    setAccessToken(value);
    setUnlocked(true);
  }

  if (unlocked) return children;

  return (
    <div className="page-shell access-page">
      <BrandHeader />
      <main className="access-card">
        <span className="mini-label">PRIVATE WORKSPACE</span>
        <h1>进入完整工作台</h1>
        <p>真实上传、历史数据和模型调用受访问密码保护。密码只保存在当前浏览器标签页中。</p>
        <form onSubmit={unlock}>
          <label className="field"><span>访问密码</span><input type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="current-password" required /></label>
          <button className="button button-primary" type="submit">继续</button>
        </form>
      </main>
    </div>
  );
}
