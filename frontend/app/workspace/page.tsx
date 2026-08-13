"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { BrandHeader } from "@/components/BrandHeader";
import { FileDropzone } from "@/components/FileDropzone";
import { ResultSections } from "@/components/ResultSections";
import { DemoWorkspace } from "@/components/DemoWorkspace";
import { api, downloadUrl } from "@/lib/api";
import type { ApiConfig, Generation, Job, ResumeVersion } from "@/lib/types";

const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

const providerDefaults: Record<string, { model: string; base_url: string }> = {
  DeepSeek: { model: "deepseek-chat", base_url: "https://api.deepseek.com" },
  OpenAI: { model: "gpt-5-mini", base_url: "https://api.openai.com/v1" },
  Custom: { model: "", base_url: "" },
};

function LiveWorkspace() {
  const [resume, setResume] = useState<ResumeVersion | null>(null);
  const [config, setConfig] = useState<ApiConfig | null>(null);
  const [jdMode, setJdMode] = useState<"text" | "file">("text");
  const [jdText, setJdText] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [generation, setGeneration] = useState<Generation | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [provider, setProvider] = useState("DeepSeek");
  const [model, setModel] = useState(providerDefaults.DeepSeek.model);
  const [baseUrl, setBaseUrl] = useState(providerDefaults.DeepSeek.base_url);
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    const snapshotId = Number(new URLSearchParams(window.location.search).get("generation"));
    const snapshotRequest = Number.isInteger(snapshotId) && snapshotId > 0
      ? api.generation(snapshotId)
      : Promise.resolve(null);
    const jobsRequest = api.jobs();
    Promise.all([api.currentResume(), api.config(), snapshotRequest, jobsRequest])
      .then(([resumeData, configData, snapshot, jobsData]) => {
        setResume(resumeData.item);
        setConfig(configData);
        setGeneration(snapshot);
        const restoredJob = snapshot
          ? jobsData.items.find((item) => item.id === snapshot.job_id) ?? null
          : jobsData.items[0] ?? null;
        if (restoredJob) {
          setJob(restoredJob);
          setJdText(restoredJob.jd_text);
          setJdMode(restoredJob.source_type === "file" ? "file" : "text");
        }
        if (configData.provider) {
          setProvider(configData.provider);
          setModel(configData.model);
          setBaseUrl(configData.base_url);
        }
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  const canGenerate = useMemo(
    () => Boolean(resume && config?.is_configured && (job || jdText.trim().length > 0) && !busy),
    [resume, config, job, jdText, busy],
  );

  async function uploadResume(file: File) {
    setBusy("resume"); setError(null);
    try { const value = await api.uploadResume(file); setResume(value); setNotice(value.ocr_used ? "图片文字已在本机识别，新简历版本已保存。" : "新简历版本已保存并设为当前版本。"); }
    catch (reason) { setError((reason as Error).message); }
    finally { setBusy(null); }
  }

  async function uploadJob(file: File) {
    setBusy("job"); setError(null);
    try { const value = await api.uploadJob(file); setJob(value); setJdText(value.jd_text); setNotice(value.ocr_used ? "JD 图片文字已在本机识别并保存。" : "JD 原文件和解析文本已保存到本地。"); }
    catch (reason) { setError((reason as Error).message); }
    finally { setBusy(null); }
  }

  async function saveConfig(event: FormEvent) {
    event.preventDefault(); setBusy("config"); setError(null); setApiError(null);
    try {
      const value = await api.saveConfig({ provider, model, base_url: baseUrl, api_key: apiKey });
      setConfig(value);
      setApiKey("");
      setNotice(value.key_persisted ? "模型配置已安全保存到本机。" : "配置已生效；Windows 凭据库当前不可用，API Key 仅在本次后端运行期间有效。");
    } catch (reason) { setApiError((reason as Error).message); }
    finally { setBusy(null); }
  }

  async function testConfig() {
    setBusy("test"); setError(null); setApiError(null);
    try { const value = await api.testConfig(); setNotice(value.message); }
    catch (reason) { setApiError((reason as Error).message); }
    finally { setBusy(null); }
  }

  async function deleteConfig() {
    if (!window.confirm("删除这台电脑上保存的 API Key？Provider 和 Model 可重新配置。")) return;
    setBusy("delete-config"); setError(null); setApiError(null);
    try {
      await api.deleteConfig();
      setConfig(await api.config());
      setApiKey("");
      setNotice("本地 API Key 已删除。");
    } catch (reason) { setApiError((reason as Error).message); }
    finally { setBusy(null); }
  }

  async function generate() {
    if (!resume || !canGenerate) return;
    setBusy("generate"); setError(null); setNotice(null);
    try {
      const activeJob = job ?? (await api.createJobText(jdText));
      setJob(activeJob);
      setGeneration(await api.generate(resume.id, activeJob.id));
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(null); }
  }

  async function retry(module: "match" | "hr-message" | "resume-advice") {
    if (!generation) return;
    setRetrying(module); setError(null);
    try { setGeneration(await api.retry(generation.id, module)); }
    catch (reason) { setError((reason as Error).message); }
    finally { setRetrying(null); }
  }

  if (loading) return <div className="page-shell"><BrandHeader action={{ href: "/profile", label: "用户档案" }} /><main className="loading-page">正在打开本地工作台…</main></div>;

  return (
    <div className="page-shell workspace-page">
      <BrandHeader action={{ href: "/profile", label: "用户档案" }} />
      <main className="workspace-main">
        <header className="workspace-intro">
          <h1>上传材料，<br />一键生成。</h1>
          <p>选择当前简历，提供岗位 JD，接入你自己的模型 API。匹配分析、HR 话术和简历建议会作为一次快照保存在本地。</p>
        </header>

        <aside className="privacy-note">本次填写只为记录个人求职材料并生成本次分析，不涉及自动投递、联系招聘方或向其他用户公开。模型生成时，简历与 JD 会直接发送给你选择的第三方 AI Provider。</aside>
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {notice && <div className="notice" aria-live="polite">{notice}</div>}

        <section className="material-grid">
          <article className="work-panel resume-panel">
            <header><span className="panel-number">01</span><div><h2>简历</h2><p>使用当前版本，或上传一个新版本。</p></div></header>
            {resume ? (
              <div className="current-file">
                <div><strong>{resume.original_filename}</strong><span>{resume.label} · 当前</span></div>
                <a className="text-button" href={downloadUrl(`/api/resumes/versions/${resume.id}/download`)}>下载原文件</a>
              </div>
            ) : <div className="empty-inline">尚未上传简历。</div>}
            <FileDropzone accept=".pdf,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp" label={resume ? "上传新版本" : "上传简历"} hint="PDF / DOCX / TXT / MD / PNG / JPG / WEBP · 最大 12 MB" busy={busy === "resume"} onFile={uploadResume} />
          </article>

          <article className="work-panel job-panel">
            <header><span className="panel-number">02</span><div><h2>岗位 JD</h2><p>粘贴正文，或上传原始文件。</p></div></header>
            <div className="segmented" role="tablist" aria-label="JD 输入方式">
              <button className={jdMode === "text" ? "is-active" : ""} onClick={() => { setJdMode("text"); setJob(null); }}>粘贴文本</button>
              <button className={jdMode === "file" ? "is-active" : ""} onClick={() => setJdMode("file")}>上传文件</button>
            </div>
            {jdMode === "text" ? (
              <label className="field"><span>JD 正文</span><textarea value={jdText} onChange={(event) => { setJdText(event.target.value); setJob(null); }} placeholder="粘贴岗位职责与任职要求" /><small>{jdText.trim() ? `${jdText.length.toLocaleString()} 字符 · 不做静默截断，长 JD 会自动分段分析` : "粘贴任意长度的有效 JD 内容"}</small></label>
            ) : (
              <>
                <FileDropzone accept=".pdf,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp" label="拖入或选择 JD 文件" hint="PDF / DOCX / TXT / MD / PNG / JPG / WEBP · 最大 12 MB" busy={busy === "job"} onFile={uploadJob} />
                {job && <div className="current-file"><div><strong>{job.original_filename}</strong><span>{job.ocr_used ? "本地 OCR 已完成并保存" : "已解析并保存"}</span></div><a className="text-button" href={downloadUrl(`/api/jobs/${job.id}/download`)}>下载原文件</a></div>}
              </>
            )}
          </article>
        </section>

        <details className="api-panel" open={!config?.is_configured}>
          <summary>
            <div><span className="panel-number">03</span><span>模型 API</span></div>
            <span className={config?.is_configured ? "status-ok" : "status-muted"}>{config?.is_configured ? `${config.provider} · ${config.model} · 已配置` : "尚未配置"}</span>
          </summary>
          <form className="api-form" onSubmit={saveConfig}>
            <label className="field"><span>Provider</span><select value={provider} onChange={(event) => { const value = event.target.value; setProvider(value); setModel(providerDefaults[value].model); setBaseUrl(providerDefaults[value].base_url); }}><option>DeepSeek</option><option>OpenAI</option><option>Custom</option></select></label>
            <label className="field"><span>Model</span><input value={model} onChange={(event) => setModel(event.target.value)} placeholder="模型名称" required /></label>
            {provider === "Custom" && <label className="field"><span>Base URL</span><input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" required /></label>}
            <label className="field"><span>API Key</span><input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={config?.is_configured ? "已保存；填写新 Key 可替换" : "只写入操作系统凭据库"} required={!config?.is_configured} autoComplete="off" /></label>
            <div className="api-actions"><button className="button button-primary" type="submit" disabled={busy === "config"}>{busy === "config" ? "正在保存…" : "本地保存"}</button><button className="button button-secondary" type="button" onClick={testConfig} disabled={!config?.is_configured || busy === "test"}>{busy === "test" ? "正在测试…" : "测试连接"}</button>{config?.is_configured && <button className="text-button" type="button" onClick={deleteConfig} disabled={busy === "delete-config"}>{busy === "delete-config" ? "正在删除…" : "删除本地 Key"}</button>}</div>
            {apiError && <p className="api-feedback" role="alert">{apiError}</p>}
            {config?.is_configured && !config.key_persisted && <p className="key-warning">系统凭据库不可用；Key 仅在本次后端运行期间有效。</p>}
          </form>
        </details>

        <button className="generate-button" onClick={generate} disabled={!canGenerate} aria-busy={busy === "generate"}>
          {busy === "generate" ? "正在完成结构化与三项独立分析…" : "一键生成"}
        </button>
        {!canGenerate && !busy && <p className="generate-helper">需要当前简历、非空 JD，以及已保存的 API 配置。</p>}

        {generation && <ResultSections generation={generation} retrying={retrying} onRetry={retry} />}
      </main>
    </div>
  );
}

export default function WorkspacePage() {
  return DEMO_MODE ? <DemoWorkspace /> : <LiveWorkspace />;
}
