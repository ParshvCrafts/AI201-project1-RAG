"""
Stage 2 of the pipeline: splitting documents into chunks.

Milestone 3 replaced the body of `split_documents`. The starter cut every
document into fixed 800-character windows; on `city_guides` that produced 51
chunks that sliced straight through the labelled sections the guides are
written in. `section_split` below cuts on those labels instead.

Three things about this corpus drove the design, all of them measured before
any code was written (see README.md, "Chunking Strategy"):

  1. Every document is Markdown with one `# Title` line and a handful of
     `## Section` headings. There are 84 sections across the 14 files, averaging
     311 characters, the longest 708 and the shortest 173. A section is already
     almost exactly the size a chunk wants to be, so the section boundary is the
     chunk boundary.
  2. A section body almost never repeats the name of the town it belongs to.
     "Getting there" under `# Kestrelford` says "the bus from Brightwater" and
     never the word Kestrelford. Embedding that text on its own loses the one
     term the question will be phrased with, so every chunk carries a
     `Title: Heading` breadcrumb line.
  3. The "Practical notes" section is byte-for-byte identical in 9 of the 14
     files. Without the breadcrumb those are 9 indistinguishable vectors, and
     whichever one comes back first decides which town gets cited. The
     breadcrumb is what makes the citation correct rather than merely present.

`fallback_split` is kept as the starter left it, so unit 2 can index both
strategies side by side with `--variant` and compare them.
"""

import re
from dataclasses import dataclass

import config
from ingest import Document

# A line like "# Brightwater" — the document title.
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# A line like "## Getting there" — a section heading. Two or more hashes, so a
# deeper "### " heading is treated as a section boundary too rather than being
# swallowed into the text above it.
HEADING_RE = re.compile(r"^#{2,6}\s+(.+?)\s*$", re.MULTILINE)

# Sentence end: . ! or ? followed by whitespace. Good enough for prose; it is
# only used to choose where to cut an oversized paragraph, so a false positive
# costs a slightly odd boundary, not a lost fact.
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")

# What a chunk with no heading above it is called.
PREAMBLE_HEADING = "Overview"


@dataclass
class Chunk:
    """One piece of one document."""

    text: str
    source: str        # which file it came from
    index: int         # which chunk within that file, starting at 0
    produced_by: str   # the function that made it — cite this in your README

    @property
    def label(self) -> str:
        return f"{self.source}#{self.index}"


def fallback_split(
    documents: list[Document],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    The starter's original chunker. Fixed-size character windows with overlap.

    Keep this function. Milestone 3's stop rule points back at it, and having
    something to compare your own strategy against is useful in unit 2.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    overlap = overlap or config.CHUNK_OVERLAP

    if overlap >= chunk_size:
        raise ValueError("overlap has to be smaller than chunk_size")

    chunks: list[Chunk] = []
    for doc in documents:
        start = 0
        index = 0
        while start < len(doc.text):
            piece = doc.text[start : start + chunk_size].strip()
            if piece:
                chunks.append(
                    Chunk(
                        text=piece,
                        source=doc.source,
                        index=index,
                        produced_by="chunker.py::fallback_split",
                    )
                )
                index += 1
            start += chunk_size - overlap

    return chunks


# ─── The pieces section_split is built out of ────────────────────────────────


def _title_match(text: str):
    """
    The document's title line, but only if it is the first thing in the file.

    A `# ` line further down is content, not a title. `_document_title` and
    `_sections` both go through here so they can never disagree about which
    line the title is.
    """
    match = TITLE_RE.search(text)
    if match and not text[: match.start()].strip():
        return match
    return None


def _document_title(text: str, source: str) -> str:
    """
    The document's `# Title`, or a readable name made from the filename.

    The filename fallback matters: a document with no title line still needs a
    breadcrumb, or its chunks go into the index with nothing that names their
    subject.
    """
    match = _title_match(text)
    if match:
        return match.group(1).strip()

    stem = source.rsplit(".", 1)[0]
    stem = re.sub(r"^guide[_-]", "", stem)
    return stem.replace("_", " ").replace("-", " ").strip() or source


def _sections(text: str) -> list[tuple[str, str]]:
    """
    Split a document into (heading, body) pairs on its `##` lines.

    Anything above the first heading, minus the title line, comes back as the
    `Overview` section — in this corpus that is the one-sentence summary that
    opens every town guide, and it is the best single answer to "what is X
    like", so it must not be dropped.

    A document with no headings at all comes back as one Overview section, and
    the size cap in `_pack` takes it from there.
    """
    # Drop the title line, but only when it really is the first thing in the
    # document. A stray "# " further down is content, not a title.
    title = _title_match(text)
    body = text[title.end() :] if title else text

    matches = list(HEADING_RE.finditer(body))

    sections: list[tuple[str, str]] = []
    preamble = body[: matches[0].start()] if matches else body
    if preamble.strip():
        sections.append((PREAMBLE_HEADING, preamble.strip()))

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_body = body[match.end() : end].strip()
        if section_body:                      # a heading with nothing under it
            sections.append((match.group(1).strip(), section_body))

    return sections


def _split_paragraph(paragraph: str, budget: int, overlap: int) -> list[str]:
    """
    Cut one over-long paragraph at sentence boundaries, carrying `overlap`
    characters of the previous piece into the next so a fact that straddles the
    cut survives in one of them.

    A single sentence longer than the budget is emitted whole rather than cut
    mid-word. An over-long chunk is a worse outcome than a truncated one only
    if you never read it; a sentence chopped in half is wrong in a way no
    retrieval setting recovers from.
    """
    sentences = [s for s in SENTENCE_END_RE.split(paragraph) if s.strip()]
    pieces: list[str] = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(candidate) > budget:
            pieces.append(current)
            tail = current[-overlap:] if overlap else ""
            # Start the carried text at a sentence boundary where we can.
            if tail:
                parts = SENTENCE_END_RE.split(tail)
                tail = parts[-1] if len(parts) > 1 else tail
            current = f"{tail} {sentence}".strip() if tail else sentence
        else:
            current = candidate

    if current:
        pieces.append(current)

    return pieces or [paragraph]


def _pack(body: str, budget: int, overlap: int) -> list[str]:
    """
    Fit a section body into pieces of at most `budget` characters, preferring
    to break between paragraphs and falling back to sentences.

    Paragraphs are packed greedily rather than one-per-chunk because the long
    sections in this corpus are lists of two-line entries — one town each in
    `guide_accessibility.md` — and a two-line chunk on its own has lost the
    question it was answering.
    """
    if budget <= 0:
        raise ValueError("budget has to be positive")

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
    if not paragraphs:
        return []

    pieces: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > budget:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_paragraph(paragraph, budget, overlap))
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if current and len(candidate) > budget:
            pieces.append(current)
            current = paragraph
        else:
            current = candidate

    if current:
        pieces.append(current)

    return pieces


def section_split(
    documents: list[Document],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    Cut each document on its Markdown section headings, then cap the size.

    One chunk per `## Section`, prefixed with a `Title: Heading` breadcrumb.
    Sections over `chunk_size` are packed into several pieces at paragraph or
    sentence boundaries, and only those pieces overlap — two different sections
    are two different subjects, so carrying text between them would put the
    wrong town's opening hours at the end of another town's chunk.
    """
    chunk_size = config.CHUNK_SIZE if chunk_size is None else chunk_size
    overlap = config.CHUNK_OVERLAP if overlap is None else overlap

    if overlap >= chunk_size:
        raise ValueError("overlap has to be smaller than chunk_size")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    chunks: list[Chunk] = []

    for doc in documents:
        title = _document_title(doc.text, doc.source)
        index = 0

        for heading, body in _sections(doc.text):
            breadcrumb = f"{title}: {heading}"
            # The breadcrumb is part of the chunk, so it comes out of the budget.
            budget = max(chunk_size - len(breadcrumb) - 2, 80)

            for piece in _pack(body, budget, overlap):
                chunks.append(
                    Chunk(
                        text=f"{breadcrumb}\n\n{piece}",
                        source=doc.source,
                        index=index,
                        produced_by="chunker.py::section_split",
                    )
                )
                index += 1

    return chunks


def split_documents(documents: list[Document]) -> list[Chunk]:
    """
    Split documents into chunks. This is what the rest of the pipeline calls.

    It delegates to `section_split`. The two are kept separate so the strategy
    can be unit-tested with explicit sizes without reaching into config.
    """
    return section_split(documents)


def describe(chunks: list[Chunk]) -> str:
    """A one-line summary, printed after indexing."""
    if not chunks:
        return "0 chunks"
    lengths = [len(c.text) for c in chunks]
    return (
        f"{len(chunks)} chunks, "
        f"{sum(lengths) // len(lengths)} characters on average "
        f"(shortest {min(lengths)}, longest {max(lengths)}), "
        f"produced by {chunks[0].produced_by}"
    )


if __name__ == "__main__":
    from ingest import load_documents

    chunks = split_documents(load_documents())
    print(describe(chunks))
