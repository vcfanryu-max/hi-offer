from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.ai.schemas import HRMessage, MatchAnalysis, ResumeAdvice


def _data(value: Any) -> dict:
    return value.model_dump() if hasattr(value, "model_dump") else (value or {})


def match_markdown(match: MatchAnalysis | dict) -> str:
    value = _data(match)
    strong = "\n".join(
        f"- **{item.get('requirement', '')}**：{item.get('resume_evidence', '')}（{item.get('reason', '')}）"
        for item in value.get("strong_matches", [])
    ) or "- 暂无可确认的强匹配证据"
    gaps = "\n".join(
        f"- **{item.get('requirement', '')}**（{item.get('severity', '')}）：{item.get('reason', '')}"
        for item in value.get("gaps", [])
    ) or "- 暂无明确缺口"
    keywords = "、".join(value.get("keywords", [])) or "暂无"
    risks = "\n".join(f"- {item}" for item in value.get("risks", [])) or "- 暂无"
    return (
        "# Resume Matcher - 匹配分析\n\n"
        f"匹配度：{value.get('match_score', '—')}\n\n"
        f"匹配等级：{value.get('fit_level', '旧版未记录')}\n\n"
        f"## 总结\n\n{value.get('summary', '')}\n\n"
        f"## 最强匹配\n\n{strong}\n\n## 关键缺口\n\n{gaps}\n\n"
        f"## 关键词\n\n{keywords}\n\n## 风险\n\n{risks}\n"
    )


def hr_text(message: HRMessage | dict) -> str:
    return str(_data(message).get("message", "")).strip() + "\n"


def advice_markdown(advice: ResumeAdvice | dict, *, company: str, position: str,
                    resume_version: int, created_at: datetime) -> str:
    value = _data(advice)
    header = (
        "# Resume Matcher - 简历修改建议\n\n"
        f"岗位：{position or '未命名岗位'}\n公司：{company or '未注明公司'}\n"
        f"简历版本：Resume V{resume_version}\n生成时间：{created_at.isoformat()}\n\n"
        f"匹配等级：{value.get('fit_level', '旧版未记录')}\n"
        f"建议模式：{value.get('advice_mode', '旧版未记录')}\n\n"
        f"## 总体方向\n\n{value.get('overall_direction', '')}\n\n"
    )
    blocks: list[str] = []
    labels = {"high": "高", "medium": "中", "low": "低"}
    for index, item in enumerate(value.get("suggestions", []), start=1):
        blocks.append(
            f"## {index}. {item.get('section', '')} / {item.get('location', '')}\n\n"
            f"操作：{item.get('action_type', '旧版未记录')}\n\n"
            f"### 原内容\n{item.get('original') or '原文未提供可直接引用的句子'}\n\n"
            f"### 问题\n{item.get('problem', '')}\n\n### 修改建议\n{item.get('suggestion', '')}\n\n"
            f"### 原因\n{item.get('reason', '')}\n\n### 优先级\n{labels.get(item.get('priority'), item.get('priority', ''))}\n"
        )
    hard_gaps = value.get("hard_gaps", [])
    if hard_gaps:
        blocks.append("## 无法仅靠措辞解决的差距\n\n" + "\n".join(
            f"- {item.get('requirement', '')}：{item.get('reason', '')}；下一步：{item.get('recommended_next_step', '')}"
            for item in hard_gaps
        ))
    legacy = value.get("limitations", [])
    if legacy:
        blocks.append("## 限制说明\n\n" + "\n".join(f"- {item}" for item in legacy))
    return header + "\n\n".join(blocks)


def generation_markdown(*, jd_text: str, match: dict | None, hr_message: dict | None,
                        resume_advice: dict | None, company: str, position: str,
                        resume_version: int, created_at: datetime) -> str:
    return "\n\n".join([
        f"# {position or '未命名岗位'} · Resume Matcher Generation",
        f"公司：{company or '未注明公司'}  \n简历版本：Resume V{resume_version}  \n生成时间：{created_at.isoformat()}",
        "# Job Description\n\n" + jd_text,
        "# Match Analysis\n\n" + match_markdown(match or {}),
        "# HR Message\n\n" + hr_text(hr_message or {}),
        "# Resume Advice\n\n" + advice_markdown(
            resume_advice or {}, company=company, position=position,
            resume_version=resume_version, created_at=created_at,
        ),
    ]) + "\n"


def safe_export_stem(value: str, *, fallback: str) -> str:
    import re
    cleaned = re.sub(r'[^\w\u4e00-\u9fff-]+', "_", value.strip()).strip("_")
    return (cleaned[:80] or fallback)
