from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
import re

from docx import Document
from pypdf import PdfReader


ALLOWED_DOCUMENTS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
SUFFIX_MIME = {suffix: mime for mime, suffix in ALLOWED_DOCUMENTS.items()}
SAFE_FILENAME = re.compile(r"^[\w.\- ()]+$", re.UNICODE)


class DocumentParser(ABC):
    @abstractmethod
    def extract_text(self, content: bytes) -> str:
        raise NotImplementedError


class PDFDocumentParser(DocumentParser):
    def extract_text(self, content: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:  # noqa: BLE001 - surface as validation error
            raise ValueError("Unable to read PDF. The file may be corrupted.") from exc
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not text.strip():
            raise ValueError("PDF contains no extractable text")
        return text


class DOCXDocumentParser(DocumentParser):
    def extract_text(self, content: bytes) -> str:
        try:
            document = Document(BytesIO(content))
        except Exception as exc:  # noqa: BLE001 - surface as validation error
            raise ValueError("Unable to read DOCX. The file may be corrupted.") from exc
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        if not text.strip():
            raise ValueError("DOCX contains no extractable text")
        return text


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "").name.strip()
    if not name or len(name) > 255 or ".." in name:
        raise ValueError("Invalid filename")
    if not SAFE_FILENAME.match(name):
        raise ValueError("Filename contains unsupported characters")
    return name


def parser_for(filename: str, mime_type: str) -> DocumentParser:
    safe_name = sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    normalized_mime = mime_type.split(";")[0].strip().lower()
    if normalized_mime in {"", "application/octet-stream", "binary/octet-stream"}:
        normalized_mime = SUFFIX_MIME.get(suffix, "")
    expected_suffix = ALLOWED_DOCUMENTS.get(normalized_mime)
    if expected_suffix is None or suffix != expected_suffix:
        raise ValueError(
            "Unable to process this resume. Please verify that the uploaded file is a valid PDF or DOCX."
        )
    if suffix == ".pdf" and not safe_name.lower().endswith(".pdf"):
        raise ValueError("Invalid PDF filename")
    return PDFDocumentParser() if suffix == ".pdf" else DOCXDocumentParser()
