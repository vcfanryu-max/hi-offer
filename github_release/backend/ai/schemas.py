from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Candidate(StrictModel):
    name: str | None = None
    current_title: str | None = None
    location: str | None = None


class Education(StrictModel):
    institution: str
    degree: str
    major: str
    status: str
    start_date: str | None = None
    end_date: str | None = None
    gpa: str | None = None
    highlights: list[str] = Field(default_factory=list)
    source_evidence: str


class ResumeMetric(StrictModel):
    metric: str
    value: str
    source_evidence: str


class WorkExperience(StrictModel):
    company: str
    title: str
    employment_type: str
    start_date: str | None = None
    end_date: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    metrics: list[ResumeMetric] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    source_evidence: str


class ResumeProject(StrictModel):
    name: str
    role: str
    start_date: str | None = None
    end_date: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    metrics: list[ResumeMetric] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    source_evidence: str


class ResumeSkills(StrictModel):
    hard_skills: list[str] = Field(default_factory=list)
    software_tools: list[str] = Field(default_factory=list)
    domain_skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class Uncertainty(StrictModel):
    field: str
    issue: str
    source_evidence: str


class ResumeStructure(StrictModel):
    candidate: Candidate
    education: list[Education] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    projects: list[ResumeProject] = Field(default_factory=list)
    skills: ResumeSkills
    uncertainties: list[Uncertainty] = Field(default_factory=list)


class JDResponsibility(StrictModel):
    id: str = Field(pattern=r"^RESP_[0-9]{2,}$")
    content: str = Field(min_length=1)
    importance: Literal["must", "should", "nice_to_have"]
    source_evidence: str = Field(min_length=1)


class JDCoreRequirement(StrictModel):
    id: str = Field(pattern=r"^REQ_[0-9]{2,}$")
    category: str
    requirement: str = Field(min_length=1)
    importance: Literal["must", "should", "nice_to_have"]
    source_evidence: str = Field(min_length=1)


class JDPreferredRequirement(StrictModel):
    id: str = Field(pattern=r"^PREF_[0-9]{2,}$")
    category: str
    requirement: str = Field(min_length=1)
    source_evidence: str = Field(min_length=1)


class JDHardConstraint(StrictModel):
    id: str = Field(pattern=r"^HARD_[0-9]{2,}$")
    category: str
    requirement: str = Field(min_length=1)
    source_evidence: str = Field(min_length=1)


class AvailabilityRequirements(StrictModel):
    earliest_start_time: str | None = None
    internship_duration_months: int | None = Field(default=None, ge=1)
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    notes: list[str] = Field(default_factory=list)


class JDAmbiguity(StrictModel):
    field: str
    issue: str
    source_evidence: str


class JDAnalysis(StrictModel):
    job_title: str | None = None
    company: str | None = None
    employment_type: Literal["full_time", "internship", "part_time", "contract", "unknown"]
    department: str | None = None
    location: str | None = None
    work_mode: str | None = None
    responsibilities: list[JDResponsibility] = Field(default_factory=list)
    core_requirements: list[JDCoreRequirement] = Field(default_factory=list)
    preferred_requirements: list[JDPreferredRequirement] = Field(default_factory=list)
    hard_constraints: list[JDHardConstraint] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    domain_context: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    availability_requirements: AvailabilityRequirements
    ambiguities: list[JDAmbiguity] = Field(default_factory=list)


class StrongMatch(StrictModel):
    requirement_id: str = Field(min_length=1)
    requirement: str = Field(min_length=1)
    resume_evidence: str = Field(min_length=1)
    match_type: Literal["direct", "transferable"]
    reason: str = Field(min_length=1)


class Gap(StrictModel):
    requirement_id: str = Field(min_length=1)
    requirement: str = Field(min_length=1)
    severity: Literal["high", "medium", "low"]
    reason: str = Field(min_length=1)


class MatchAnalysis(StrictModel):
    match_score: int = Field(strict=True, ge=0, le=100)
    fit_level: Literal["strong_fit", "partial_fit", "weak_fit", "insufficient_evidence"]
    summary: str = Field(min_length=1)
    strong_matches: list[StrongMatch] = Field(max_length=8)
    gaps: list[Gap] = Field(max_length=8)
    keywords: list[str] = Field(max_length=16)
    risks: list[str] = Field(max_length=8)

    @field_validator("keywords", "risks")
    @classmethod
    def remove_blanks(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class HRFitPoint(StrictModel):
    jd_requirement: str
    resume_evidence: str
    sentence: str


class HRMessage(StrictModel):
    status: Literal["ready", "needs_input"]
    opening: str
    self_intro: str
    fit_points: list[HRFitPoint] = Field(max_length=2)
    interest: str
    availability: str
    message: str = Field(max_length=180)
    evidence_used: list[str] = Field(max_length=6)
    missing_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ready_message(self):
        if self.status == "ready":
            for name in ("opening", "self_intro", "interest", "availability", "message"):
                if not getattr(self, name).strip():
                    raise ValueError(f"{name} must be non-empty when status is ready")
            if not self.opening.startswith("您好"):
                raise ValueError("opening must begin with 您好")
            if not self.message.rstrip().endswith(self.availability.rstrip()):
                raise ValueError("availability must be the final part of message")
        return self


class ResumeSuggestion(StrictModel):
    priority: Literal["high", "medium", "low"]
    section: str = Field(min_length=1)
    location: str = Field(min_length=1)
    action_type: Literal["rewrite", "reorder", "remove", "clarify", "add_if_true"]
    original: str
    problem: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    can_apply_directly: bool
    needs_user_confirmation: bool

    @model_validator(mode="after")
    def validate_conditional_change(self):
        if self.needs_user_confirmation and self.can_apply_directly:
            raise ValueError("a suggestion that needs confirmation cannot apply directly")
        if self.action_type == "add_if_true":
            if self.can_apply_directly or not self.needs_user_confirmation:
                raise ValueError("add_if_true must require confirmation and cannot apply directly")
        return self


class HardGap(StrictModel):
    requirement: str
    reason: str
    can_fix_by_rewriting: Literal[False]
    recommended_next_step: str


class ResumeAdvice(StrictModel):
    fit_level: Literal["strong_fit", "partial_fit", "weak_fit", "insufficient_evidence"]
    advice_mode: Literal["polish", "bridge", "reposition", "needs_input"]
    overall_direction: str
    suggestions: list[ResumeSuggestion] = Field(max_length=12)
    hard_gaps: list[HardGap] = Field(default_factory=list, max_length=8)
    user_input_needed: list[str] = Field(default_factory=list)
    not_recommended_changes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mode(self):
        expected = {
            "strong_fit": "polish",
            "partial_fit": "bridge",
            "weak_fit": "reposition",
            "insufficient_evidence": "needs_input",
        }[self.fit_level]
        if self.advice_mode != expected:
            raise ValueError(f"advice_mode must be {expected} for {self.fit_level}")
        return self


class ModuleRun(StrictModel):
    status: Literal["pending", "running", "success", "failed", "blocked"]
    error: str | None = None


class GenerationRequest(StrictModel):
    resume_version_id: int
    job_id: int


class ProviderConfigInput(StrictModel):
    provider: Literal["DeepSeek", "OpenAI", "Custom"]
    model: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=8, max_length=500)
    base_url: str = Field(default="", max_length=500)


class ProviderConfigPublic(StrictModel):
    provider: str = ""
    model: str = ""
    base_url: str = ""
    is_configured: bool = False
    key_persisted: bool = False
    updated_at: str | None = None


class JobTextInput(StrictModel):
    jd_text: str
    company: str = Field(default="", max_length=120)
    position: str = Field(default="", max_length=120)

    @field_validator("jd_text")
    @classmethod
    def require_non_whitespace(cls, value: str) -> str:
        if not re.search(r"\S", value):
            raise ValueError("JD 不能为空。")
        return value
