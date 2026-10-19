import importlib.util

import pytest

from interviewforge.resume.parser import ResumeParseError, extract_text

_HAS_DOCX = importlib.util.find_spec("docx") is not None
_HAS_PYPDF = importlib.util.find_spec("pypdf") is not None


def test_txt_passthrough():
    assert extract_text("你好 Redis".encode("utf-8"), "resume.txt") == "你好 Redis"


def test_md_passthrough():
    assert "Kafka" in extract_text(b"# resume\nKafka", "cv.md")


def test_unsupported_extension_raises():
    with pytest.raises(ResumeParseError):
        extract_text(b"...", "resume.rtf")


def test_empty_text_raises():
    with pytest.raises(ResumeParseError):
        extract_text(b"   \n  ", "resume.txt")


@pytest.mark.skipif(not _HAS_DOCX, reason="python-docx 未安装")
def test_docx_extraction(tmp_path):
    import docx
    p = tmp_path / "cv.docx"
    d = docx.Document()
    d.add_paragraph("精通 Redis 与 MySQL")
    d.save(p)
    assert "Redis" in extract_text(p.read_bytes(), "cv.docx")


@pytest.mark.skipif(not _HAS_PYPDF, reason="pypdf 未安装")
def test_corrupt_pdf_raises():
    with pytest.raises(ResumeParseError):
        extract_text(b"%PDF-broken", "cv.pdf")
