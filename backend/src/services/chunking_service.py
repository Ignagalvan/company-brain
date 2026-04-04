import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document_chunk import DocumentChunk

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

_HEADING_MAX_CHARS = 60
_SENTENCE_ENDINGS = frozenset(".!?…")
_LIST_STARTERS = frozenset("-*•·–—")


def _is_heading(text: str) -> bool:
    """Return True if the paragraph looks like a section heading.

    Heuristics (no LLM):
    - Short: at most _HEADING_MAX_CHARS characters
    - Does not end with sentence-ending punctuation
    - Is not a list item (no leading dash/bullet)
    """
    t = text.strip()
    if not t or len(t) > _HEADING_MAX_CHARS:
        return False
    if t[-1] in _SENTENCE_ENDINGS:
        return False
    if t[0] in _LIST_STARTERS:
        return False
    return True


def _split_paragraph(paragraph: str, chunk_size: int, overlap: int) -> list[str]:
    """Split a long paragraph by sentences, keeping chunks under chunk_size with overlap."""
    # Split on sentence boundaries: ". ", "? ", "! "
    import re
    sentences = re.split(r'(?<=[.!?])\s+', paragraph)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = (current + " " + sentence).strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # sentence itself exceeds chunk_size → hard-split it
            if len(sentence) > chunk_size:
                start = 0
                while start < len(sentence):
                    chunks.append(sentence[start : start + chunk_size])
                    start += chunk_size - overlap
                current = ""
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    raw_chunks: list[str] = []

    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            raw_chunks.append(paragraph)
        else:
            raw_chunks.extend(_split_paragraph(paragraph, chunk_size, overlap))

    # Apply overlap by appending the tail of the previous chunk to the next one
    if overlap <= 0 or len(raw_chunks) <= 1:
        return raw_chunks

    result: list[str] = [raw_chunks[0]]
    for chunk in raw_chunks[1:]:
        prev_tail = result[-1][-overlap:]
        result.append((prev_tail + " " + chunk).strip())
    return result


def chunk_text_with_sections(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """Like chunk_text but each item carries the nearest preceding section heading.

    Returns a list of dicts: {"content": str, "section": str | None}
    Heading paragraphs are consumed as metadata and not emitted as standalone chunks.
    """
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Tag each content paragraph with the last heading seen before it
    tagged: list[tuple[str, str | None]] = []
    current_section: str | None = None
    for para in paragraphs:
        if _is_heading(para):
            current_section = para
        else:
            tagged.append((para, current_section))

    # Split long paragraphs, preserving their section tag
    raw_chunks: list[dict] = []
    for para, section in tagged:
        if len(para) <= chunk_size:
            raw_chunks.append({"content": para, "section": section})
        else:
            for sub in _split_paragraph(para, chunk_size, overlap):
                raw_chunks.append({"content": sub, "section": section})

    if not raw_chunks:
        return []

    # Apply overlap between consecutive chunks
    if overlap <= 0 or len(raw_chunks) <= 1:
        return raw_chunks

    result: list[dict] = [raw_chunks[0]]
    for item in raw_chunks[1:]:
        prev_tail = result[-1]["content"][-overlap:]
        result.append({
            "content": (prev_tail + " " + item["content"]).strip(),
            "section": item["section"],
        })
    return result


async def create_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
    text: str,
) -> list[DocumentChunk]:
    items = chunk_text_with_sections(text)

    chunks: list[DocumentChunk] = []
    for i, item in enumerate(items):
        section = item["section"]
        # Prepend the section heading so the embedding captures its context
        enriched = f"[{section}]\n{item['content']}" if section else item["content"]
        chunks.append(
            DocumentChunk(
                document_id=document_id,
                organization_id=organization_id,
                content=enriched,
                chunk_index=i,
            )
        )

    db.add_all(chunks)
    return chunks
