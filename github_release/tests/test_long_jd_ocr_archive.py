from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from backend.ai.long_jd import estimate_tokens, semantic_chunks
from backend.ai.schemas import JobTextInput
from backend.errors import DocumentError
from backend.parsers import documents
from backend.services.export_service import generation_markdown


@pytest.mark.parametrize("text", ["JD", "产品经理岗位" * 100, "职责要求\n\n" + "用户研究与数据分析。" * 30000], ids=["short", "medium", "very-long"])
def test_jd_input_has_no_artificial_length_limit(text):
    assert JobTextInput(jd_text=text).jd_text == text


def test_long_jd_chunking_preserves_all_content_without_truncation():
    text = "\n\n".join(f"第{i}段：岗位职责、核心能力、学历要求、到岗时间。" * 100 for i in range(120))
    chunks = semantic_chunks(text, token_budget=1200)
    assert len(chunks) > 1
    compact = lambda value: "".join(value.split())
    assert compact("".join(chunks)) == compact(text)
    assert estimate_tokens(text) > 1200


def test_single_extremely_long_sentence_is_losslessly_bounded():
    text = "岗位职责：" + "必须保留核心能力学历要求到岗时间" * 5000 + "。"
    chunks = semantic_chunks(text, token_budget=900)
    assert len(chunks) > 1
    assert "".join(chunks) == text
    assert all(estimate_tokens(chunk) <= 900 for chunk in chunks)


def _image_bytes(texts: list[str], fmt="JPEG") -> bytes:
    candidates = [
        Path(os.environ.get("WINDIR", "")) / "Fonts" / "msyh.ttc",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    font_path = next((path for path in candidates if path.is_file()), None)
    if font_path is None:
        pytest.skip("No suitable test font is available on this system")
    font = ImageFont.truetype(str(font_path), 34)
    image = Image.new("RGB", (1600, 100 + len(texts) * 70), "white")
    draw = ImageDraw.Draw(image)
    for index, text in enumerate(texts): draw.text((40, 35 + index * 70), text, font=font, fill="black")
    stream = BytesIO(); image.save(stream, fmt, quality=95); return stream.getvalue()


def test_real_local_ocr_chinese_and_mixed_jpg():
    raw = _image_bytes(["岗位 产品运营实习生", "职责 用户研究 数据分析", "Product Operations Intern 2026"])
    result = documents.parse_document(filename="mixed.jpg", raw=raw, kind="job")
    assert result.ocr_used and result.method == "local_ocr"
    assert "Product" in result.text and "2026" in result.text
    assert result.ocr_metadata["engine"] == "RapidOCR"


def test_normal_pdf_uses_embedded_text():
    import pymupdf
    doc = pymupdf.open(); page = doc.new_page(); page.insert_text((72, 72), "Product Manager Job Description with enough embedded text for direct extraction.")
    raw = doc.tobytes(); doc.close()
    result = documents.parse_document(filename="normal.pdf", raw=raw, kind="job")
    assert not result.ocr_used and result.method == "pdf_embedded_text"


def test_scanned_pdf_uses_local_ocr():
    raw_image = _image_bytes(["Job Description", "User Research and Data Analysis"], fmt="PNG")
    import pymupdf
    doc = pymupdf.open(); page = doc.new_page(width=1600, height=300); page.insert_image(page.rect, stream=raw_image)
    raw = doc.tobytes(); doc.close()
    result = documents.parse_document(filename="scan.pdf", raw=raw, kind="job")
    assert result.ocr_used and result.method == "pdf_mixed_ocr" and "User Research" in result.text


def test_ocr_empty_aborts_pipeline(monkeypatch):
    class Empty: txts = []; scores = []
    monkeypatch.setattr(documents, "_OCR_ENGINE", lambda _image: Empty())
    with pytest.raises(DocumentError, match="图片文字识别失败"):
        documents.parse_document(filename="blank.png", raw=_image_bytes(["   "], fmt="PNG"), kind="job")


def test_full_generation_markdown_has_four_sections():
    from datetime import datetime, timezone
    text = generation_markdown(jd_text="JD", match={"match_score": 50, "summary": "S", "strong_matches": [], "gaps": [], "keywords": [], "risks": []}, hr_message={"message": "您好。能尽快到岗。"}, resume_advice={"suggestions": [], "hard_gaps": []}, company="C", position="P", resume_version=3, created_at=datetime.now(timezone.utc))
    for heading in ("# Job Description", "# Match Analysis", "# HR Message", "# Resume Advice"):
        assert heading in text


def test_required_export_formats_and_original_downloads(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.db.session import Base
    from backend.services import export_service, job_service, resume_service

    engine = create_engine(f"sqlite:///{(tmp_path / 'downloads.db').as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    resume_dir = tmp_path / "resumes"; resume_dir.mkdir()
    job_dir = tmp_path / "jobs"; job_dir.mkdir()
    monkeypatch.setattr(resume_service, "RESUME_DIR", resume_dir)
    monkeypatch.setattr(job_service, "JOB_DIR", job_dir)

    with Session() as session:
        resume_raw = b"Candidate resume plain text"
        resume = resume_service.upload_resume(session, filename="resume.txt", raw=resume_raw, mime_type="text/plain")
        resume_path, resume_name, _ = resume_service.download_path(session, resume["id"])
        assert resume_name.endswith(".txt") and resume_path.read_bytes() == resume_raw

        jd_text = job_service.create_text(session, jd_text="Product job description")
        jd_bytes, jd_name, jd_mime = job_service.download(session, jd_text["id"])
        assert jd_name.endswith(".txt") and jd_mime.startswith("text/plain") and jd_bytes.decode() == "Product job description"

        jd_raw = b"Job description uploaded as markdown"
        jd_file = job_service.upload_job(session, filename="job.md", raw=jd_raw, mime_type="text/markdown")
        jd_path, jd_filename, _ = job_service.download(session, jd_file["id"])
        assert jd_filename.endswith(".md") and jd_path.read_bytes() == jd_raw

    now = datetime.now(timezone.utc)
    assert export_service.hr_text({"message": "您好。能尽快到岗。"}).endswith("\n")
    assert export_service.match_markdown({"match_score": 50, "fit_level": "weak_fit", "summary": "S", "strong_matches": [], "gaps": [], "keywords": [], "risks": []}).startswith("# Resume Matcher")
    assert export_service.advice_markdown({"fit_level": "weak_fit", "advice_mode": "reposition", "suggestions": [], "hard_gaps": []}, company="C", position="P", resume_version=1, created_at=now).startswith("# Resume Matcher")


def test_unicode_download_header_has_ascii_fallback_and_utf8_name():
    from backend.api.generations import _download_header
    header = _download_header("影像产品运营_2026-08-12.md")
    assert 'filename="' in header
    assert "filename*=UTF-8''" in header
    header.encode("latin-1")
