from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.ai.llm_client import ClientSettings
from backend.ai.schemas import HRMessage, MatchAnalysis, ResumeAdvice
from backend.ai.structured import StructuredTrace, generate_structured, normalize_match_analysis, normalize_resume_advice
from backend.errors import StructuredOutputError


def valid_match(**overrides):
    value = {
        "match_score": 82, "fit_level": "partial_fit", "summary": "存在直接匹配证据。",
        "strong_matches": [{"requirement_id": "REQ_01", "requirement": "用户研究", "resume_evidence": "负责用户访谈", "match_type": "direct", "reason": "职责直接对应"}],
        "gaps": [{"requirement_id": "REQ_02", "requirement": "行业经验", "severity": "medium", "reason": "未提供行业证据"}],
        "keywords": ["用户研究"], "risks": ["行业经验待确认"],
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize("score", [82, "82", "82%"])
def test_match_score_normalizes_safe_equivalents(score):
    normalized = normalize_match_analysis(valid_match(match_score=score))
    assert MatchAnalysis.model_validate(normalized).match_score == 82


def test_match_score_out_of_range_fails():
    with pytest.raises(ValidationError):
        MatchAnalysis.model_validate(normalize_match_analysis(valid_match(match_score=120)))


@pytest.mark.parametrize("severity,expected", [("high", "high"), ("高", "high")])
def test_severity_normalizes_safe_equivalents(severity, expected):
    value = valid_match(gaps=[{"requirement_id": "REQ_02", "requirement": "行业经验", "severity": severity, "reason": "无证据"}])
    assert MatchAnalysis.model_validate(normalize_match_analysis(value)).gaps[0].severity == expected


def test_unknown_severity_fails():
    value = valid_match(gaps=[{"requirement_id": "REQ_02", "requirement": "行业经验", "severity": "严重", "reason": "无证据"}])
    with pytest.raises(ValidationError):
        MatchAnalysis.model_validate(normalize_match_analysis(value))


def test_missing_nested_evidence_has_exact_path():
    value = valid_match(strong_matches=[{"requirement_id": "REQ_01", "requirement": "用户研究", "match_type": "direct", "reason": "对应"}])
    with pytest.raises(ValidationError) as caught:
        MatchAnalysis.model_validate(value)
    assert caught.value.errors()[0]["loc"] == ("strong_matches", 0, "resume_evidence")


def test_renamed_field_is_not_accepted():
    value = valid_match(); value["matchScore"] = value.pop("match_score")
    with pytest.raises(ValidationError) as caught:
        MatchAnalysis.model_validate(normalize_match_analysis(value))
    assert {error["type"] for error in caught.value.errors()} == {"missing", "extra_forbidden"}


class SequenceClient:
    settings = ClientSettings(provider="Fake", model="fake-model", base_url="https://example.com", api_key="fake-key")
    def __init__(self, outputs): self.outputs, self.calls = iter(outputs), 0
    async def complete_text(self, **_kwargs): self.calls += 1; return next(self.outputs)


async def test_first_invalid_then_one_shot_repair_valid():
    invalid = valid_match(strong_matches=[{"requirement_id": "REQ_01", "requirement": "用户研究", "match_type": "direct", "reason": "对应"}])
    client = SequenceClient([json.dumps(invalid, ensure_ascii=False), json.dumps(valid_match(), ensure_ascii=False)])
    result = await generate_structured(client=client, module="match_analysis", prompt_version="v2", system_prompt="role", task_prompt="task", schema=MatchAnalysis)
    assert result.value.match_score == 82
    assert result.trace.repair_attempted is True
    assert result.trace.repair_prompt_version == "v1"
    assert result.trace.validation_result == "repaired_valid"
    assert result.trace.validation_errors[0]["field_path"] == "strong_matches.0.resume_evidence"
    assert client.calls == 2


async def test_invalid_after_repair_returns_structured_debug_error():
    invalid = valid_match(match_score=120)
    client = SequenceClient([json.dumps(invalid), json.dumps(invalid)])
    with pytest.raises(StructuredOutputError) as caught:
        await generate_structured(client=client, module="match_analysis", prompt_version="v2", system_prompt="role", task_prompt="task", schema=MatchAnalysis)
    assert caught.value.trace.validation_result == "invalid_after_repair"
    assert caught.value.trace.repair_validation_errors[0]["field_path"] == "match_score"
    assert client.calls == 2


def test_schema_is_strict_and_includes_fit_level():
    schema = MatchAnalysis.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"match_score", "fit_level", "summary", "strong_matches", "gaps", "keywords", "risks"}


def test_all_business_output_schemas_forbid_extra_fields():
    from backend.ai.schemas import JDAnalysis, ResumeStructure
    for model in (ResumeStructure, JDAnalysis, MatchAnalysis, HRMessage, ResumeAdvice):
        assert model.model_json_schema()["additionalProperties"] is False


def test_add_if_true_requires_confirmation():
    value = {
        "fit_level": "partial_fit", "advice_mode": "bridge", "overall_direction": "桥接真实经验",
        "suggestions": [{"priority": "高", "section": "项目", "location": "项目 A", "action_type": "如属实则补充", "original": "", "problem": "缺少数据", "suggestion": "如果有真实数据则补充", "reason": "JD关注结果", "can_apply_directly": False, "needs_user_confirmation": True}],
        "hard_gaps": [], "user_input_needed": [], "not_recommended_changes": [],
    }
    normalized = normalize_resume_advice(value)
    assert ResumeAdvice.model_validate(normalized).suggestions[0].action_type == "add_if_true"
    normalized["suggestions"][0]["can_apply_directly"] = True
    with pytest.raises(ValidationError): ResumeAdvice.model_validate(normalized)


def test_hr_message_extra_field_is_rejected():
    with pytest.raises(ValidationError) as caught:
        HRMessage.model_validate({
            "status": "ready", "opening": "您好，关注到贵司岗位。", "self_intro": "我是产品专业学生。",
            "fit_points": [], "interest": "希望进一步沟通。", "availability": "能尽快到岗。",
            "message": "您好，关注到贵司岗位。我是产品专业学生。希望进一步沟通。能尽快到岗。",
            "evidence_used": [], "missing_fields": [], "api_key": "must-never-be-accepted",
        })
    assert any(item["type"] == "extra_forbidden" for item in caught.value.errors())


def test_debug_trace_redacts_sensitive_values():
    trace = StructuredTrace(module="match_analysis", prompt_version="v2", provider="Fake", model="fake-model", request_id="request-1", raw_output='{"api_key":"should-not-appear","summary":"ok"}', parsed_json={"authorization": "Bearer should-not-appear"}, diagnostics={"estimated_tokens": 12345})
    public = json.dumps(trace.public_dict(), ensure_ascii=False)
    assert "should-not-appear" not in public and "[REDACTED]" in public
    assert '"estimated_tokens": 12345' in public
