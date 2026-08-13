from __future__ import annotations

from io import BytesIO

from docx import Document
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.db.models import ApiConfig, Generation, Job, ResumeVersion
from backend.db.session import Base
from backend.services import generation_service, job_service, resume_service
from tests.test_v25_pipeline import FakeClient


def docx_bytes(text: str) -> bytes:
    stream = BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(stream)
    return stream.getvalue()


def test_resume_versions_files_and_generation_relation(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    resume_dir = tmp_path / "resumes"; resume_dir.mkdir()
    job_dir = tmp_path / "jobs"; job_dir.mkdir()
    monkeypatch.setattr(resume_service, "RESUME_DIR", resume_dir)
    monkeypatch.setattr(job_service, "JOB_DIR", job_dir)

    with Session() as session:
        first_raw = docx_bytes("产品经理简历。负责用户访谈、需求分析和产品方案设计。" * 8)
        second_raw = docx_bytes("产品经理简历第二版。负责用户访谈、需求分析、上线复盘和跨团队协作。" * 8)
        first = resume_service.upload_resume(session, filename="resume_v1.docx", raw=first_raw, mime_type=None)
        second = resume_service.upload_resume(session, filename="resume_v2.docx", raw=second_raw, mime_type=None)
        versions = resume_service.list_versions(session)
        assert [item["version_number"] for item in versions] == [2, 1]
        assert versions[0]["is_current"] is True
        path, _, _ = resume_service.download_path(session, first["id"])
        assert path.read_bytes() == first_raw

        job_a = job_service.create_text(session, jd_text="岗位 A：负责用户研究、需求分析、产品规划与协作落地。" * 8)
        job_b = job_service.create_text(session, jd_text="岗位 B：负责增长实验、数据分析、渠道策略与迭代复盘。" * 8)
        session.add(ApiConfig(provider="DeepSeek", model="deepseek-chat", base_url="https://api.deepseek.com", is_configured=True, key_persisted=True))
        session.commit()

        monkeypatch.setattr(generation_service, "make_client", lambda _session, _store: FakeClient())
        import asyncio
        gen_a = asyncio.run(generation_service.create_generation(session, object(), resume_version_id=second["id"], job_id=job_a["id"]))
        gen_b = asyncio.run(generation_service.create_generation(session, object(), resume_version_id=second["id"], job_id=job_b["id"]))
        detail_a = generation_service.public_generation(generation_service.get_generation(session, gen_a["id"]))
        detail_b = generation_service.public_generation(generation_service.get_generation(session, gen_b["id"]))
        assert detail_a["job_id"] == job_a["id"]
        assert detail_b["job_id"] == job_b["id"]
        assert detail_a["id"] != detail_b["id"]
        assert detail_a["resume_structure"] is not None
        assert detail_a["jd_analysis"] is not None
        assert detail_a["match_result"] is not None
        assert detail_a["hr_message"] is not None
        assert detail_a["resume_advice"] is not None
        assert detail_b["resume_advice"] is not None
        assert set(detail_a["prompt_versions"]) == {"resume_structure", "jd_analysis", "match_analysis", "hr_message", "resume_advice", "structured_repair"}

    columns = {column["name"] for column in inspect(engine).get_columns("api_configs")}
    assert "api_key" not in columns
    assert "plaintext_api_key" not in columns

    # A brand-new Session simulates closing/reopening the local application.
    with Session() as reopened:
        saved_generation = reopened.get(Generation, gen_a["id"])
        assert saved_generation is not None
        assert reopened.get(Job, saved_generation.job_id).jd_text.startswith("岗位 A")
        assert reopened.get(ResumeVersion, saved_generation.resume_version_id).version_number == 2
        persisted = generation_service.public_generation(saved_generation)
        assert all(persisted[key] is not None for key in (
            "resume_structure", "jd_analysis", "match_result", "hr_message", "resume_advice"
        ))
