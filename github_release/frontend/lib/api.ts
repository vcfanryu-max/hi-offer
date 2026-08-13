import type { ApiConfig, Generation, Job, ResumeVersion } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

function publicError(detail: unknown): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return "输入内容不符合要求，请检查文件、JD 长度和模型配置后重试。";
  }
  return "请求失败，请稍后重试。";
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("本地后端未连接。历史数据仍保存在电脑中，请启动 Backend 后重试。", 0);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "请求失败。" }));
    throw new ApiError(publicError(body.detail), response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  resumes: () => request<{ items: ResumeVersion[] }>("/api/resumes"),
  currentResume: () => request<{ item: ResumeVersion | null }>("/api/resumes/current"),
  uploadResume: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ResumeVersion>("/api/resumes/upload", { method: "POST", body: form });
  },
  setCurrentResume: (id: number) => request<ResumeVersion>(`/api/resumes/versions/${id}/current`, { method: "PATCH" }),
  createJobText: (jd_text: string) => request<Job>("/api/jobs/text", { method: "POST", body: JSON.stringify({ jd_text }) }),
  uploadJob: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Job>("/api/jobs/upload", { method: "POST", body: form });
  },
  jobs: () => request<{ items: Job[] }>("/api/jobs"),
  config: () => request<ApiConfig>("/api/settings/provider"),
  saveConfig: (value: { provider: string; model: string; base_url: string; api_key: string }) =>
    request<ApiConfig>("/api/settings/provider", { method: "PUT", body: JSON.stringify(value) }),
  testConfig: () => request<{ ok: boolean; message: string }>("/api/settings/provider/test", { method: "POST" }),
  deleteConfig: () => request<{ ok: boolean }>("/api/settings/provider", { method: "DELETE" }),
  generate: (resume_version_id: number, job_id: number) =>
    request<Generation>("/api/generations", { method: "POST", body: JSON.stringify({ resume_version_id, job_id }) }),
  generations: () => request<{ items: Generation[] }>("/api/generations"),
  generation: (id: number) => request<Generation>(`/api/generations/${id}`),
  retry: (id: number, module: "match" | "hr-message" | "resume-advice") =>
    request<Generation>(`/api/generations/${id}/retry/${module}`, { method: "POST" }),
};

export const downloadUrl = (path: string) => `${API_BASE}${path}`;
