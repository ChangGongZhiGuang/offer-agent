"""简历文件 → 纯文本。pdf/docx 懒导入, 容错。"""
from __future__ import annotations

import io
from pathlib import Path


class ResumeParseError(RuntimeError):
    """无法从上传文件抽出有效文本 (不支持的格式 / 坏文件 / 空内容)。"""


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ResumeParseError("解析 PDF 需要 pypdf, 请安装 [resume] extra") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise ResumeParseError(f"PDF 解析失败: {exc}") from exc


def _extract_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover
        raise ResumeParseError("解析 Word 需要 python-docx, 请安装 [resume] extra") from exc
    try:
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    except Exception as exc:
        raise ResumeParseError(f"Word 解析失败: {exc}") from exc


def extract_text(file_bytes: bytes, filename: str) -> str:
    """按扩展名分流抽文本; 抽不出有效内容抛 ResumeParseError。"""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        text = _extract_pdf(file_bytes)
    elif ext == ".docx":
        text = _extract_docx(file_bytes)
    elif ext in {".txt", ".md"}:
        text = file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ResumeParseError(f"不支持的简历格式: {ext or '(无扩展名)'}")
    text = text.strip()
    if not text:
        raise ResumeParseError("简历内容为空, 无法解析")
    return text
