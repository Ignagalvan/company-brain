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

    # 3. Build raw chunks from sections
    raw_chunks: list[dict] = []

    for heading, paragraphs in sections:
        for para in paragraphs:
            if not para.strip():
                continue

            # Merge short paragraphs with the previous chunk in the same section
            # to avoid near-empty, low-information chunks
            if (
                len(para) < MIN_CHUNK_SIZE
                and raw_chunks
                and raw_chunks[-1]['section'] == heading
            ):
                merged = raw_chunks[-1]['content'] + '\n' + para
                if len(merged) <= chunk_size:
                    raw_chunks[-1]['content'] = merged
                    continue

            if len(para) <= chunk_size:
                raw_chunks.append({'content': para, 'section': heading})
            else:
                for sub in _split_paragraph(para, chunk_size, overlap):
                    raw_chunks.append({'content': sub, 'section': heading})

    if not raw_chunks:
        return []

    # 3.5 Consolidate adjacent short chunks across sections.
    # Many structured documents (templates, policies) produce multiple sections
    # that are each small (< half chunk_size). Keeping them separate means the
    # judge sees many tiny fragments that individually feel incomplete, causing
    # "partial" coverage even when the topic is fully covered in aggregate.
    # Strategy: merge two consecutive chunks when BOTH are below the half-size
    # threshold and the combined result stays within chunk_size.
    _HALF_SIZE = chunk_size // 2  # 750 chars at default settings

    consolidated: list[dict] = []
    for item in raw_chunks:
        prev = consolidated[-1] if consolidated else None
        if (
            prev is not None
            and len(prev['content']) < _HALF_SIZE
            and len(item['content']) < _HALF_SIZE
            and len(prev['content']) + len(item['content']) + 2 <= chunk_size
        ):
            # Merge: newline separator, keep section from first chunk
            prev['content'] = prev['content'] + '\n' + item['content']
        else:
            consolidated.append({'content': item['content'], 'section': item['section']})

    raw_chunks = consolidated

    # 4. Apply semantic overlap: last sentence of previous chunk
    if overlap <= 0 or len(raw_chunks) <= 1:
        return raw_chunks

    result: list[dict] = [raw_chunks[0]]
    for item in raw_chunks[1:]:
        tail = _last_sentence(result[-1]['content'])
        prefix = tail if tail else result[-1]['content'][-overlap:]
        result.append({
            'content': (prefix + ' ' + item['content']).strip(),
            'section': item['section'],
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
