from __future__ import annotations

import asyncio
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.pipeline import ResumeMatcherPipeline
from backend.ai.schemas import JDAnalysis, MatchAnalysis, ResumeAdvice, ResumeStructure
from backend.ai.structured import StructuredTrace
from backend.config import (
    DEBUG_MODE,
    HR_PROMPT_VERSION,
    JD_ANALYSIS_PROMPT_VERSION,
    MATCH_PROMPT_VERSION,
    RESUME_ADVICE_PROMPT_VERSION,
    RESUME_STRUCTURE_PROMPT_VERSION,
    STRUCTURED_REPAIR_PROMPT_VERSION,
)
from backend.db.models import Generation, GenerationDebugTrace, Job, ResumeVersion
from backend.errors import LLMError, NotFoundError, StructuredOutputError
from backend.security import ApiKeyStore
from backend.services.api_config_service import get_record, make_client


def _loads(value: str | None):
    try:
        return json.loads(value) if value else None
    except json.JSONDecodeError:
        return None


def _safe_module_error(exc: Exception) -> str:
    if isinstance(exc, LLMError):
        return str(exc)
    return "生成过程遇到未预期的问题。当前快照已保留，请重试。"


def _trace_from_exception(exc: Exception) -> StructuredTrace | None:
    return exc.trace if isinstance(exc, StructuredOutputError) else None


def _store_trace(session: Session, generation: Generation, trace: StructuredTrace | None) -> None:
    if not DEBUG_MODE or not trace:
        return
    session.add(GenerationDebugTrace(
        generation_id=generation.id, module=trace.module, request_id=trace.request_id,
        prompt_version=trace.prompt_version, provider=trace.provider, model=trace.model,
        trace_json=json.dumps(trace.public_dict(generation_id=generation.id), ensure_ascii=False),
    ))


def _store_traces(session: Session, generation: Generation, traces: list[StructuredTrace]) -> None:
    for trace in traces:
        _store_trace(session, generation, trace)


def public_generation(item: Generation, *, include_content: bool = True) -> dict:
    payload = {
        "id": item.id, "generation_id": item.id, "job_id": item.job_id,
        "resume_version_id": item.resume_version_id,
        "resume_version_number": item.resume_version.version_number,
        "resume_filename": item.resume_version.original_filename,
        "company": item.job.company or "未注明公司", "position": item.job.position or "未命名岗位",
        "job_source_type": item.job.source_type, "job_original_filename": item.job.original_filename,
        "match_status": item.match_status, "hr_message_status": item.hr_message_status,
        "resume_advice_status": item.resume_advice_status, "match_error": item.match_error,
        "hr_message_error": item.hr_message_error, "resume_advice_error": item.resume_advice_error,
        "resume_structure_prompt_version": item.resume_structure_prompt_version,
        "jd_analysis_prompt_version": item.jd_analysis_prompt_version,
        "match_prompt_version": item.match_prompt_version, "hr_prompt_version": item.hr_prompt_version,
        "resume_advice_prompt_version": item.resume_advice_prompt_version,
        "structured_repair_prompt_version": item.structured_repair_prompt_version,
        "prompt_versions": {
            "resume_structure": item.resume_structure_prompt_version,
            "jd_analysis": item.jd_analysis_prompt_version,
            "match_analysis": item.match_prompt_version,
            "hr_message": item.hr_prompt_version,
            "resume_advice": item.resume_advice_prompt_version,
            "structured_repair": item.structured_repair_prompt_version,
        },
        "provider": item.provider, "model": item.model,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
        "debug_enabled": DEBUG_MODE,
    }
    if include_content:
        payload.update(
            resume_structure=_loads(item.resume_structure_json), jd_analysis=_loads(item.jd_analysis_json),
            match_result=_loads(item.match_result_json), hr_message=_loads(item.hr_message_json),
            resume_advice=_loads(item.resume_advice_json), jd_text=item.job.jd_text,
        )
        if DEBUG_MODE:
            payload["debug_traces"] = [_loads(trace.trace_json) for trace in item.debug_traces]
            payload["ocr_extracted_text"] = {
                "resume": item.resume_version.ocr_text if item.resume_version.ocr_used else None,
                "jd": item.job.ocr_text if item.job.ocr_used else None,
            }
    return payload


def get_generation(session: Session, generation_id: int) -> Generation:
    item = session.get(Generation, generation_id)
    if not item:
        raise NotFoundError("找不到该生成记录。")
    return item


def list_generations(session: Session) -> list[dict]:
    items = session.scalars(select(Generation).order_by(Generation.created_at.desc())).all()
    return [public_generation(item, include_content=False) for item in items]


async def _prepare_inputs(session: Session, generation: Generation, pipeline: ResumeMatcherPipeline,
                          resume: ResumeVersion, job: Job) -> tuple[ResumeStructure, JDAnalysis]:
    use_resume_cache = (
        not DEBUG_MODE and resume.structured_resume_json and
        resume.structured_prompt_version == RESUME_STRUCTURE_PROMPT_VERSION
    )
    if use_resume_cache:
        structured_resume = ResumeStructure.model_validate_json(resume.structured_resume_json)
    else:
        result = await pipeline.resume_structure(resume.parsed_text)
        structured_resume = result.value
        resume.structured_resume_json = result.value.model_dump_json()
        resume.structured_prompt_version = RESUME_STRUCTURE_PROMPT_VERSION
        result.trace.diagnostics.update({
            "ocr_used": bool(resume.ocr_used),
            "ocr_extracted_text": resume.ocr_text if DEBUG_MODE and resume.ocr_used else None,
        })
        _store_trace(session, generation, result.trace)

    use_jd_cache = (
        not DEBUG_MODE and job.structured_jd_json and
        job.structured_prompt_version == JD_ANALYSIS_PROMPT_VERSION
    )
    if use_jd_cache:
        structured_jd = JDAnalysis.model_validate_json(job.structured_jd_json)
    else:
        result = await pipeline.jd_analysis(job.jd_text)
        structured_jd = result.value
        job.structured_jd_json = result.value.model_dump_json()
        job.structured_prompt_version = JD_ANALYSIS_PROMPT_VERSION
        for trace in result.traces:
            trace.diagnostics.update({
                "ocr_used": bool(job.ocr_used),
                "ocr_extracted_text": job.ocr_text if DEBUG_MODE and job.ocr_used else None,
            })
        _store_traces(session, generation, result.traces)

    generation.resume_structure_json = structured_resume.model_dump_json()
    generation.jd_analysis_json = structured_jd.model_dump_json()
    generation.resume_structure_prompt_version = RESUME_STRUCTURE_PROMPT_VERSION
    generation.jd_analysis_prompt_version = JD_ANALYSIS_PROMPT_VERSION
    generation.structured_repair_prompt_version = STRUCTURED_REPAIR_PROMPT_VERSION
    session.commit()
    return structured_resume, structured_jd


async def _run_downstream(session: Session, generation: Generation, pipeline: ResumeMatcherPipeline,
                          resume: ResumeStructure, jd: JDAnalysis, match: MatchAnalysis) -> None:
    generation.hr_message_status = "running"
    generation.resume_advice_status = "running"
    generation.hr_message_error = None
    generation.resume_advice_error = None
    session.commit()
    hr_result, advice_result = await asyncio.gather(
        pipeline.hr_message(resume, jd, match), pipeline.resume_advice(resume, jd, match),
        return_exceptions=True,
    )
    if isinstance(hr_result, Exception):
        generation.hr_message_status = "failed"
        generation.hr_message_error = _safe_module_error(hr_result)
        _store_trace(session, generation, _trace_from_exception(hr_result))
    else:
        generation.hr_message_json = hr_result.value.model_dump_json()
        generation.hr_message_status = "success"
        generation.hr_prompt_version = HR_PROMPT_VERSION
        _store_trace(session, generation, hr_result.trace)
    if isinstance(advice_result, Exception):
        generation.resume_advice_status = "failed"
        generation.resume_advice_error = _safe_module_error(advice_result)
        _store_trace(session, generation, _trace_from_exception(advice_result))
    else:
        generation.resume_advice_json = advice_result.value.model_dump_json()
        generation.resume_advice_status = "success"
        generation.resume_advice_prompt_version = RESUME_ADVICE_PROMPT_VERSION
        _store_trace(session, generation, advice_result.trace)
    session.commit()


async def create_generation(session: Session, store: ApiKeyStore, *, resume_version_id: int, job_id: int) -> dict:
    resume = session.get(ResumeVersion, resume_version_id)
    job = session.get(Job, job_id)
    config = get_record(session)
    if not resume:
        raise NotFoundError("当前简历版本不存在。")
    if not job:
        raise NotFoundError("岗位记录不存在。")
    if not config:
        raise NotFoundError("尚未配置模型 API。")
    pipeline = ResumeMatcherPipeline(make_client(session, store))
    generation = Generation(
        job_id=job.id, resume_version_id=resume.id, match_status="running",
        hr_message_status="pending", resume_advice_status="pending",
        resume_structure_prompt_version=RESUME_STRUCTURE_PROMPT_VERSION,
        jd_analysis_prompt_version=JD_ANALYSIS_PROMPT_VERSION,
        match_prompt_version=MATCH_PROMPT_VERSION, hr_prompt_version=HR_PROMPT_VERSION,
        resume_advice_prompt_version=RESUME_ADVICE_PROMPT_VERSION,
        structured_repair_prompt_version=STRUCTURED_REPAIR_PROMPT_VERSION,
        provider=config.provider, model=config.model,
    )
    session.add(generation)
    session.commit()
    try:
        structured_resume, structured_jd = await _prepare_inputs(session, generation, pipeline, resume, job)
        match_result = await pipeline.match_analysis(structured_resume, structured_jd)
        generation.match_result_json = match_result.value.model_dump_json()
        generation.match_status = "success"
        _store_trace(session, generation, match_result.trace)
        session.commit()
    except Exception as exc:
        generation.match_status = "failed"
        generation.match_error = _safe_module_error(exc)
        generation.hr_message_status = "blocked"
        generation.resume_advice_status = "blocked"
        _store_trace(session, generation, _trace_from_exception(exc))
        session.commit()
        return public_generation(generation)
    await _run_downstream(session, generation, pipeline, structured_resume, structured_jd, match_result.value)
    return public_generation(generation)


async def retry_module(session: Session, store: ApiKeyStore, generation_id: int, module: str) -> dict:
    generation = get_generation(session, generation_id)
    pipeline = ResumeMatcherPipeline(make_client(session, store))
    resume_record, job_record = generation.resume_version, generation.job
    if module == "match":
        generation.match_status, generation.match_error = "running", None
        generation.hr_message_status = generation.resume_advice_status = "pending"
        session.commit()
        try:
            try:
                resume = ResumeStructure.model_validate_json(generation.resume_structure_json or "")
                jd = JDAnalysis.model_validate_json(generation.jd_analysis_json or "")
            except Exception:
                resume, jd = await _prepare_inputs(session, generation, pipeline, resume_record, job_record)
            result = await pipeline.match_analysis(resume, jd)
            generation.match_result_json = result.value.model_dump_json()
            generation.match_status = "success"
            generation.match_prompt_version = MATCH_PROMPT_VERSION
            _store_trace(session, generation, result.trace)
            session.commit()
            await _run_downstream(session, generation, pipeline, resume, jd, result.value)
        except Exception as exc:
            generation.match_status, generation.match_error = "failed", _safe_module_error(exc)
            generation.hr_message_status = generation.resume_advice_status = "blocked"
            _store_trace(session, generation, _trace_from_exception(exc))
            session.commit()
        return public_generation(generation)

    if not generation.match_result_json:
        raise LLMError("匹配分析尚未成功，无法重跑下游模块。")
    try:
        match = MatchAnalysis.model_validate_json(generation.match_result_json)
        resume = ResumeStructure.model_validate_json(generation.resume_structure_json or "")
        jd = JDAnalysis.model_validate_json(generation.jd_analysis_json or "")
    except Exception:
        # Legacy V1 snapshots did not contain fit_level or structured inputs.
        # Rebuild the current structured contract from the original local files,
        # then recompute Match before retrying a downstream module. The old
        # snapshot itself is never overwritten until the new run succeeds.
        resume, jd = await _prepare_inputs(session, generation, pipeline, resume_record, job_record)
        match_result = await pipeline.match_analysis(resume, jd)
        match = match_result.value
        generation.match_result_json = match.model_dump_json()
        generation.match_status = "success"
        generation.match_prompt_version = MATCH_PROMPT_VERSION
        _store_trace(session, generation, match_result.trace)
        session.commit()
    if module == "hr-message":
        generation.hr_message_status, generation.hr_message_error = "running", None
        session.commit()
        try:
            result = await pipeline.hr_message(resume, jd, match)
            generation.hr_message_json = result.value.model_dump_json()
            generation.hr_message_status, generation.hr_prompt_version = "success", HR_PROMPT_VERSION
            _store_trace(session, generation, result.trace)
        except Exception as exc:
            generation.hr_message_status, generation.hr_message_error = "failed", _safe_module_error(exc)
            _store_trace(session, generation, _trace_from_exception(exc))
    elif module == "resume-advice":
        generation.resume_advice_status, generation.resume_advice_error = "running", None
        session.commit()
        try:
            result = await pipeline.resume_advice(resume, jd, match)
            generation.resume_advice_json = result.value.model_dump_json()
            generation.resume_advice_status = "success"
            generation.resume_advice_prompt_version = RESUME_ADVICE_PROMPT_VERSION
            _store_trace(session, generation, result.trace)
        except Exception as exc:
            generation.resume_advice_status, generation.resume_advice_error = "failed", _safe_module_error(exc)
            _store_trace(session, generation, _trace_from_exception(exc))
    else:
        raise ValueError("Unknown module")
    session.commit()
    return public_generation(generation)
