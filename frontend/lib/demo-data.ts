import type { Generation } from "./types";

export const demoGeneration: Generation = {
  id: 2026, job_id: 1, resume_version_id: 1, resume_version_number: 3,
  resume_filename: "林晓_前端工程师_示例简历.pdf",
  company: "Northstar Studio（虚构公司）", position: "Frontend Engineer", job_source_type: "text",
  match_status: "completed", hr_message_status: "completed", resume_advice_status: "completed",
  match_prompt_version: "v2", hr_prompt_version: "v2", resume_advice_prompt_version: "v2",
  provider: "Demo Dataset", model: "Pre-generated sample",
  created_at: "2026-08-13T10:00:00+08:00", updated_at: "2026-08-13T10:00:00+08:00",
  match_result: {
    match_score: 84, fit_level: "strong_fit",
    summary: "候选人的 React、TypeScript 与设计系统经验能够直接覆盖岗位核心要求；性能优化和跨职能协作证据充分。主要缺口是缺少公开的国际化产品经历，以及对端到端测试影响的量化说明。",
    strong_matches: [
      { requirement: "React 与 TypeScript 生产经验", resume_evidence: "负责 React 19 + TypeScript 客户端重构", match_type: "direct", reason: "技术栈与职责直接对应" },
      { requirement: "建设可复用设计系统", resume_evidence: "交付 28 个可访问组件并服务 4 条产品线", match_type: "direct", reason: "有明确范围与复用结果" },
      { requirement: "前端性能优化", resume_evidence: "将 LCP 从 3.1s 降至 1.8s", match_type: "direct", reason: "提供了可验证的性能指标" },
    ],
    gaps: [
      { requirement: "国际化产品经验", severity: "medium", reason: "简历没有多语言或多地区交付证据" },
      { requirement: "端到端测试体系", severity: "low", reason: "提到 Playwright，但没有说明覆盖率或稳定性收益" },
    ],
    keywords: ["React", "TypeScript", "Next.js", "Design System", "Web Performance"], risks: ["国际化经验需要进一步确认"],
  },
  hr_message: {
    status: "ready",
    message: "您好，我关注到贵团队正在招聘 Frontend Engineer。过去三年我主要使用 React、TypeScript 与 Next.js 构建复杂 Web 产品，曾主导 28 个组件的设计系统建设，并把核心页面 LCP 从 3.1 秒优化到 1.8 秒。这些经历与岗位强调的工程质量、性能和跨团队协作较为契合。如果方便，希望进一步了解团队目前最重要的前端挑战。",
    evidence_used: ["React/TypeScript 重构", "28 个设计系统组件", "LCP 3.1s → 1.8s"],
  },
  resume_advice: {
    fit_level: "strong_fit", advice_mode: "polish", overall_direction: "保留工程深度，优先补足测试与业务影响证据。",
    suggestions: [
      { section: "工作经历", location: "Northwind 项目第 1 条", original: "负责前端性能优化", problem: "描述过于宽泛，无法判断具体动作和效果", suggestion: "主导 Next.js 页面性能治理，通过路由级拆包、图片策略与请求缓存将移动端 LCP 从 3.1s 降至 1.8s。", reason: "把技术动作、范围和结果放在同一句中", priority: "high", action_type: "rewrite", can_apply_directly: true },
      { section: "项目经历", location: "设计系统项目", original: "使用 Playwright 编写测试", problem: "缺少测试规模与稳定性收益", suggestion: "如属实，补充关键流程数量、CI 执行频率，以及上线后回归缺陷下降比例。", reason: "岗位重视端到端质量体系，量化证据会增强可信度", priority: "medium", action_type: "add_if_true", needs_user_confirmation: true },
      { section: "技能", location: "前端技术栈", original: "React、Vue、Next.js、Node.js……", problem: "技能罗列没有体现与目标岗位的优先级", suggestion: "将 React、TypeScript、Next.js、Web Performance 与 Design System 前置，其余技术压缩到次级分组。", reason: "让招聘方在首屏快速看到岗位关键词", priority: "medium", action_type: "reorder", can_apply_directly: true },
    ],
  },
};

