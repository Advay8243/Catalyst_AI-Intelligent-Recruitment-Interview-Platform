from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


ALLOWED_DOCUMENTS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
SUFFIX_MIME = {suffix: mime for mime, suffix in ALLOWED_DOCUMENTS.items()}


class DocumentParser(ABC):
    @abstractmethod
    def extract_text(self, content: bytes) -> str:
        raise NotImplementedError


class PDFDocumentParser(DocumentParser):
    def extract_text(self, content: bytes) -> str:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
        if not text.strip():
            raise ValueError("PDF contains no extractable text")
        return text


class DOCXDocumentParser(DocumentParser):
    def extract_text(self, content: bytes) -> str:
        text = "\n".join(paragraph.text for paragraph in Document(BytesIO(content)).paragraphs)
        if not text.strip():
            raise ValueError("DOCX contains no extractable text")
        return text


def parser_for(filename: str, mime_type: str) -> DocumentParser:
    suffix = Path(filename).suffix.lower()
    normalized_mime = mime_type.split(";")[0].strip().lower()
    if normalized_mime in {"", "application/octet-stream", "binary/octet-stream"}:
        normalized_mime = SUFFIX_MIME.get(suffix, "")
    expected_suffix = ALLOWED_DOCUMENTS.get(normalized_mime)
    if expected_suffix is None or suffix != expected_suffix:
        raise ValueError(
            "Unable to process this resume. Please verify that the uploaded file is a valid PDF or DOCX."
        )
    return PDFDocumentParser() if suffix == ".pdf" else DOCXDocumentParser()
