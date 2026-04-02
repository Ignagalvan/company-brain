import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(file_path: Path) -> str | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages_text).strip()
        return text if text else None
    except Exception as exc:
        logger.warning("PDF text extraction failed for '%s': %s", file_path.name, exc)
        return None
