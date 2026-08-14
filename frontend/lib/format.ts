import type { Generation, MatchAnalysis, ResumeAdvice } from "./types";

export function formatMatch(match: MatchAnalysis): string {
  return [
    "# Hi Offer - 匹配分析",
    "",
    `匹配度：${match.match_score}`,
    `匹配等级：${match.fit_level ?? "旧版未记录"}`,
    "",
    "## 总结",
    match.summary,
    "",
    "## 最强匹配",
    ...match.strong_matches.map((item) => `- ${item.requirement}：${item.resume_evidence}（${item.reason}）`),
    "",
    "## 关键缺口",
    ...match.gaps.map((item) => `- ${item.requirement}（${item.severity}）：${item.reason}`),
    "",
    "## 关键词",
    match.keywords.join("、"),
    "",
    "## 风险",
    ...match.risks.map((item) => `- ${item}`),
  ].join("\n");
}

export function formatAdvice(advice: ResumeAdvice, generation?: Generation): string {
  const blocks = advice.suggestions.flatMap((item, index) => [
    `## ${index + 1}. ${item.section} / ${item.location}`,
    "",
    "### 原内容",
    item.original || "原文未提供可直接引用的句子",
    "",
    "### 问题",
    item.problem,
    "",
    "### 修改建议",
    item.suggestion,
    "",
    "### 原因",
    item.reason,
    "",
    `### 优先级\n${({ high: "高", medium: "中", low: "低" } as const)[item.priority]}`,
    item.action_type ? `### 操作类型\n${item.action_type}` : "",
    "",
  ]);
  return [
    "# Hi Offer - 简历修改建议",
    generation ? `岗位：${generation.position}` : "",
    generation ? `公司：${generation.company}` : "",
    generation ? `简历版本：Resume V${generation.resume_version_number}` : "",
    advice.fit_level ? `匹配等级：${advice.fit_level}` : "",
    advice.advice_mode ? `建议模式：${advice.advice_mode}` : "",
    advice.overall_direction ? `总体方向：${advice.overall_direction}` : "",
    "",
    ...blocks,
    ...((advice.hard_gaps ?? []).length ? ["## 无法仅靠措辞解决的差距", ...(advice.hard_gaps ?? []).map((item) => `- ${item.requirement}：${item.reason}；下一步：${item.recommended_next_step}`)] : []),
    ...((advice.limitations ?? []).length ? ["## 限制说明", ...(advice.limitations ?? []).map((item) => `- ${item}`)] : []),
  ]
    .filter((line, index, lines) => line !== "" || lines[index - 1] !== "")
    .join("\n");
}
