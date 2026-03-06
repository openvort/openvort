"""Document parsing and chunking for knowledge base."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from openvort.utils.logging import get_logger

log = get_logger("plugins.knowledge.chunker")

# ~500 tokens ≈ ~2000 chars for Chinese/English mixed text
DEFAULT_CHUNK_SIZE = 2000
DEFAULT_CHUNK_OVERLAP = 200


@dataclass
class Chunk:
    """A text chunk from a document."""
    index: int
    content: str
    metadata: dict = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return len(self.content) // 4 + 1


def parse_document(file_bytes: bytes, file_type: str, file_name: str = "") -> str:
    """Parse document bytes into plain text.

    Supports: pdf, docx, md, txt, qa (plain text pass-through).
    """
    file_type = file_type.lower().strip(".")

    if file_type == "pdf":
        return _parse_pdf(file_bytes)
    elif file_type in ("docx", "doc"):
        return _parse_docx(file_bytes)
    elif file_type in ("md", "markdown", "txt", "text", "qa"):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        log.warning(f"Unsupported file type: {file_type}, treating as plain text")
        return file_bytes.decode("utf-8", errors="replace")


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Split text into overlapping chunks.

    Strategy: split by paragraphs first, then merge into chunks up to chunk_size.
    """
    if not text or not text.strip():
        return []

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    current = ""
    idx = 0

    for para in paragraphs:
        if len(current) + len(para) + 1 > chunk_size and current:
            chunks.append(Chunk(index=idx, content=current.strip()))
            idx += 1
            # Keep overlap from end of current chunk
            if chunk_overlap > 0 and len(current) > chunk_overlap:
                current = current[-chunk_overlap:] + "\n" + para
            else:
                current = para
        else:
            current = current + "\n" + para if current else para

    if current.strip():
        chunks.append(Chunk(index=idx, content=current.strip()))

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by double newlines or markdown headings."""
    parts = re.split(r"\n{2,}", text)
    result = []
    for part in parts:
        part = part.strip()
        if part:
            result.append(part)
    return result


def _parse_pdf(file_bytes: bytes) -> str:
    """Parse PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf is required for PDF parsing: pip install pypdf")

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(page_text)
    return "\n\n".join(pages)


def _parse_docx(file_bytes: bytes) -> str:
    """Parse DOCX using python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required for DOCX parsing: pip install python-docx")

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)
