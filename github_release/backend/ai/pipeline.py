from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

from pydantic import BaseModel

from backend.ai.llm_client import OpenAICompatibleClient
from backend.ai.long_jd import LongJDDiagnostics, estimate_tokens, merge_jd_analyses, safe_jd_budget, semantic_chunks
from backend.ai.prompts.loader import load_role, render_prompt
from backend.ai.schemas import HRMessage, JDAnalysis, MatchAnalysis, ResumeAdvice, ResumeStructure
from backend.ai.structured import (
    StructuredResult,
    StructuredTrace,
    generate_structured,
    normalize_hr_message,
)
from backend.config import (
    HR_PROMPT_VERSION,
    JD_ANALYSIS_PROMPT_VERSION,
    MATCH_PROMPT_VERSION,
    RESUME_ADVICE_PROMPT_VERSION,
    RESUME_STRUCTURE_PROMPT_VERSION,
)
from backend.errors import LLMError, StructuredOutputError


T = TypeVar("T", bound=BaseModel)
ProgressCallback = Callable[[str, str], Awaitable[None] | None]
PERCENT_PATTERN = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s*%")
NUMERIC_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?\s*%?")


@dataclass
class JDStructuredResult:
    value: JDAnalysis
    traces: list[StructuredTrace]
    diagnostics: LongJDDiagnostics


@dataclass
class PipelineOutcome:
    resume_structure: ResumeStructure | None = None
    jd_analysis: JDAnalysis | None = None
    match: MatchAnalysis | None = None
    hr_message: HRMessage | None = None
    resume_advice: ResumeAdvice | None = None
    match_error: str | None = None
    hr_message_error: str | None = None
    resume_advice_error: str | None = None
    traces: list[StructuredTrace] = field(default_factory=list)


def _input_prompt(task: str, version: str, **sections: str) -> str:
    blocks = [render_prompt(task, version)]
    for name, value in sections.items():
        blocks.append(f"## Runtime Input: {name}\n{value}")
    return "\n\n".join(blocks)


def availability_policy(jd: JDAnalysis) -> str:
    req = jd.availability_requirements
    if jd.employment_type == "internship":
        baseline = "目前可实习6个月，每周到岗5天，能立即到岗。"
        conflicts: list[str] = []
        if req.internship_duration_months and req.internship_duration_months > 6:
            conflicts.append("更长实习周期")
        if req.days_per_week and req.days_per_week > 5:
            conflicts.append("更高每周到岗天数")
        if conflicts:
            return baseline[:-1] + f"；如需{'、'.join(conflicts)}可进一步沟通。"
        return baseline
    return "到岗方面可以尽快安排。"


def _compact_evidence(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]", "", value).casefold()


def _evidence_supported(evidence: str, source: str) -> bool:
    needle = _compact_evidence(evidence)
    haystack = _compact_evidence(source)
    if not needle:
        return False
    if needle in haystack:
        return True
    # LLMs commonly join two verbatim resume facts with a short connective.
    # Accept that only when most overlapping character trigrams remain in the
    # source and every number is still source-backed. This is deterministic;
    # it neither invents facts nor performs semantic guessing.
    numeric_tokens = re.findall(r"\d+(?:\.\d+)?%?", needle)
    if any(token not in haystack for token in numeric_tokens):
        return False
    if len(needle) < 8:
        return False
    grams = [needle[index:index + 3] for index in range(len(needle) - 2)]
    coverage = sum(gram in haystack for gram in grams) / len(grams)
    return coverage >= 0.58


def _resume_fact_validator(resume_text: str):
    """Reject metrics that cannot be found in the actual resume text.

    This deliberately validates only deterministic numeric evidence. It does not
    guess whether paraphrases are semantically equivalent and therefore never
    creates or repairs business facts.
    """
    source = _compact_evidence(resume_text)

    def validate(value: ResumeStructure) -> list[dict]:
        errors: list[dict] = []
        groups = (("work_experience", value.work_experience), ("projects", value.projects))
        for group_name, records in groups:
            for record_index, record in enumerate(records):
                for metric_index, metric in enumerate(record.metrics):
                    tokens = NUMERIC_TOKEN_PATTERN.findall(metric.value)
                    unsupported = [token for token in tokens if _compact_evidence(token) not in source]
                    if unsupported:
                        errors.append({
                            "error_code": "unsupported_resume_metric",
                            "field_path": f"{group_name}.{record_index}.metrics.{metric_index}.value",
                            "expected": "every numeric metric must appear in the original resume text",
                            "received": unsupported,
                            "validation_message": "结构化简历包含原始简历中不存在的量化指标。",
                        })
        return errors

    return validate


def _jd_fact_validator(jd_text: str):
    def validate(value: JDAnalysis) -> list[dict]:
        errors: list[dict] = []
        for group_name in ("responsibilities", "core_requirements", "preferred_requirements", "hard_constraints"):
            for index, item in enumerate(getattr(value, group_name)):
                if not _evidence_supported(item.source_evidence, jd_text):
                    errors.append({
                        "error_code": "unsupported_jd_evidence",
                        "field_path": f"{group_name}.{index}.source_evidence",
                        "expected": "a verbatim or punctuation/whitespace-equivalent substring of this JD chunk",
                        "received": item.source_evidence,
                        "validation_message": "JD 结构化证据无法回溯到当前 JD 原文。",
                    })
        # An ambiguity can describe information that is absent from the JD.  In
        # that case there is no honest source quotation to provide, so an empty
        # source_evidence is valid.  If the model does provide evidence, it must
        # still be traceable to the original JD text.
        for index, item in enumerate(value.ambiguities):
            if item.source_evidence and not _evidence_supported(item.source_evidence, jd_text):
                errors.append({
                    "error_code": "unsupported_jd_evidence",
                    "field_path": f"ambiguities.{index}.source_evidence",
                    "expected": "an empty value for absent information, or a source-backed JD excerpt",
                    "received": item.source_evidence,
                    "validation_message": "JD 不确定项的证据无法回溯到当前 JD 原文。",
                })
        return errors

    return validate


def _match_fact_validator(resume: ResumeStructure, jd: JDAnalysis):
    resume_source = json.dumps(resume.model_dump(), ensure_ascii=False)
    requirements = {
        item.id: item.requirement
        for collection in (jd.core_requirements, jd.preferred_requirements, jd.hard_constraints)
        for item in collection
    }
    requirements.update({item.id: item.content for item in jd.responsibilities})

    def validate(value: MatchAnalysis) -> list[dict]:
        errors: list[dict] = []
        for group_name, records in (("strong_matches", value.strong_matches), ("gaps", value.gaps)):
            for index, record in enumerate(records):
                known_requirement = requirements.get(record.requirement_id)
                if known_requirement is None:
                    errors.append({
                        "error_code": "unknown_requirement_id",
                        "field_path": f"{group_name}.{index}.requirement_id",
                        "expected": "an id from the current Structured JD",
                        "received": record.requirement_id,
                        "validation_message": "匹配结果引用了当前 JD 中不存在的 Requirement ID。",
                    })
                elif not (
                    _evidence_supported(record.requirement, known_requirement)
                    or _evidence_supported(known_requirement, record.requirement)
                ):
                    errors.append({
                        "error_code": "requirement_text_mismatch",
                        "field_path": f"{group_name}.{index}.requirement",
                        "expected": known_requirement,
                        "received": record.requirement,
                        "validation_message": "匹配结果中的岗位要求与其 Requirement ID 不一致。",
                    })
                if group_name == "strong_matches" and not _evidence_supported(record.resume_evidence, resume_source):
                    errors.append({
                        "error_code": "unsupported_resume_evidence",
                        "field_path": f"strong_matches.{index}.resume_evidence",
                        "expected": "evidence contained in the current Structured Resume",
                        "received": record.resume_evidence,
                        "validation_message": "匹配证据无法回溯到当前结构化简历。",
                    })
        return errors

    return validate


def _ensure_sentence(value: str) -> str:
    text = value.strip()
    return text if not text or text[-1] in "。！？!?；;" else text + "。"


def _brief_self_intro(resume: ResumeStructure, fallback: str) -> str:
    if resume.education:
        education = resume.education[0]
        raw_status = education.status.strip().casefold()
        if raw_status in {"ongoing", "current", "enrolled", "在读", "就读中"}:
            status = "在读"
        elif raw_status in {"graduated", "completed", "已毕业", "毕业"}:
            status = ""
        else:
            status = education.status if education.status and education.status not in education.degree else ""
        return _ensure_sentence(f"我目前是{education.institution}{education.major}{education.degree}{status}")
    if resume.candidate.current_title:
        return _ensure_sentence(f"我目前从事{resume.candidate.current_title}相关工作")
    return _ensure_sentence(fallback)


def _complete_clauses(value: str, max_chars: int) -> str:
    """Keep whole semantic clauses only; never cut at an arbitrary character."""
    if max_chars <= 1:
        return ""
    clauses = [item.strip(" ，,。；;！？!?") for item in re.split(r"[。；;！？!?]", value) if item.strip()]
    chosen: list[str] = []
    for clause in clauses:
        candidate = "；".join([*chosen, clause]) + "。"
        if len(candidate) > max_chars:
            break
        chosen.append(clause)
    return "；".join(chosen) + "。" if chosen else ""


def _hr_normalizer(resume: ResumeStructure, jd: JDAnalysis, match: MatchAnalysis):
    required_availability = availability_policy(jd)

    def normalize(value: dict) -> dict:
        normalized = normalize_hr_message(value)
        if normalized.get("status") != "ready":
            return normalized
        opening = str(normalized.get("opening", "")).strip()
        if opening.startswith("你好"):
            opening = "您好" + opening[2:]
        normalized["opening"] = opening
        normalized["availability"] = required_availability
        points = normalized.get("fit_points")
        if isinstance(points, list):
            fit_limit = {"strong_fit": 2, "partial_fit": 2, "weak_fit": 1, "insufficient_evidence": 0}[match.fit_level]
            normalized["fit_points"] = points[:fit_limit]
        for point in normalized.get("fit_points", []):
            if not isinstance(point, dict):
                continue
            sentence = str(point.get("sentence", ""))
            if match.fit_level in {"partial_fit", "weak_fit"}:
                sentence = sentence.replace("能够胜任", "这段经验可用于").replace("能胜任", "这段经验可用于")
                sentence = sentence.replace("高度匹配", "存在相关基础")
            point["sentence"] = sentence

        def compose() -> str:
            pieces = [normalized.get("opening", ""), normalized.get("self_intro", "")]
            pieces.extend(item.get("sentence", "") for item in normalized.get("fit_points", []) if isinstance(item, dict))
            pieces.extend([normalized.get("interest", ""), required_availability])
            clean = [str(piece).strip() for piece in pieces if str(piece).strip()]
            return "".join(piece for index, piece in enumerate(clean) if piece not in clean[:index])

        message = compose()
        if len(message) > 180:
            normalized["fit_points"] = normalized.get("fit_points", [])[:1]
            message = compose()
        if len(message) > 180:
            title = (jd.job_title or "该岗位").strip()
            label = title if title.endswith(("岗", "岗位", "职位")) else title + "岗位"
            normalized["opening"] = f"您好，关注到贵司发布的{label}。"
            normalized["self_intro"] = _brief_self_intro(resume, str(normalized.get("self_intro", "")))
            normalized["interest"] = "岗位方向与我希望发展的方向一致，希望进一步沟通。"
            message = compose()
        if len(message) > 180 and normalized.get("fit_points"):
            point = normalized["fit_points"][0]
            fixed_length = len(compose()) - len(str(point.get("sentence", "")))
            remaining = 180 - fixed_length
            candidates = [
                str(point.get("sentence", "")),
                str(point.get("resume_evidence", "")),
                match.strong_matches[0].resume_evidence if match.strong_matches else "",
            ]
            compact = next((_ensure_sentence(item) for item in candidates if item and len(_ensure_sentence(item)) <= remaining), "")
            if not compact:
                compact = next((_complete_clauses(item, remaining) for item in candidates if _complete_clauses(item, remaining)), "")
            if compact:
                point["sentence"] = compact
            message = compose()
        normalized["message"] = message
        return normalized

    return normalize


def _hr_fact_validator(resume: ResumeStructure, match: MatchAnalysis):
    source = json.dumps(resume.model_dump(), ensure_ascii=False)
    allowed_percentages = set(PERCENT_PATTERN.findall(source))

    def validate(value: HRMessage) -> list[dict]:
        errors: list[dict] = []
        if value.status == "ready":
            rendered = json.dumps(value.model_dump(), ensure_ascii=False)
            unknown = set(PERCENT_PATTERN.findall(rendered)) - allowed_percentages
            if unknown:
                errors.append({
                    "error_code": "unsupported_quantified_claim",
                    "field_path": "message",
                    "expected": "every percentage must appear in Structured Resume source evidence",
                    "received": sorted(unknown),
                    "validation_message": "话术包含简历证据中不存在的百分比。",
                })
            expected_count = 0 if match.fit_level == "insufficient_evidence" else (1 if match.fit_level == "weak_fit" else None)
            if expected_count is not None and len(value.fit_points) > expected_count:
                errors.append({
                    "error_code": "fit_point_policy",
                    "field_path": "fit_points",
                    "expected": f"at most {expected_count} item(s) for {match.fit_level}",
                    "received": len(value.fit_points),
                    "validation_message": "话术能力点数量不符合匹配等级策略。",
                })
        return errors

    return validate


def _advice_fact_validator(resume: ResumeStructure, match: MatchAnalysis):
    source = json.dumps(resume.model_dump(), ensure_ascii=False)
    allowed_percentages = set(PERCENT_PATTERN.findall(source))
    conditional_pattern = re.compile(r"如果|若(?:有|无|能|实际)|如有|假如|前提是|需(?:要)?用户确认")
    addition_pattern = re.compile(r"增加|补充|加入|添加")

    def validate(value: ResumeAdvice) -> list[dict]:
        errors: list[dict] = []
        if value.fit_level != match.fit_level:
            errors.append({
                "error_code": "fit_level_mismatch",
                "field_path": "fit_level",
                "expected": match.fit_level,
                "received": value.fit_level,
                "validation_message": "修改建议必须继承本次 Match Analysis 的匹配等级。",
            })
        for index, suggestion in enumerate(value.suggestions):
            rendered = json.dumps(suggestion.model_dump(), ensure_ascii=False)
            unknown = set(PERCENT_PATTERN.findall(rendered)) - allowed_percentages
            if unknown:
                errors.append({
                    "error_code": "unsupported_quantified_advice",
                    "field_path": f"suggestions.{index}",
                    "expected": "percentages must already exist in the Structured Resume",
                    "received": sorted(unknown),
                    "validation_message": "修改建议包含原简历中不存在的具体百分比。",
                })
            conditional_content = bool(conditional_pattern.search(suggestion.suggestion))
            unconfirmed_addition = bool(
                addition_pattern.search(suggestion.suggestion)
                and suggestion.needs_user_confirmation
            )
            if (conditional_content or unconfirmed_addition) and (
                suggestion.action_type != "add_if_true"
                or suggestion.can_apply_directly
                or not suggestion.needs_user_confirmation
            ):
                errors.append({
                    "error_code": "conditional_content_policy",
                    "field_path": f"suggestions.{index}.action_type",
                    "expected": "add_if_true with needs_user_confirmation=true and can_apply_directly=false",
                    "received": {
                        "action_type": suggestion.action_type,
                        "can_apply_directly": suggestion.can_apply_directly,
                        "needs_user_confirmation": suggestion.needs_user_confirmation,
                    },
                    "validation_message": "需要用户确认或以条件成立为前提的新增内容，只能作为 add_if_true 建议。",
                })
        return errors

    return validate


class ResumeMatcherPipeline:
    def __init__(self, client: OpenAICompatibleClient):
        self.client = client
        self.role = load_role()

    async def _run(self, *, task: str, version: str, schema: type[T], task_prompt: str,
                   temperature: float = 0.2, normalizer=None, semantic_validator=None,
                   repair_context: str = "", diagnostics: dict | None = None) -> StructuredResult[T]:
        return await generate_structured(
            client=self.client, module=task, prompt_version=version, system_prompt=self.role,
            task_prompt=task_prompt, schema=schema, temperature=temperature,
            normalizer=normalizer, semantic_validator=semantic_validator,
            repair_context=repair_context, diagnostics=diagnostics,
        )

    async def resume_structure(self, resume_text: str, *, version: str = RESUME_STRUCTURE_PROMPT_VERSION,
                               temperature: float = 0.1) -> StructuredResult[ResumeStructure]:
        return await self._run(
            task="resume_structure", version=version, schema=ResumeStructure, temperature=temperature,
            task_prompt=_input_prompt("resume_structure", version, RESUME_RAW_TEXT=resume_text),
            semantic_validator=_resume_fact_validator(resume_text),
            repair_context="Numeric metrics are valid only when the exact value appears in RESUME_RAW_TEXT.",
        )

    async def jd_analysis(self, jd_text: str, *, version: str = JD_ANALYSIS_PROMPT_VERSION,
                          temperature: float = 0.1) -> JDStructuredResult:
        estimated = estimate_tokens(jd_text)
        budget = safe_jd_budget(self.client.settings.model)
        chunks = semantic_chunks(jd_text, token_budget=budget) if estimated > budget else [jd_text]
        traces: list[StructuredTrace] = []
        values: list[JDAnalysis] = []
        for index, chunk in enumerate(chunks, start=1):
            diagnostics = {
                "jd_original_chars": len(jd_text), "estimated_tokens": estimated,
                "long_jd_triggered": len(chunks) > 1, "chunk_count": len(chunks),
                "chunk_index": index, "chunk_chars": len(chunk),
            }
            result = await self._run(
                task="jd_analysis", version=version, schema=JDAnalysis, temperature=temperature,
                task_prompt=_input_prompt(
                    "jd_analysis", version,
                    CHUNK_CONTEXT=f"这是完整 JD 的第 {index}/{len(chunks)} 个语义分段。只提取本段明确事实；不要假设其他分段内容。",
                    JD_RAW_TEXT=chunk,
                ),
                semantic_validator=_jd_fact_validator(chunk),
                repair_context="Every source_evidence must remain supported by the exact JD chunk; do not add facts.",
                diagnostics=diagnostics,
            )
            traces.append(result.trace)
            values.append(result.value)
        merged = merge_jd_analyses(values) if len(values) > 1 else values[0]
        final_size = len(json.dumps(merged.model_dump(), ensure_ascii=False))
        final_diagnostics = LongJDDiagnostics(len(jd_text), estimated, len(chunks) > 1, len(chunks), final_size)
        for trace in traces:
            trace.diagnostics.update(final_diagnostics.as_dict())
        return JDStructuredResult(value=merged, traces=traces, diagnostics=final_diagnostics)

    async def match_analysis(self, resume: ResumeStructure, jd: JDAnalysis, *,
                             version: str = MATCH_PROMPT_VERSION, temperature: float = 0.2) -> StructuredResult[MatchAnalysis]:
        return await self._run(
            task="match_analysis", version=version, schema=MatchAnalysis, temperature=temperature,
            task_prompt=_input_prompt(
                "match_analysis", version,
                STRUCTURED_RESUME=json.dumps(resume.model_dump(), ensure_ascii=False),
                STRUCTURED_JD=json.dumps(jd.model_dump(), ensure_ascii=False),
                CANDIDATE_AVAILABILITY_POLICY=availability_policy(jd),
            ),
            semantic_validator=_match_fact_validator(resume, jd),
            repair_context=(
                "Requirement IDs and requirement text must stay aligned to STRUCTURED_JD; resume_evidence must "
                "already occur in STRUCTURED_RESUME. Remove unsupported matches instead of inventing evidence."
            ),
        )

    async def hr_message(self, resume: ResumeStructure, jd: JDAnalysis, match: MatchAnalysis, *,
                         version: str = HR_PROMPT_VERSION, temperature: float = 0.2) -> StructuredResult[HRMessage]:
        policy = availability_policy(jd)
        return await self._run(
            task="hr_message", version=version, schema=HRMessage, temperature=temperature,
            task_prompt=_input_prompt(
                "hr_message", version,
                STRUCTURED_RESUME=json.dumps(resume.model_dump(), ensure_ascii=False),
                STRUCTURED_JD=json.dumps(jd.model_dump(), ensure_ascii=False),
                MATCH_ANALYSIS=json.dumps(match.model_dump(), ensure_ascii=False),
                APPLICATION_AVAILABILITY_POLICY=policy,
            ),
            normalizer=_hr_normalizer(resume, jd, match), semantic_validator=_hr_fact_validator(resume, match),
            repair_context=f"The application availability policy is exactly: {policy} Do not infer candidate availability from the JD.",
        )

    async def resume_advice(self, resume: ResumeStructure, jd: JDAnalysis, match: MatchAnalysis, *,
                            version: str = RESUME_ADVICE_PROMPT_VERSION, temperature: float = 0.2) -> StructuredResult[ResumeAdvice]:
        return await self._run(
            task="resume_advice", version=version, schema=ResumeAdvice, temperature=temperature,
            task_prompt=_input_prompt(
                "resume_advice", version,
                STRUCTURED_RESUME=json.dumps(resume.model_dump(), ensure_ascii=False),
                STRUCTURED_JD=json.dumps(jd.model_dump(), ensure_ascii=False),
                MATCH_ANALYSIS=json.dumps(match.model_dump(), ensure_ascii=False),
            ),
            semantic_validator=_advice_fact_validator(resume, match),
            repair_context=(
                f"fit_level must remain exactly {match.fit_level}. Percentages not present in the "
                "Structured Resume must be removed, not invented or replaced. Any conditional suggestion "
                "to add an unconfirmed metric must use action_type=add_if_true, "
                "needs_user_confirmation=true, and can_apply_directly=false."
            ),
        )

    async def run(self, resume_text: str, jd_text: str) -> PipelineOutcome:
        outcome = PipelineOutcome()
        try:
            resume_result = await self.resume_structure(resume_text)
            outcome.resume_structure = resume_result.value
            outcome.traces.append(resume_result.trace)
            jd_result = await self.jd_analysis(jd_text)
            outcome.jd_analysis = jd_result.value
            outcome.traces.extend(jd_result.traces)
            match_result = await self.match_analysis(resume_result.value, jd_result.value)
            outcome.match = match_result.value
            outcome.traces.append(match_result.trace)
        except (StructuredOutputError, LLMError) as exc:
            outcome.match_error = str(exc)
            if isinstance(exc, StructuredOutputError):
                outcome.traces.append(exc.trace)
            return outcome

        results = await asyncio.gather(
            self.hr_message(outcome.resume_structure, outcome.jd_analysis, outcome.match),
            self.resume_advice(outcome.resume_structure, outcome.jd_analysis, outcome.match),
            return_exceptions=True,
        )
        for name, result in zip(("hr_message", "resume_advice"), results):
            if isinstance(result, Exception):
                setattr(outcome, f"{name}_error", str(result))
                if isinstance(result, StructuredOutputError):
                    outcome.traces.append(result.trace)
            else:
                setattr(outcome, name, result.value)
                outcome.traces.append(result.trace)
        return outcome
