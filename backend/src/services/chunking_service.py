import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document_chunk import DocumentChunk

CHUNK_SIZE = 1500     # raised from 1000 — allows complete ideas per section
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 200  # chunks below this are merged with adjacent content

_HEADING_MAX_CHARS = 60
_SENTENCE_ENDINGS = frozenset(".!?…")
_LIST_STARTERS = frozenset("-*•·–—")


def _is_heading(text: str) -> bool:
    """Return True if the line looks like a section heading.

    Heuristics (no LLM):
    - Short: at most _HEADING_MAX_CHARS characters
    - Does not end with sentence-ending punctuation
    - Is not a list item (no leading dash/bullet)
    - "Key: Value" lines are content, not headings
    - Numbered items (1. text, 2) text) are content, not headings
    """
    t = text.strip()
    if not t or len(t) > _HEADING_MAX_CHARS:
        return False
    if t[-1] in _SENTENCE_ENDINGS:
        return False
    if t[0] in _LIST_STARTERS:
        return False
    # "Key: Value" — colon with content after it → content line, not heading
    colon_pos = t.find(':')
    if 0 < colon_pos < len(t) - 1:
        return False
    # Numbered list items
    if re.match(r'^\d+[.)]\s', t):
        return False
    return True


def _last_sentence(text: str) -> str:
    """Return the last complete sentence from text, for semantic overlap.
    Returns empty string if the text is a single sentence (no split possible).
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return sentences[-1] if len(sentences) > 1 else ""


def _split_paragraph(paragraph: str, chunk_size: int, overlap: int) -> list[str]:
    """Split a long paragraph by sentences, keeping chunks under chunk_size with overlap."""
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
            if len(sentence) > chunk_size:
                start = 0
                while start < len(sentence):
                    chunks.append(sentence[start: start + chunk_size])
                    start += chunk_size - overlap
                current = ""
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks


def _split_section_paragraphs(
    paragraphs: list[str],
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """
    Build chunks within a single section, keeping adjacent paragraphs and lists
    together whenever they fit. Overlap is applied later, section-locally.
    """
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        candidate = f"{current}\n{para}".strip() if current else para
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(para) <= chunk_size:
            current = para
            continue

        chunks.extend(_split_paragraph(para, chunk_size, overlap))

    if current:
        chunks.append(current)

    return chunks


def _apply_section_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result: list[str] = [chunks[0]]
    for chunk in chunks[1:]:
        tail = _last_sentence(result[-1])
        prefix = tail if tail else result[-1][-overlap:]
        result.append((prefix + " " + chunk).strip())
    return result


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
    """Hierarchical chunking: section → paragraph → sentence.

    Handles both \\n\\n and \\n-separated documents (common in PDF extraction).
    Short lines without sentence punctuation are treated as section headings
    and consumed as metadata — not emitted as standalone chunks.

    Returns list of {"content": str, "section": str | None}.
    """
    if not text:
        return []

    # 1. Normalize whitespace
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()

    # 2. Scan lines → group into (heading, paragraphs) sections
    #    Works for both \n and \n\n separated documents.
    lines = text.split('\n')
    sections: list[tuple[str | None, list[str]]] = []
    cur_heading: str | None = None
    cur_para: list[str] = []
    cur_paras: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            # blank line → paragraph break within section
            if cur_para:
                cur_paras.append(' '.join(cur_para))
                cur_para = []
        elif _is_heading(line):
            # flush current paragraph and section, start new section
            if cur_para:
                cur_paras.append(' '.join(cur_para))
                cur_para = []
            if cur_paras:
                sections.append((cur_heading, cur_paras))
                cur_paras = []
            cur_heading = line
        else:
            cur_para.append(line)

    # flush trailing content
    if cur_para:
        cur_paras.append(' '.join(cur_para))
    if cur_paras:
        sections.append((cur_heading, cur_paras))

    # 3. Build chunks section-by-section so each chunk stays semantically
    # self-contained. We never merge across section boundaries.
    result: list[dict] = []

    for heading, paragraphs in sections:
        cleaned_paragraphs = [p.strip() for p in paragraphs if p.strip()]
        if not cleaned_paragraphs:
            continue

        section_chunks = _split_section_paragraphs(cleaned_paragraphs, chunk_size, overlap)

        # Avoid tiny trailing chunks inside the same section when they can fit
        # into the previous section chunk without breaking size limits.
        if (
            len(section_chunks) >= 2
            and len(section_chunks[-1]) < MIN_CHUNK_SIZE
            and len(section_chunks[-2]) + len(section_chunks[-1]) + 1 <= chunk_size
        ):
            section_chunks[-2] = section_chunks[-2] + "\n" + section_chunks[-1]
            section_chunks.pop()

        for content in _apply_section_overlap(section_chunks, overlap):
            result.append({"content": content, "section": heading})

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
        # Prepend section heading so the embedding captures its context
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
