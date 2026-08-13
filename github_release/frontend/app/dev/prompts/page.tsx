"use client";

import { FormEvent, useEffect, useState } from "react";
import { BrandHeader } from "@/components/BrandHeader";
import { TextActionBar } from "@/components/TextActionBar";
import { request } from "@/lib/api";
import type { Job, ResumeVersion } from "@/lib/types";

type PromptResult = { prompt_content: string; raw_output: string; parsed_output: unknown; validation_error: string | null; latency_ms: number; model: string; prompt_version: string };
type PromptCatalog = { tasks: { id: string; versions: string[]; content: string }[] };

export default function PromptLabPage() {
  const [resumes, setResumes] = useState<ResumeVersion[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [resumeId, setResumeId] = useState(0);
  const [jobId, setJobId] = useState(0);
  const [task, setTask] = useState("hr_message");
  const [catalog, setCatalog] = useState<PromptCatalog["tasks"]>([]);
  const [promptVersion, setPromptVersion] = useState("v2");
  const [temperature, setTemperature] = useState(0.2);
  const [result, setResult] = useState<PromptResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [debugAvailable, setDebugAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    Promise.all([
      request<{ debug: boolean }>("/api/health"),
      request<{ items: ResumeVersion[] }>("/api/resumes"),
      request<{ items: Job[] }>("/api/jobs"),
      request<PromptCatalog>("/api/dev/prompts"),
    ]).then(([health, resumeData, jobData, promptData]) => {
      setDebugAvailable(health.debug);
      setResumes(resumeData.items); setJobs(jobData.items);
      setCatalog(promptData.tasks);
      setResumeId(resumeData.items[0]?.id ?? 0); setJobId(jobData.items[0]?.id ?? 0);
    }).catch((reason: Error) => { setDebugAvailable(false); setError("Prompt Lab 仅在 DEBUG=true 时开放。"); });
  }, []);

  async function run(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      setResult(await request<PromptResult>("/api/dev/prompts/run", { method: "POST", body: JSON.stringify({ task, prompt_version: promptVersion, resume_version_id: resumeId, job_id: jobId, temperature }) }));
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <div className="page-shell prompt-lab-page">
      <BrandHeader action={{ href: "/workspace", label: "返回工作台" }} />
      <main className="prompt-lab-main">
        <header className="bilingual-title"><span>DEVELOPER ONLY</span><h1>Prompt Lab</h1><p>普通导航不会展示此页。每次运行都从磁盘读取当前 Prompt。</p></header>
        {error && <div className="notice notice-error">{error}</div>}
        {debugAvailable === false ? null : <>
        <form className="prompt-controls" onSubmit={run}>
          <label className="field"><span>Resume</span><select value={resumeId} onChange={(event) => setResumeId(Number(event.target.value))}>{resumes.map((item) => <option value={item.id} key={item.id}>{item.label} · {item.original_filename}</option>)}</select></label>
          <label className="field"><span>JD</span><select value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>{jobs.map((item) => <option value={item.id} key={item.id}>#{item.id} · {item.position}</option>)}</select></label>
          <label className="field"><span>Task</span><select value={task} onChange={(event) => { const next = event.target.value; setTask(next); const versions=catalog.find((item) => item.id === next)?.versions ?? ["v1"]; setPromptVersion(versions[versions.length - 1]); }}><option value="resume_structure">Resume Structure</option><option value="jd_analysis">JD Analysis</option><option value="match_analysis">Match Analysis</option><option value="hr_message">HR Message</option><option value="resume_advice">Resume Advice</option></select></label>
          <label className="field"><span>Prompt Version</span><select value={promptVersion} onChange={(event) => setPromptVersion(event.target.value)}>{(catalog.find((item) => item.id === task)?.versions ?? ["v1"]).map((version) => <option value={version} key={version}>{version}</option>)}</select></label>
          <label className="field"><span>Temperature</span><input type="number" min="0" max="1" step="0.1" value={temperature} onChange={(event) => setTemperature(Number(event.target.value))} /></label>
          <button className="button button-primary" disabled={busy || !resumeId || !jobId}>{busy ? "正在运行…" : "Run"}</button>
        </form>
        {result && <section className="prompt-results"><article><header><h2>Prompt Content</h2><TextActionBar text={result.prompt_content} filename={`${task}_${result.prompt_version}.md`} mime="text/markdown;charset=utf-8" /></header><pre>{result.prompt_content}</pre></article><article><header><h2>Parsed Output</h2><TextActionBar text={result.raw_output} filename={`${task}_output.json`} mime="application/json;charset=utf-8" /></header><pre>{result.raw_output}</pre><footer>{result.latency_ms} ms · {result.model} · {result.prompt_version}</footer></article></section>}
        </>}
      </main>
    </div>
  );
}
