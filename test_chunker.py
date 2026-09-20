#!/usr/bin/env python3
"""
Unit tests for the Milestone 3 chunker.

    python -m unittest test_chunker -v

`test.py` checks the environment; this checks the one piece of the pipeline I
actually wrote. It runs offline: no embedding, no vector store, no API calls.

The last class runs against the real corpus, so a change to chunker.py that
quietly breaks the claims in my README fails here rather than three milestones
later.
"""

import re
import unittest

import chunker
import config
from chunker import Chunk, section_split
from ingest import Document, load_documents


def doc(text: str, source: str = "guide_test.md") -> Document:
    return Document(source=source, text=text.strip())


def bodies(chunks: list[Chunk]) -> list[str]:
    """Chunk text with the breadcrumb line removed."""
    return [c.text.split("\n\n", 1)[1] if "\n\n" in c.text else "" for c in chunks]


def breadcrumbs(chunks: list[Chunk]) -> list[str]:
    return [c.text.split("\n", 1)[0] for c in chunks]


class SectionBoundaries(unittest.TestCase):
    """One chunk per section, which is the whole point of the strategy."""

    SIMPLE = """
# Brightwater

A harbour town with a working fish market.

## Getting there

Trains from the city every half hour, journey time 40 minutes.

## Where to stay

Two hotels on the quay and a campsite behind the dunes.
"""

    def test_one_chunk_per_section_plus_preamble(self):
        chunks = section_split([doc(self.SIMPLE)], chunk_size=600, overlap=100)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(
            breadcrumbs(chunks),
            [
                "Brightwater: Overview",
                "Brightwater: Getting there",
                "Brightwater: Where to stay",
            ],
        )

    def test_section_text_is_not_mixed_between_chunks(self):
        chunks = section_split([doc(self.SIMPLE)], chunk_size=600, overlap=100)
        getting_there = bodies(chunks)[1]
        self.assertIn("every half hour", getting_there)
        self.assertNotIn("campsite", getting_there)
        self.assertNotIn("fish market", getting_there)

    def test_adjacent_sections_do_not_overlap(self):
        # Overlap exists to rescue a fact split across a cut. Two sections were
        # never one fact, so carrying text across them only mislabels it.
        chunks = section_split([doc(self.SIMPLE)], chunk_size=600, overlap=100)
        self.assertNotIn("Trains from the city", bodies(chunks)[2])

    def test_indices_start_at_zero_and_are_contiguous(self):
        chunks = section_split([doc(self.SIMPLE)], chunk_size=600, overlap=100)
        self.assertEqual([c.index for c in chunks], [0, 1, 2])
        self.assertEqual([c.label for c in chunks][0], "guide_test.md#0")

    def test_produced_by_matches_what_the_readme_claims(self):
        chunks = section_split([doc(self.SIMPLE)], chunk_size=600, overlap=100)
        self.assertTrue(all(c.produced_by == "chunker.py::section_split" for c in chunks))

    def test_deeper_headings_are_boundaries_too(self):
        text = "# T\n\n## A\n\nalpha text\n\n### B\n\nbravo text\n"
        chunks = section_split([doc(text)], chunk_size=600, overlap=100)
        self.assertEqual(breadcrumbs(chunks), ["T: A", "T: B"])

    def test_heading_with_no_body_is_dropped(self):
        text = "# T\n\n## Empty\n\n## Real\n\nsomething here\n"
        chunks = section_split([doc(text)], chunk_size=600, overlap=100)
        self.assertEqual(breadcrumbs(chunks), ["T: Real"])


class Breadcrumbs(unittest.TestCase):
    """
    The breadcrumb is the fix for the two problems I measured in the corpus:
    section bodies never name their own town, and "Practical notes" is
    identical in 9 of 14 files.
    """

    def test_every_chunk_starts_with_title_and_heading(self):
        chunks = section_split([doc("# Halden Bay\n\n## Eat and drink\n\nchips.")],
                               chunk_size=600, overlap=100)
        self.assertTrue(chunks[0].text.startswith("Halden Bay: Eat and drink\n\n"))

    def test_identical_sections_in_different_files_become_different_chunks(self):
        shared = "## Practical notes\n\nCash is still useful at the market."
        a = doc(f"# Kestrelford\n\n{shared}", source="guide_kestrelford.md")
        b = doc(f"# Marchwood\n\n{shared}", source="guide_marchwood.md")
        chunks = section_split([a, b], chunk_size=600, overlap=100)
        self.assertNotEqual(chunks[0].text, chunks[1].text)
        self.assertIn("Kestrelford", chunks[0].text)
        self.assertIn("Marchwood", chunks[1].text)

    def test_title_falls_back_to_the_filename(self):
        chunks = section_split([doc("## Getting there\n\nBus.", source="guide_elder_ness.md")],
                               chunk_size=600, overlap=100)
        self.assertEqual(breadcrumbs(chunks), ["elder ness: Getting there"])

    def test_a_hash_line_further_down_is_content_not_a_title(self):
        text = "Intro line.\n\n# Not a title\n\nmore text"
        chunks = section_split([doc(text, source="notes.txt")], chunk_size=600, overlap=100)
        self.assertEqual(breadcrumbs(chunks), ["notes: Overview"])
        self.assertIn("Not a title", chunks[0].text)


class SizeCap(unittest.TestCase):
    """What happens to the sections that are too long to leave alone."""

    def long_section(self, paragraphs: int = 6, sentence: str = None) -> str:
        sentence = sentence or "Kestrelford has a bus and a very long single track road. "
        body = "\n\n".join(f"Paragraph {i}. {sentence * 2}".strip() for i in range(paragraphs))
        return f"# Town\n\n## Long\n\n{body}\n"

    def test_long_section_is_split(self):
        chunks = section_split([doc(self.long_section())], chunk_size=300, overlap=60)
        self.assertGreater(len(chunks), 1)

    def test_no_chunk_exceeds_the_cap(self):
        chunks = section_split([doc(self.long_section())], chunk_size=300, overlap=60)
        for c in chunks:
            self.assertLessEqual(len(c.text), 300, msg=f"{len(c.text)} chars: {c.text[:60]!r}")

    def test_every_piece_keeps_the_breadcrumb(self):
        chunks = section_split([doc(self.long_section())], chunk_size=300, overlap=60)
        self.assertTrue(all(b == "Town: Long" for b in breadcrumbs(chunks)))

    def test_split_pieces_carry_overlap(self):
        # Sentence-level overlap: the tail of one piece opens the next.
        text = "# T\n\n## S\n\n" + " ".join(f"Sentence number {i} about buses." for i in range(20))
        chunks = section_split([doc(text)], chunk_size=260, overlap=80)
        self.assertGreater(len(chunks), 2)
        for first, second in zip(chunks, chunks[1:]):
            tail = bodies([first])[0].split(". ")[-1].strip(" .")
            self.assertIn(tail, bodies([second])[0],
                          msg="a piece did not carry its predecessor's last sentence")

    def test_a_sentence_longer_than_the_cap_is_kept_whole(self):
        # Cutting mid-word destroys the fact; an over-long chunk only costs
        # context budget. Prefer the over-long chunk, but prove it is deliberate.
        giant = "The bus " + "runs and " * 80 + "stops."
        chunks = section_split([doc(f"# T\n\n## S\n\n{giant}")], chunk_size=200, overlap=50)
        self.assertEqual(len(chunks), 1)
        self.assertIn(giant, chunks[0].text)
        self.assertFalse(chunks[0].text.endswith("ru"))

    def test_paragraphs_are_packed_not_emitted_one_by_one(self):
        # Three 40-character paragraphs under a 600 cap belong in one chunk.
        text = "# T\n\n## S\n\n" + "\n\n".join(["Short line about the ferry." ] * 3)
        chunks = section_split([doc(text)], chunk_size=600, overlap=100)
        self.assertEqual(len(chunks), 1)


class Validation(unittest.TestCase):
    def test_overlap_must_be_smaller_than_chunk_size(self):
        with self.assertRaises(ValueError):
            section_split([doc("# T\n\n## S\n\nx")], chunk_size=100, overlap=100)

    def test_negative_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            section_split([doc("# T\n\n## S\n\nx")], chunk_size=100, overlap=-1)

    def test_empty_input_is_not_an_error(self):
        self.assertEqual(section_split([], chunk_size=600, overlap=100), [])

    def test_title_only_document_produces_nothing(self):
        self.assertEqual(section_split([doc("# Just a title\n")], chunk_size=600, overlap=100), [])

    def test_document_with_no_headings_still_chunks(self):
        text = "Plain text with no markdown at all. " * 5
        chunks = section_split([doc(text, source="plain.txt")], chunk_size=600, overlap=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(breadcrumbs(chunks), ["plain: Overview"])

    def test_zero_overlap_is_allowed(self):
        chunks = section_split([doc("# T\n\n## S\n\nbody text")], chunk_size=600, overlap=0)
        self.assertEqual(len(chunks), 1)


class RealCorpus(unittest.TestCase):
    """
    The claims my README makes, checked against the documents themselves.

    These use the configured corpus, so they also catch "I switched corpus and
    forgot that the numbers in the README were measured on the old one".
    """

    @classmethod
    def setUpClass(cls):
        cls.documents = load_documents()
        cls.chunks = chunker.split_documents(cls.documents)

    def test_corpus_is_the_one_the_readme_describes(self):
        self.assertEqual(config.CORPUS, "city_guides")
        self.assertEqual(len(self.documents), 14)

    def test_no_chunk_is_over_the_configured_cap(self):
        longest = max(self.chunks, key=lambda c: len(c.text))
        self.assertLessEqual(len(longest.text), config.CHUNK_SIZE,
                             msg=f"{longest.label} is {len(longest.text)} characters")

    def test_no_chunk_is_a_scrap(self):
        # The starter's chunker left a 24-character tail on this corpus and a
        # 2-character one on advice_threads. Criterion 4 says mine has none.
        shortest = min(self.chunks, key=lambda c: len(c.text))
        self.assertGreaterEqual(len(shortest.text), 150,
                                msg=f"{shortest.label}: {shortest.text!r}")

    def test_every_document_is_represented(self):
        sources = {c.source for c in self.chunks}
        self.assertEqual(sources, {d.source for d in self.documents})

    def test_every_chunk_is_unique(self):
        texts = [c.text for c in self.chunks]
        self.assertEqual(len(texts), len(set(texts)),
                         msg="duplicate chunks — the breadcrumb is not doing its job")

    def test_no_chunk_starts_mid_sentence(self):
        # A chunk that opens with a lowercase word is the tail of something
        # else. Overlap makes a few legitimate exceptions, so allow the ones
        # that begin with the carried sentence of the piece before them.
        offenders = []
        for c in self.chunks:
            body = bodies([c])[0].lstrip()
            if body and body[0].islower():
                offenders.append(c.label)
        self.assertEqual(offenders, [], msg=f"chunks starting mid-sentence: {offenders}")

    def test_content_survives_chunking(self):
        # Every sentence of every document has to end up in at least one chunk.
        # This is the test that would have caught a regex that ate a section.
        blob = re.sub(r"\s+", " ", " ".join(c.text for c in self.chunks))
        missing = []
        for document in self.documents:
            for line in document.text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if re.sub(r"\s+", " ", line) not in blob:
                    missing.append((document.source, line[:60]))
        self.assertEqual(missing[:5], [], msg=f"{len(missing)} lines lost in chunking")

    def test_the_numbers_in_the_readme_are_still_true(self):
        # Not a quality claim on its own — these are the measurements the
        # README reports, pinned so the write-up cannot drift from the code.
        starter = chunker.fallback_split(self.documents, chunk_size=800, overlap=120)
        self.assertEqual(len(starter), 51)          # baseline, Milestone 1
        self.assertEqual(len(self.chunks), 97)      # 84 sections + 10 overviews + 3 splits
        lengths = [len(c.text) for c in self.chunks]
        self.assertEqual((min(lengths), max(lengths)), (152, 565))
        self.assertEqual(sum(lengths) // len(lengths), 310)

    def test_only_the_long_multi_place_sections_get_split(self):
        # Splitting is supposed to be rare and targeted: the three sections
        # that list several towns one after another.
        counts = {}
        for c in self.chunks:
            head = c.text.split("\n", 1)[0]
            counts[head] = counts.get(head, 0) + 1
        split = sorted(h for h, n in counts.items() if n > 1)
        self.assertEqual(split, [
            "Eating across the region: The pattern worth knowing",
            "Getting around the region with limited mobility: Straightforward",
            "Walking in the region: Easy, on good surfaces",
        ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
