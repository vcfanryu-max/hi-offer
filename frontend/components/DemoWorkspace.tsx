"use client";
import { BrandHeader } from "./BrandHeader";
import { ResultSections } from "./ResultSections";
import { demoGeneration } from "@/lib/demo-data";

export function DemoWorkspace() {
  return <div className="page-shell workspace-page">
    <BrandHeader action={{ href: "https://github.com/vcfanryu-max/hi-offer", label: "GitHub 源码" }} />
    <main className="workspace-main">
      <header className="workspace-intro"><h1>作品集<br />交互演示。</h1><p>这是一份由虚构简历与虚构岗位生成的安全样例，展示完整的匹配分析、HR 话术和简历建议。</p></header>
      <aside className="privacy-note demo-note">DEMO MODE · 不上传文件、不收集个人信息、不连接付费模型。完整 FastAPI、OCR 与结构化输出实现可在 GitHub 查看。</aside>
      <section className="material-grid demo-materials" aria-label="演示输入">
        <article className="work-panel"><header><span className="panel-number">01</span><div><h2>示例简历</h2><p>虚构候选人 · Resume V3</p></div></header><div className="current-file"><div><strong>{demoGeneration.resume_filename}</strong><span>React · TypeScript · Design System</span></div></div></article>
        <article className="work-panel"><header><span className="panel-number">02</span><div><h2>示例岗位</h2><p>虚构招聘需求</p></div></header><div className="current-file"><div><strong>{demoGeneration.position}</strong><span>{demoGeneration.company}</span></div></div></article>
      </section>
      <ResultSections generation={demoGeneration} retrying={null} onRetry={() => undefined} demo />
    </main>
  </div>;
}

