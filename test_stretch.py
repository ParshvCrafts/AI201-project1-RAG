#!/usr/bin/env python3
"""
Unit tests for the two stretch features: metadata filtering and conversational
memory.

    python -m unittest test_stretch -v

The conversation tests are pure functions and run anywhere. The filtering tests
that touch the vector store need an index, so they skip themselves with a clear
message rather than failing if you have not run `python app.py index` yet. No
API calls either way.
"""

import unittest

import config
import store
from chunker import Chunk, section_split
from conversation import Conversation, looks_like_follow_up
from generate import build_prompt
from ingest import Document


# ─── Stretch feature 1: metadata filtering ───────────────────────────────────


class Slugs(unittest.TestCase):
    def test_titles_become_command_line_friendly(self):
        self.assertEqual(store.slug("Elder Ness"), "elder_ness")
        self.assertEqual(store.slug("Getting there"), "getting_there")
        self.assertEqual(store.slug("Spring, March to May"), "spring_march_to_may")

    def test_empty_and_odd_values_do_not_explode(self):
        self.assertEqual(store.slug(""), "")
        self.assertEqual(store.slug("   "), "")
        self.assertEqual(store.slug("--Halden  Bay--"), "halden_bay")


class WhereClauses(unittest.TestCase):
    def test_no_filter_is_none_not_an_empty_dict(self):
        # Chroma treats {} as a filter that matches nothing, so this matters.
        self.assertIsNone(store.build_where())
        self.assertIsNone(store.build_where(None, None, None))

    def test_one_filter_is_a_bare_clause(self):
        self.assertEqual(store.build_where(place="Kestrelford"), {"place": "kestrelford"})

    def test_several_filters_are_anded(self):
        where = store.build_where(place="Elder Ness", section="Getting there")
        self.assertEqual(
            where,
            {"$and": [{"place": "elder_ness"}, {"section": "getting_there"}]},
        )

    def test_source_is_matched_exactly_not_slugged(self):
        # A filename is already exact. Slugging it would turn
        # guide_kestrelford.md into guide_kestrelford_md and match nothing.
        self.assertEqual(
            store.build_where(source="guide_kestrelford.md"),
            {"source": "guide_kestrelford.md"},
        )


class ChunkMetadata(unittest.TestCase):
    """The filters can only work if the chunker records where a chunk sits."""

    def test_section_split_records_title_and_heading(self):
        doc = Document(source="guide_x.md", text="# Halden Bay\n\n## Getting there\n\nBy road.")
        chunk = section_split([doc], chunk_size=600, overlap=100)[0]
        self.assertEqual(chunk.title, "Halden Bay")
        self.assertEqual(chunk.heading, "Getting there")

    def test_the_starter_chunker_still_constructs(self):
        # fallback_split does not know about sections, so title and heading
        # default to empty rather than becoming required arguments.
        chunk = Chunk(text="x", source="a.md", index=0, produced_by="f")
        self.assertEqual((chunk.title, chunk.heading), ("", ""))


class FilteredSearch(unittest.TestCase):
    """Against the real index, if there is one."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.available = store.facets()
        except RuntimeError as exc:
            raise unittest.SkipTest(f"no index to search: {exc}")

    def test_facets_list_the_towns(self):
        self.assertIn("kestrelford", self.available["place"])
        self.assertIn("practical_notes", self.available["section"])
        self.assertIn("guide_kestrelford.md", self.available["source"])

    def test_a_place_filter_only_returns_that_place(self):
        results = store.search("where do I eat", top_k=5, where=store.build_where(place="kestrelford"))
        self.assertTrue(results)
        self.assertEqual({r.source for r in results}, {"guide_kestrelford.md"})

    def test_filtering_fixes_the_nine_identical_sections(self):
        # Unfiltered, the nine byte-identical "Practical notes" chunks are
        # separated by thousandths of a distance and the winner is arbitrary.
        # This is the whole reason the feature exists.
        unfiltered = store.search("what are the practical notes", top_k=3)
        self.assertGreater(len({r.source for r in unfiltered}), 1)

        filtered = store.search(
            "what are the practical notes",
            top_k=3,
            where=store.build_where(place="marchwood"),
        )
        self.assertEqual(filtered[0].source, "guide_marchwood.md")

    def test_a_filter_that_matches_nothing_raises_rather_than_refusing(self):
        with self.assertRaises(store.NoMatchingChunks) as caught:
            store.search("where do I eat", where=store.build_where(place="atlantis"))
        # The message has to be useful enough to fix the typo from.
        self.assertIn("kestrelford", str(caught.exception))

    def test_two_filters_narrow_further_than_one(self):
        one = store.search("how do I arrive", top_k=8, where=store.build_where(place="kestrelford"))
        two = store.search(
            "how do I arrive",
            top_k=8,
            where=store.build_where(place="kestrelford", section="getting_there"),
        )
        self.assertEqual(len(two), 1)
        self.assertLess(len(two), len(one))


# ─── Stretch feature 2: conversational memory ────────────────────────────────


class FollowUpDetection(unittest.TestCase):
    def test_openers_are_follow_ups(self):
        for question in ["how about on Sundays?", "What about in winter?", "and the trams?"]:
            self.assertTrue(looks_like_follow_up(question)[0], question)

    def test_short_questions_with_a_referring_word_are_follow_ups(self):
        for question in ["is it open on Mondays?", "how long does that take?"]:
            self.assertTrue(looks_like_follow_up(question)[0], question)

    def test_a_full_question_is_not_a_follow_up(self):
        for question in [
            "How often do Marchwood's trams run on weekdays?",
            "How much does it cost to climb the church tower in Kestrelford?",
        ]:
            self.assertFalse(looks_like_follow_up(question)[0], question)

    def test_a_long_question_with_a_pronoun_is_left_alone(self):
        # Long questions carry enough subject of their own, and dragging the
        # previous one in can answer something nobody asked.
        question = (
            "Given that the ferry stops running in October, is it still "
            "possible to reach the island by road in the winter months?"
        )
        self.assertFalse(looks_like_follow_up(question)[0])

    def test_every_decision_comes_with_a_reason(self):
        for question in ["how about Sundays?", "How do the trams run on weekdays in Marchwood?"]:
            self.assertTrue(looks_like_follow_up(question)[1])


class Memory(unittest.TestCase):
    def setUp(self):
        self.memory = Conversation(max_turns=3)

    def test_the_first_question_is_never_a_follow_up(self):
        resolution = self.memory.resolve("how about on Sundays?")
        self.assertFalse(resolution.is_follow_up)
        self.assertEqual(resolution.retrieval_query, "how about on Sundays?")

    def test_a_follow_up_retrieves_on_both_questions(self):
        self.memory.add("How often do buses run to Kestrelford on Saturdays?", "Every two hours.")
        resolution = self.memory.resolve("how about on Sundays?")
        self.assertTrue(resolution.is_follow_up)
        self.assertIn("Kestrelford", resolution.retrieval_query)
        self.assertIn("Sundays", resolution.retrieval_query)

    def test_the_question_itself_is_never_rewritten(self):
        # The model must answer what was typed. Only retrieval sees the merge.
        self.memory.add("How often do buses run to Kestrelford?", "Hourly.")
        resolution = self.memory.resolve("how about on Sundays?")
        self.assertEqual(resolution.question, "how about on Sundays?")
        self.assertNotEqual(resolution.question, resolution.retrieval_query)

    def test_a_new_subject_drops_the_old_one(self):
        self.memory.add("How often do buses run to Kestrelford?", "Hourly.")
        resolution = self.memory.resolve("How often do Marchwood's trams run on weekdays?")
        self.assertFalse(resolution.is_follow_up)
        self.assertNotIn("Kestrelford", resolution.retrieval_query)

    def test_refusals_are_remembered_too(self):
        # Otherwise a follow-up after a refusal attaches to two subjects ago.
        self.memory.add("Who won the 1994 World Cup?", "I don't have enough information.", refused=True)
        resolution = self.memory.resolve("how about the 1998 one?")
        self.assertIn("1994", resolution.retrieval_query)

    def test_only_the_last_few_turns_are_kept(self):
        for i in range(5):
            self.memory.add(f"question {i}", f"answer {i}")
        self.assertEqual(len(self.memory.turns), 3)
        self.assertEqual(self.memory.turns[0].question, "question 2")

    def test_reset_forgets_everything(self):
        self.memory.add("a", "b")
        self.memory.reset()
        self.assertIsNone(self.memory.context_block())
        self.assertFalse(self.memory.resolve("how about Sundays?").is_follow_up)

    def test_memory_can_be_switched_off(self):
        off = Conversation(enabled=False)
        off.add("How often do buses run to Kestrelford?", "Hourly.")
        resolution = off.resolve("how about on Sundays?")
        self.assertFalse(resolution.is_follow_up)
        self.assertIsNone(off.context_block())

    def test_max_turns_must_be_sensible(self):
        with self.assertRaises(ValueError):
            Conversation(max_turns=0)

    def test_long_answers_are_previewed_not_pasted_whole(self):
        self.memory.add("q", "word " * 500)
        block = self.memory.context_block()
        self.assertLess(len(block), 400)
        self.assertTrue(block.endswith("..."))


class HistoryInThePrompt(unittest.TestCase):
    def fake_results(self):
        class R:
            source = "guide_kestrelford.md"
            text = "Kestrelford: Getting there\n\nBuses run hourly."
        return [R()]

    def test_no_history_leaves_the_prompt_exactly_as_it_was(self):
        prompt = build_prompt("How do I get there?", self.fake_results())
        self.assertTrue(prompt.startswith("Documents:"))
        self.assertNotIn("Earlier in this conversation", prompt)

    def test_history_is_labelled_as_context_and_not_as_a_source(self):
        prompt = build_prompt("how about Sundays?", self.fake_results(), history="Q: a\nA: b")
        self.assertIn("Earlier in this conversation", prompt)
        self.assertIn("not a source of facts", prompt)
        # The documents still come after it, so the last thing the model reads
        # before the question is the real source material.
        self.assertLess(prompt.index("Earlier in this conversation"), prompt.index("Documents:"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
