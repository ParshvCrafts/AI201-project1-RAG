#!/usr/bin/env python3
"""
Unit tests for scorer.py.

    python -m unittest test_scorer -v

Every verdict in the unit 2 write-up rests on this file, so it is the last
place that should go untested. If the scorer is wrong, the run log is wrong and
the diagnosis is wrong, and nothing downstream would notice.

Offline. `judge` writes a scorecard as a side effect, so these tests set
AI201_NO_SCORECARD=1 and never touch results/.
"""

import os
import unittest

import scorer

os.environ["AI201_NO_SCORECARD"] = "1"


def results(*texts):
    """Fake retrieved chunks. The scorer reads .text, .source and .distance."""
    class R:
        def __init__(self, text, i):
            self.text = text
            self.source = f"guide_{i}.md"
            self.distance = 0.3 + i / 100

    return [R(t, i) for i, t in enumerate(texts)]


class Normalising(unittest.TestCase):
    def test_case_and_whitespace_do_not_matter(self):
        self.assertTrue(scorer.contains("Every   Two\nHours on Saturdays", "every two hours"))

    def test_curly_and_straight_apostrophes_match(self):
        # The corpus uses typographic apostrophes and questions are typed with
        # straight ones. Without this, "Marchwood's" never matches itself.
        self.assertTrue(scorer.contains("Marchwood’s trams", "Marchwood's trams"))

    def test_an_empty_expectation_never_matches(self):
        # Otherwise a question with no `expects` filled in would score as a
        # pass on every run, which is worse than useless.
        self.assertFalse(scorer.contains("anything at all", ""))


class CriterionOne(unittest.TestCase):
    def test_true_when_a_chunk_holds_the_fact(self):
        chunks = results("Kestrelford: Getting there\n\nBuses run every two hours on Saturdays.")
        self.assertTrue(scorer.retrieved_contains_answer("two hours", chunks))

    def test_false_when_no_chunk_holds_it(self):
        chunks = results("Marchwood: Getting around\n\nTrams every 8 minutes.")
        self.assertFalse(scorer.retrieved_contains_answer("two hours", chunks))

    def test_it_judges_the_chunks_and_not_the_answer(self):
        # A right answer built from nothing retrieved is the failure grounding
        # exists to prevent, so criterion 1 must not be satisfied by it.
        chunks = results("something unrelated about the harbour")
        self.assertFalse(scorer.retrieved_contains_answer("1963", chunks))


class CriterionTwo(unittest.TestCase):
    def test_filenames_are_found_however_they_are_wrapped(self):
        answer = "See `guide_kestrelford.md` and (guide_walking.md) and [guide_eating.md]."
        self.assertEqual(
            scorer.cited_files(answer),
            ["guide_kestrelford.md", "guide_walking.md", "guide_eating.md"],
        )

    def test_a_repeated_filename_is_listed_once(self):
        answer = "guide_kestrelford.md says so, and guide_kestrelford.md agrees."
        self.assertEqual(scorer.cited_files(answer), ["guide_kestrelford.md"])

    def test_an_answer_with_no_filename_fails(self):
        self.assertFalse(scorer.names_a_source("It costs two pounds."))


class CriterionFive(unittest.TestCase):
    """The two readings, against the real corpus files."""

    def test_lenient_passes_when_one_cited_file_holds_the_fact(self):
        answer = "Every two hours on Saturdays (guide_kestrelford.md, guide_regional_transport.md)."
        check = scorer.citation_check(answer, "two hours")
        self.assertTrue(check["lenient"])

    def test_strict_fails_on_the_paraphrase_that_caused_the_miss(self):
        # guide_kestrelford.md says "every two hours on Saturdays";
        # guide_regional_transport.md says "two-hourly on Saturdays".
        answer = "Every two hours on Saturdays (guide_kestrelford.md, guide_regional_transport.md)."
        check = scorer.citation_check(answer, "two hours")
        self.assertFalse(check["strict"])
        self.assertEqual(check["supporting"], ["guide_kestrelford.md"])

    def test_both_readings_pass_when_one_file_is_cited_and_it_is_right(self):
        check = scorer.citation_check("Trams run every 8 minutes (guide_marchwood.md).", "8 minutes")
        self.assertTrue(check["lenient"])
        self.assertTrue(check["strict"])

    def test_a_citation_of_a_file_that_does_not_exist_fails(self):
        check = scorer.citation_check("Every two hours (guide_atlantis.md).", "two hours")
        self.assertFalse(check["lenient"])

    def test_no_citation_at_all_fails_both(self):
        check = scorer.citation_check("Every two hours on Saturdays.", "two hours")
        self.assertFalse(check["lenient"])
        self.assertFalse(check["strict"])


class Scorecards(unittest.TestCase):
    def test_a_refusal_is_not_counted_as_an_answer(self):
        from gate import REFUSAL

        card = scorer.scorecard("q", "two hours", REFUSAL, results("nothing relevant"))
        self.assertTrue(card["refused"])
        # None, not False: a refused question has no opinion to offer about
        # whether an answer named a source.
        self.assertIsNone(card["c2_names_a_source"])
        self.assertIsNone(card["c5_strict"])

    def test_judge_returns_criterion_one_and_nothing_else(self):
        chunks = results("Buses run every two hours on Saturdays.")
        self.assertTrue(scorer.judge("q", "two hours", "anything (guide_x.md)", chunks))
        self.assertFalse(scorer.judge("q", "1963", "anything (guide_x.md)", chunks))

    def test_the_scorecard_carries_everything_the_run_log_needs(self):
        card = scorer.scorecard("q", "8 minutes", "Trams every 8 minutes (guide_marchwood.md).",
                                results("Marchwood: trams every 8 minutes"))
        for key in ("c1_retrieved_contains_answer", "c2_names_a_source",
                    "c5_lenient", "c5_strict", "best_distance", "retrieved_sources"):
            self.assertIn(key, card)


class CriterionFour(unittest.TestCase):
    def test_the_real_index_passes_the_shape_check(self):
        import chunker
        from ingest import load_documents

        shape = scorer.chunk_shape(chunker.split_documents(load_documents()))
        self.assertTrue(shape["passes"])
        self.assertEqual((shape["count"], shape["min"], shape["max"]), (97, 152, 565))

    def test_a_scrap_is_caught(self):
        from chunker import Chunk

        tiny = [Chunk(text="too short.", source="a.md", index=0, produced_by="f")]
        shape = scorer.chunk_shape(tiny)
        self.assertFalse(shape["passes"])
        self.assertEqual(shape["too_short"], ["a.md#0"])

    def test_a_chunk_starting_mid_sentence_is_caught(self):
        from chunker import Chunk

        body = "and then the road climbs steeply for four miles before it levels out again near the top of the pass, which is where the view opens up across the whole valley below."
        chunks = [Chunk(text=f"Town: Section\n\n{body}", source="a.md", index=0, produced_by="f")]
        shape = scorer.chunk_shape(chunks)
        self.assertEqual(shape["starts_mid_sentence"], ["a.md#0"])
        self.assertFalse(shape["passes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
