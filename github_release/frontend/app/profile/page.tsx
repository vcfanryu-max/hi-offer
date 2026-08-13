"use client";

import { useEffect, useState } from "react";
import { BrandHeader } from "@/components/BrandHeader";
import { FileDropzone } from "@/components/FileDropzone";
import { TextActionBar } from "@/components/TextActionBar";
import { api, downloadUrl } from "@/lib/api";
import { formatAdvice, formatMatch } from "@/lib/format";
import type { ApiConfig, Generation, ResumeVersion } from "@/lib/types";

function date(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

export default function ProfilePage() {
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [config, setConfig] = useState<ApiConfig | null>(null);
  const [records, setRecords] = useState<Generation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Generation | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [resumeData, configData, historyData] = await Promise.all([api.resumes(), api.config(), api.generations()]);
      setVersions(resumeData.items); setConfig(configData); setRecords(historyData.items);
      if (!selectedId && historyData.items[0]) setSelectedId(historyData.items[0].id);
    } catch (reason) { setError((reason as Error).message); }
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!selectedId) { setSelected(null); return; }
    setBusy("history");
    api.generation(selectedId).then(setSelected).catch((reason: Error) => setError(reason.message)).finally(() => setBusy(null));
  }, [selectedId]);

  async function upload(file: File) {
    setBusy("upload"); setError(null);
    try { await api.uploadResume(file); await load(); }
    catch (reason) { setError((reason as Error).message); }
    finally { setBusy(null); }
  }

  async function makeCurrent(id: number) {
    setBusy(`resume-${id}`); setError(null);
    try { await api.setCurrentResume(id); await load(); }
    catch (reason) { setError((reason as Error).message); }
    finally { setBusy(null); }
  }

  const current = versions.find((item) => item.is_current) ?? null;
  const matchText = selected?.match_result ? formatMatch(selected.match_result) : "";
  const adviceText = selected?.resume_advice ? formatAdvice(selected.resume_advice, selected) : "";

  return (
    <div className="page-shell profile-page">
      <BrandHeader action={{ href: "/workspace", label: "开始" }} />
      <main className="profile-main">
        <header className="bilingual-title">
          <span>USER PROFILE</span><h1>用户档案</h1>
          <p>简历版本、模型状态与每一次完整 Generation，只保存在这台电脑。</p>
        </header>
        {error && <div className="notice notice-error" role="alert">{error}</div>}

        <section className="profile-top-grid">
          <article className="resume-archive">
            <header className="section-heading"><div><h2>简历版本</h2><span>RESUME VERSIONS</span></div><span>{versions.length} 个版本</span></header>
            {current ? (
              <div className="current-resume-large">
                <span className="version-mark">V{current.version_number}</span>
                <div><strong>{current.original_filename}</strong><span>{date(current.created_at)} · 当前使用{current.ocr_used ? " · 本地 OCR" : ""}</span></div>
                <a className="text-button" href={downloadUrl(`/api/resumes/versions/${current.id}/download`)}>下载原文件</a>
              </div>
            ) : <div className="empty-state"><strong>尚未上传简历</strong><span>上传后会创建 Resume V1。</span></div>}
            <FileDropzone accept=".pdf,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp" label="上传新版本" hint="旧版本不会被覆盖 · 图片会在本机 OCR" busy={busy === "upload"} onFile={upload} />
            <div className="version-list">
              {versions.filter((item) => !item.is_current).map((item) => (
                <div className="version-row" key={item.id}>
                  <span className="version-mark small">V{item.version_number}</span>
                  <div><strong>{item.original_filename}</strong><span>{date(item.created_at)}{item.ocr_used ? " · OCR" : ""}</span></div>
                  <div className="row-actions"><button className="text-button" onClick={() => makeCurrent(item.id)} disabled={busy === `resume-${item.id}`}>设为当前</button><a className="text-button" href={downloadUrl(`/api/resumes/versions/${item.id}/download`)}>下载</a></div>
                </div>
              ))}
            </div>
          </article>

          <aside className="api-status-panel">
            <span className="mini-label">API CONFIG</span><h2>{config?.is_configured ? "模型已配置" : "尚未配置"}</h2>
            {config?.is_configured ? <><strong>{config.provider}</strong><span>{config.model}</span><span>{config.key_persisted ? "密钥由操作系统安全保存" : "密钥仅在本次运行中有效"}</span></> : <p>前往工作台填写 Provider、Model 与 API Key。</p>}
            <a className="button button-secondary" href="/workspace">{config?.is_configured ? "修改配置" : "配置 API"}</a>
          </aside>
        </section>

        <section className="history-section">
          <header className="section-heading"><div><h2>求职任务历史</h2><span>GENERATION SNAPSHOTS</span></div><span>{records.length} 条快照</span></header>
          {records.length ? (
            <div className="history-master-detail">
              <nav className="job-record-list" aria-label="Generation 记录">
                {records.map((item) => (
                  <button key={item.id} className={selectedId === item.id ? "is-active" : ""} onClick={() => setSelectedId(item.id)} aria-pressed={selectedId === item.id}>
                    <strong>{item.position}</strong><span>{item.company}</span>
                    <span>Resume V{item.resume_version_number} · {date(item.created_at)}</span><small>#{item.id}</small>
                  </button>
                ))}
              </nav>
              <article className="advice-detail generation-detail" aria-live="polite">
                {busy === "history" ? <div className="loading-inline">正在读取本地快照…</div> : selected ? (
                  <>
                    <header>
                      <div><span className="mini-label">GENERATION #{selected.id}</span><h3>{selected.position}</h3><p>{selected.company} · Resume V{selected.resume_version_number} · {selected.model}</p></div>
                      <a className="text-button" href={downloadUrl(`/api/generations/${selected.id}/export/generation`)}>下载完整 Generation</a>
                    </header>

                    <details className="snapshot-section" open>
                      <summary><strong>JD</strong><span>JOB DESCRIPTION</span></summary>
                      <div className="archive-actions"><TextActionBar text={selected.jd_text ?? ""} filename={`JD_${selected.id}.txt`} /><a className="text-button" href={downloadUrl(`/api/jobs/${selected.job_id}/download`)}>下载{selected.job_source_type === "text" ? "文本" : "原文件"}</a></div>
                      <pre>{selected.jd_text}</pre>
                    </details>

                    <details className="snapshot-section" open>
                      <summary><strong>匹配分析</strong><span>MATCH ANALYSIS</span></summary>
                      {selected.match_result ? <><TextActionBar text={matchText} filename={`Resume_Matcher_Match_${selected.id}.md`} mime="text/markdown;charset=utf-8" /><pre>{matchText}</pre></> : <p>{selected.match_error || "这次快照没有匹配分析。"}</p>}
                    </details>

                    <details className="snapshot-section" open>
                      <summary><strong>HR 话术</strong><span>HR MESSAGE</span></summary>
                      {selected.hr_message ? <><TextActionBar text={selected.hr_message.message} filename={`Resume_Matcher_HR_Message_${selected.id}.txt`} /><p>{selected.hr_message.message}</p></> : <p>{selected.hr_message_error || "这次快照没有生成话术。"}</p>}
                    </details>

                    <details className="snapshot-section" open>
                      <summary><strong>简历修改意见</strong><span>RESUME ADVICE</span></summary>
                      {selected.resume_advice ? <><TextActionBar text={adviceText} filename={`Resume_Matcher_Resume_Advice_${selected.id}.md`} mime="text/markdown;charset=utf-8" /><pre>{adviceText}</pre></> : <p>{selected.resume_advice_error || "这次快照没有修改意见。"}</p>}
                    </details>

                    <footer className="snapshot-meta">Prompt Snapshot · {Object.entries(selected.prompt_versions ?? {}).map(([key, value]) => `${key}:${value ?? "legacy"}`).join(" · ")}。历史结果不会被新 Prompt 覆盖。</footer>
                  </>
                ) : null}
              </article>
            </div>
          ) : <div className="empty-state history-empty"><strong>还没有生成记录</strong><span>完成一次 Resume × JD 后，这里会出现完整快照。</span><a className="button button-primary" href="/workspace">开始一次生成</a></div>}
        </section>
      </main>
    </div>
  );
}
