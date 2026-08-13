from __future__ import annotations

import json

import pytest

from backend.ai.llm_client import ClientSettings
from backend.ai.pipeline import (
    ResumeMatcherPipeline,
    _evidence_supported,
    _jd_fact_validator,
    availability_policy,
)
from backend.ai.schemas import AvailabilityRequirements, JDAnalysis, MatchAnalysis, ResumeStructure
from backend.errors import LLMError


def resume_value():
    return {"candidate": {"name": "张三", "current_title": "产品实习生", "location": "深圳"}, "education": [], "work_experience": [], "projects": [{"name": "用户研究", "role": "负责人", "start_date": None, "end_date": None, "responsibilities": ["访谈"], "methods": ["用户访谈"], "outcomes": ["形成报告"], "metrics": [], "tools": [], "domains": ["产品"], "source_evidence": "负责访谈并形成报告"}], "skills": {"hard_skills": ["用户研究"], "software_tools": [], "domain_skills": ["产品"], "languages": []}, "uncertainties": []}


def jd_value(employment_type="internship", months=3, requirement="用户研究"):
    return {"job_title": "产品运营实习生", "company": "示例公司", "employment_type": employment_type, "department": None, "location": None, "work_mode": None, "responsibilities": [{"id": "RESP_01", "content": f"负责{requirement}", "importance": "must", "source_evidence": f"负责{requirement}"}], "core_requirements": [{"id": "REQ_01", "category": "能力", "requirement": requirement, "importance": "must", "source_evidence": requirement}], "preferred_requirements": [], "hard_constraints": [], "skills": [requirement], "domain_context": ["产品"], "keywords": [requirement], "availability_requirements": {"earliest_start_time": None, "internship_duration_months": months, "days_per_week": None, "notes": []}, "ambiguities": []}


def match_value():
    return {"match_score": 76, "fit_level": "partial_fit", "summary": "存在直接产品经验，也有明确缺口。", "strong_matches": [{"requirement_id": "REQ_01", "requirement": "用户研究", "resume_evidence": "负责访谈并形成报告", "match_type": "direct", "reason": "职责直接对应"}], "gaps": [], "keywords": ["用户研究"], "risks": []}


class FakeClient:
    def __init__(self, fail: str | None = None):
        self.fail, self.calls = fail, []
        self.settings = ClientSettings(provider="Fake", model="fake-model", base_url="https://example.com", api_key="fake-key")

    async def complete_text(self, *, schema_name, user_prompt="", **_kwargs):
        self.calls.append(schema_name)
        if self.fail and schema_name.startswith(self.fail): raise LLMError(f"{self.fail} failed")
        if schema_name.startswith("resume_structure"): return json.dumps(resume_value(), ensure_ascii=False)
        if schema_name.startswith("jd_analysis"):
            requirement = "增长实验" if "增长实验" in user_prompt else "用户研究"
            return json.dumps(jd_value(requirement=requirement), ensure_ascii=False)
        if schema_name.startswith("match_analysis"):
            value = match_value()
            if "增长实验" in user_prompt:
                value["strong_matches"][0].update(requirement="增长实验")
            return json.dumps(value, ensure_ascii=False)
        if schema_name.startswith("hr_message"):
            availability = "目前可实习6个月，每周到岗5天，能立即到岗。"
            value = {"status": "ready", "opening": "您好，关注到贵司产品运营实习生岗位。", "self_intro": "我目前有产品项目实践。", "fit_points": [{"jd_requirement": "用户研究", "resume_evidence": "负责用户访谈", "sentence": "我曾负责用户访谈并形成研究报告。"}], "interest": "岗位方向与我的发展方向一致，希望进一步沟通。", "availability": availability, "message": "ignored", "evidence_used": ["负责用户访谈"], "missing_fields": []}
            return json.dumps(value, ensure_ascii=False)
        value = {"fit_level": "partial_fit", "advice_mode": "bridge", "overall_direction": "突出真实用户研究经验。", "suggestions": [{"priority": "high", "section": "项目经历", "location": "用户研究", "action_type": "rewrite", "original": "负责访谈", "problem": "未说明方法", "suggestion": "补充真实访谈方法", "reason": "对应岗位要求", "can_apply_directly": True, "needs_user_confirmation": False}], "hard_gaps": [], "user_input_needed": [], "not_recommended_changes": []}
        return json.dumps(value, ensure_ascii=False)


async def test_five_business_modules_are_ordered_and_downstream_parallel():
    client = FakeClient(); outcome = await ResumeMatcherPipeline(client).run("负责访谈并形成报告", "负责用户研究")
    assert all([outcome.resume_structure, outcome.jd_analysis, outcome.match, outcome.hr_message, outcome.resume_advice])
    assert [call.split("_")[0] for call in client.calls[:3]] == ["resume", "jd", "match"]
    assert {"hr_message_v2", "resume_advice_v2"}.issubset(set(client.calls))


async def test_hr_failure_does_not_drop_resume_advice():
    outcome = await ResumeMatcherPipeline(FakeClient(fail="hr_message")).run("负责访谈并形成报告", "负责用户研究")
    assert outcome.match and outcome.hr_message is None and outcome.hr_message_error and outcome.resume_advice


async def test_match_failure_blocks_downstream_modules():
    client = FakeClient(fail="match_analysis"); outcome = await ResumeMatcherPipeline(client).run("负责访谈并形成报告", "负责用户研究")
    assert outcome.match is None and outcome.hr_message is None and outcome.resume_advice is None
    assert not any(call.startswith("hr_message") or call.startswith("resume_advice") for call in client.calls)


def test_availability_policy_defaults_and_conflict():
    internship = JDAnalysis.model_validate(jd_value(months=3))
    assert availability_policy(internship) == "目前可实习6个月，每周到岗5天，能立即到岗。"
    long_internship = JDAnalysis.model_validate(jd_value(months=8))
    assert "实习6个月" in availability_policy(long_internship) and "8个月" not in availability_policy(long_internship) and "进一步沟通" in availability_policy(long_internship)
    full_time = JDAnalysis.model_validate(jd_value(employment_type="full_time", months=None))
    assert availability_policy(full_time) == "到岗方面可以尽快安排。"


def test_combined_evidence_requires_high_source_coverage_and_source_numbers():
    source = "中南林业科技大学 建筑学 学士 2020.09-2025.06；深圳大学 风景园林 硕士在读 2025.09-至今"
    combined = "中南林业科技大学建筑学学士（2020.09-2025.06），深圳大学风景园林硕士在读（2025.09-至今）"
    assert _evidence_supported(combined, source)
    assert not _evidence_supported(combined.replace("2025.09", "2030.09"), source)
    assert not _evidence_supported("完全主导商业化增长并覆盖百万用户", source)


def test_jd_ambiguity_can_truthfully_report_absent_information_without_evidence():
    value = jd_value()
    value["company"] = None
    value["ambiguities"] = [{
        "field": "company",
        "issue": "JD 未提供公司名称",
        "source_evidence": "",
    }]
    jd = JDAnalysis.model_validate(value)
    assert _jd_fact_validator("负责用户研究")(jd) == []


def test_jd_ambiguity_rejects_invented_nonempty_evidence():
    value = jd_value()
    value["ambiguities"] = [{
        "field": "company",
        "issue": "JD 未提供公司名称",
        "source_evidence": "原文明确写了某公司",
    }]
    errors = _jd_fact_validator("负责用户研究")(JDAnalysis.model_validate(value))
    assert errors[0]["field_path"] == "ambiguities.0.source_evidence"


async def test_resume_metric_not_present_in_raw_text_triggers_one_shot_repair():
    first = resume_value()
    first["projects"][0]["metrics"] = [{"metric": "提效", "value": "60%", "source_evidence": "提效60%"}]
    repaired = resume_value()

    class MetricClient(FakeClient):
        async def complete_text(self, *, schema_name, **_kwargs):
            self.calls.append(schema_name)
            return json.dumps(first if len(self.calls) == 1 else repaired, ensure_ascii=False)

    result = await ResumeMatcherPipeline(MetricClient()).resume_structure("负责用户访谈并形成报告")
    assert result.value.projects[0].metrics == []
    assert result.trace.repair_attempted is True
    assert result.trace.validation_errors[0]["field_path"] == "projects.0.metrics.0.value"


async def test_resume_metric_present_in_raw_text_is_allowed():
    value = resume_value()
    value["projects"][0]["metrics"] = [{"metric": "提效", "value": "60%", "source_evidence": "提效60%"}]

    class MetricClient(FakeClient):
        async def complete_text(self, **_kwargs):
            return json.dumps(value, ensure_ascii=False)

    result = await ResumeMatcherPipeline(MetricClient()).resume_structure("通过工作流提效60%")
    assert result.value.projects[0].metrics[0].value == "60%"


async def test_resume_advice_unknown_percentage_is_removed_by_repair():
    invalid = {"fit_level": "partial_fit", "advice_mode": "bridge", "overall_direction": "突出真实经验。", "suggestions": [{"priority": "high", "section": "项目", "location": "用户研究", "action_type": "rewrite", "original": "负责访谈", "problem": "结果不足", "suggestion": "改为提效60%", "reason": "强调结果", "can_apply_directly": True, "needs_user_confirmation": False}], "hard_gaps": [], "user_input_needed": [], "not_recommended_changes": []}
    valid = {**invalid, "suggestions": [{**invalid["suggestions"][0], "suggestion": "补充原文已有的真实结果"}]}

    class AdviceClient(FakeClient):
        async def complete_text(self, **_kwargs):
            self.calls.append(_kwargs["schema_name"])
            return json.dumps(invalid if len(self.calls) == 1 else valid, ensure_ascii=False)

    pipeline = ResumeMatcherPipeline(AdviceClient())
    result = await pipeline.resume_advice(
        ResumeStructure.model_validate(resume_value()),
        JDAnalysis.model_validate(jd_value()),
        MatchAnalysis.model_validate(match_value()),
    )
    assert "60%" not in result.value.suggestions[0].suggestion
    assert result.trace.repair_attempted is True


async def test_resume_advice_unconfirmed_metric_must_be_add_if_true():
    invalid = {
        "fit_level": "partial_fit",
        "advice_mode": "bridge",
        "overall_direction": "突出真实经验。",
        "suggestions": [{
            "priority": "high", "section": "项目", "location": "用户研究",
            "action_type": "rewrite", "original": "负责访谈", "problem": "结果不足",
            "suggestion": "补充真实可量化成果；若无数据则需用户确认。",
            "reason": "强调结果", "can_apply_directly": False,
            "needs_user_confirmation": True,
        }],
        "hard_gaps": [], "user_input_needed": [], "not_recommended_changes": [],
    }
    valid = {
        **invalid,
        "suggestions": [{
            **invalid["suggestions"][0],
            "action_type": "add_if_true",
            "suggestion": "如果实际有对应量化成果，可以补充真实数值。",
        }],
    }

    class AdviceClient(FakeClient):
        async def complete_text(self, **_kwargs):
            self.calls.append(_kwargs["schema_name"])
            return json.dumps(invalid if len(self.calls) == 1 else valid, ensure_ascii=False)

    result = await ResumeMatcherPipeline(AdviceClient()).resume_advice(
        ResumeStructure.model_validate(resume_value()),
        JDAnalysis.model_validate(jd_value()),
        MatchAnalysis.model_validate(match_value()),
    )
    suggestion = result.value.suggestions[0]
    assert suggestion.action_type == "add_if_true"
    assert suggestion.needs_user_confirmation is True
    assert suggestion.can_apply_directly is False
    assert result.trace.repair_attempted is True


async def test_resume_advice_any_conditional_new_fact_must_be_add_if_true():
    invalid = {
        "fit_level": "partial_fit", "advice_mode": "bridge",
        "overall_direction": "突出真实经验。",
        "suggestions": [{
            "priority": "high", "section": "项目", "location": "内容运营",
            "action_type": "rewrite", "original": "设计工作流", "problem": "没有上线反馈",
            "suggestion": "如果项目有实际用户反馈，可补充测试和复盘过程。",
            "reason": "对应岗位要求", "can_apply_directly": False,
            "needs_user_confirmation": True,
        }], "hard_gaps": [], "user_input_needed": [], "not_recommended_changes": [],
    }
    valid = {
        **invalid,
        "suggestions": [{**invalid["suggestions"][0], "action_type": "add_if_true"}],
    }

    class AdviceClient(FakeClient):
        async def complete_text(self, **_kwargs):
            self.calls.append(_kwargs["schema_name"])
            return json.dumps(invalid if len(self.calls) == 1 else valid, ensure_ascii=False)

    result = await ResumeMatcherPipeline(AdviceClient()).resume_advice(
        ResumeStructure.model_validate(resume_value()),
        JDAnalysis.model_validate(jd_value()),
        MatchAnalysis.model_validate(match_value()),
    )
    assert result.value.suggestions[0].action_type == "add_if_true"
    assert result.trace.repair_attempted is True


@pytest.mark.parametrize("fit_level,expected", [
    ("strong_fit", 2), ("partial_fit", 2), ("weak_fit", 1), ("insufficient_evidence", 0),
])
async def test_hr_fit_points_follow_match_level(fit_level, expected):
    match = match_value(); match["fit_level"] = fit_level
    if fit_level == "insufficient_evidence": match["match_score"] = 0

    class HRClient(FakeClient):
        async def complete_text(self, *, schema_name, **_kwargs):
            availability = "目前可实习6个月，每周到岗5天，能立即到岗。"
            points = [{"jd_requirement": "用户研究", "resume_evidence": "负责用户访谈", "sentence": f"能力点{i}。"} for i in range(2)]
            return json.dumps({"status": "ready", "opening": "您好，关注到贵司产品运营实习生岗位。", "self_intro": "我目前有产品项目实践。", "fit_points": points, "interest": "岗位方向与我的发展方向一致，希望进一步沟通。", "availability": availability, "message": "ignored", "evidence_used": ["负责用户访谈"], "missing_fields": []}, ensure_ascii=False)

    result = await ResumeMatcherPipeline(HRClient()).hr_message(
        ResumeStructure.model_validate(resume_value()), JDAnalysis.model_validate(jd_value()),
        MatchAnalysis.model_validate(match),
    )
    assert len(result.value.fit_points) == expected
    assert len(result.value.message) <= 180
    assert result.value.message.startswith("您好")
    assert result.value.message.endswith(result.value.availability)


async def test_hr_compaction_uses_natural_chinese_and_avoids_overclaiming():
    long_text = "我曾负责多来源资料收集与分类归纳，搭建过信息识别框架，也拆解过影像产品功能与用户场景，能胜任竞品信息整理与行业动向分析。"

    class LongHRClient(FakeClient):
        async def complete_text(self, **_kwargs):
            availability = "目前可实习6个月，每周到岗5天，能立即到岗。"
            return json.dumps({"status": "ready", "opening": "您好，关注到贵司正在招聘影像产品相关实习岗位，想和您简单沟通一下。", "self_intro": "我目前是深圳大学风景园林硕士ongoing，本科建筑学，具备较强的调研与数据分析能力。", "fit_points": [{"jd_requirement": "用户研究", "resume_evidence": "负责访谈并形成报告", "sentence": long_text}], "interest": "这个岗位的工作方向与我希望继续发展的方向比较一致，也很希望有机会进一步沟通。", "availability": availability, "message": "ignored", "evidence_used": ["负责访谈并形成报告"], "missing_fields": []}, ensure_ascii=False)

    resume = resume_value()
    resume["education"] = [{"institution": "深圳大学", "degree": "硕士", "major": "风景园林", "status": "ongoing", "start_date": "2025.09", "end_date": None, "gpa": None, "highlights": [], "source_evidence": "深圳大学 风景园林 硕士在读"}]
    result = await ResumeMatcherPipeline(LongHRClient()).hr_message(
        ResumeStructure.model_validate(resume), JDAnalysis.model_validate(jd_value()),
        MatchAnalysis.model_validate(match_value()),
    )
    assert "ongoing" not in result.value.message
    assert "硕士在读" in result.value.message
    assert "能胜任" not in result.value.message
    assert len(result.value.message) <= 180
