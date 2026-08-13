from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.session import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ApiConfig(Base):
    __tablename__ = "api_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(500), default="")
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    key_persisted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="我的简历")
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    versions: Mapped[list["ResumeVersion"]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    file_path: Mapped[str] = mapped_column(String(600))
    parsed_text: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    parser_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ocr_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ocr_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_resume_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resume: Mapped[Resume] = relationship(back_populates="versions")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(String(120), default="")
    position: Mapped[str] = mapped_column(String(120), default="")
    source_type: Mapped[str] = mapped_column(String(20))
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    jd_text: Mapped[str] = mapped_column(Text)
    parser_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ocr_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ocr_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_jd_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), index=True)
    resume_version_id: Mapped[int] = mapped_column(ForeignKey("resume_versions.id", ondelete="RESTRICT"), index=True)
    match_status: Mapped[str] = mapped_column(String(20), default="pending")
    hr_message_status: Mapped[str] = mapped_column(String(20), default="pending")
    resume_advice_status: Mapped[str] = mapped_column(String(20), default="pending")
    match_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    hr_message_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_advice_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    hr_message_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_advice_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_structure_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_structure_prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    jd_analysis_prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    structured_repair_prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    match_prompt_version: Mapped[str] = mapped_column(String(30))
    hr_prompt_version: Mapped[str] = mapped_column(String(30))
    resume_advice_prompt_version: Mapped[str] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    job: Mapped[Job] = relationship()
    resume_version: Mapped[ResumeVersion] = relationship()
    debug_traces: Mapped[list["GenerationDebugTrace"]] = relationship(
        back_populates="generation",
        cascade="all, delete-orphan",
        order_by="GenerationDebugTrace.created_at",
    )


class GenerationDebugTrace(Base):
    __tablename__ = "generation_debug_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generation_id: Mapped[int] = mapped_column(
        ForeignKey("generations.id", ondelete="CASCADE"), index=True
    )
    module: Mapped[str] = mapped_column(String(40), index=True)
    request_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    prompt_version: Mapped[str] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    trace_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    generation: Mapped[Generation] = relationship(back_populates="debug_traces")
