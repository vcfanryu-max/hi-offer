"use client";

import Link from "next/link";
import { PointerEvent, useRef } from "react";

export function Hero() {
  const ref = useRef<HTMLDivElement>(null);

  function move(event: PointerEvent<HTMLDivElement>) {
    const box = ref.current?.getBoundingClientRect();
    if (!box || !ref.current) return;
    ref.current.style.setProperty("--pointer-x", `${event.clientX - box.left}px`);
    ref.current.style.setProperty("--pointer-y", `${event.clientY - box.top}px`);
    ref.current.style.setProperty("--tilt-x", `${((event.clientX - box.left) / box.width - 0.5) * 5}px`);
  }

  return (
    <main className="landing-main">
      <div ref={ref} className="hero-stage" onPointerMove={move}>
        <div className="hero-orbit" aria-hidden="true" />
        <h1 className="hero-title">
          Resume Matcher
        </h1>
      </div>
      <p className="hero-statement">简历与岗位的证据匹配，在你的电脑上完成。</p>
      <div className="hero-actions">
        <Link className="button button-primary" href="/workspace">
          开始
        </Link>
        <Link className="button button-secondary" href="/profile">
          用户档案
        </Link>
      </div>
    </main>
  );
}
