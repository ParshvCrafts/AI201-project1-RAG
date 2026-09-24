#!/usr/bin/env python3
"""
Unit tests for unit 2's improvement 1: the gate's unknown-name check.

    python -m unittest test_gate -v

Offline. No embedding, no vector store, no API calls — the name check reads the
corpus text and the question, and nothing else. `Result` objects are faked with
just the field the gate looks at.
"""

import unittest

import config
import gate


def results(*distances):
    """Fake retrieval results. The gate only ever reads `.distance`."""
    class R:
        def __init__(self, distance):
            self.distance = distance
    return [R(d) for d in distances]


class Vocabulary(unittest.TestCase):
    def test_the_corpus_words_are_there_and_other_places_are_not(self):
        words = gate.corpus_vocabulary()
        self.assertIn("kestrelford", words)
        self.assertIn("marchwood", words)
        self.assertNotIn("brighton", words)
        self.assertNotIn("amsterdam", words)

    def test_it_is_cached_rather_than_re_read(self):
        self.assertIs(gate.corpus_vocabulary(), gate.corpus_vocabulary())


class UnknownNames(unittest.TestCase):
    def test_a_place_the_corpus_never_mentions_is_flagged(self):
        self.assertEqual(gate.unknown_names("Is there parking in Brighton?"), ("Brighton",))

    def test_places_the_corpus_does_mention_are_not(self):
        self.assertEqual(gate.unknown_names("How do I get to Kestrelford from Marchwood?"), ())

    def test_the_first_word_is_not_treated_as_a_name(self):
        # "Amsterdam" here is the subject; "Where" is just a capital letter.
        self.assertEqual(gate.unknown_names("Where can I hire a bike?"), ())

    def test_mid_question_question_words_are_not_names(self):
        self.assertEqual(gate.unknown_names("In Kestrelford, What time is the market?"), ())

    def test_several_unknown_names_all_come_back_in_order(self):
        self.assertEqual(
            gate.unknown_names("How do I get from Manchester to Liverpool by train?"),
            ("Manchester", "Liverpool"),
        )

    def test_the_same_name_twice_is_reported_once(self):
        self.assertEqual(
            gate.unknown_names("Is Brighton nicer than Brighton was?"), ("Brighton",)
        )

    def test_an_empty_question_is_not_an_error(self):
        self.assertEqual(gate.unknown_names(""), ())


class KnownBlindSpot(unittest.TestCase):
    """
    The limitation, written down as a test so it cannot be forgotten.

    The check is capitalisation-dependent. The version that ignores
    capitalisation refuses three of my own five test questions, because
    "trams", "cost" and "flood" do not appear in the corpus in those exact word
    forms, so I chose the narrow rule knowingly. If this test ever starts
    failing, someone has made the rule broader and should re-measure the false
    refusal rate before celebrating.
    """

    def test_a_lower_case_place_name_is_not_caught(self):
        self.assertEqual(gate.unknown_names("is there parking in brighton?"), ())


class TheGate(unittest.TestCase):
    def test_a_close_question_passes(self):
        decision = gate.check(results(0.30, 0.42), question="How do I get to Kestrelford?")
        self.assertTrue(decision.passed)
        self.assertEqual(decision.refused_by, "")

    def test_a_distant_question_is_refused_on_distance(self):
        decision = gate.check(results(0.81), question="How do I get to the market?")
        self.assertFalse(decision.passed)
        self.assertEqual(decision.refused_by, "distance")

    def test_an_unknown_name_is_refused_even_when_the_distance_is_good(self):
        # This is the whole improvement. 0.443 is what the Lake District
        # question actually scored, comfortably under the 0.55 cutoff.
        decision = gate.check(
            results(0.443), question="When is the best season to visit the Lake District?"
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.refused_by, "unknown name")
        self.assertIn("Lake", decision.unknown_names)

    def test_the_explanation_says_which_check_refused(self):
        decision = gate.check(results(0.443), question="Is there parking in Brighton?")
        self.assertIn("Brighton", decision.explanation)
        self.assertIn("appears nowhere in the corpus", decision.explanation)

    def test_without_a_question_the_gate_behaves_exactly_as_it_did_before(self):
        # Every caller in this repo passes the question now, but the parameter
        # is optional so that serve.py and anything written against the old
        # signature keeps working rather than breaking silently.
        self.assertTrue(gate.check(results(0.30)).passed)
        self.assertFalse(gate.check(results(0.90)).passed)

    def test_nothing_retrieved_is_a_refusal(self):
        self.assertFalse(gate.check([]).passed)

    def test_the_threshold_can_still_be_overridden(self):
        self.assertTrue(gate.check(results(0.70), threshold=0.8).passed)
        self.assertFalse(gate.check(results(0.70), threshold=0.6).passed)

    def test_the_configured_cutoff_is_the_one_the_readme_documents(self):
        self.assertEqual(config.THRESHOLD, 0.55)


class MeasuredBehaviour(unittest.TestCase):
    """
    The numbers the README reports for this improvement, pinned.

    Retrieval is not involved: these assert what the name check does on its
    own, question by question, which is the claim being made.
    """

    def test_every_near_miss_question_is_caught(self):
        import questions as qs

        missed = [q for q in qs.NEAR_MISS if not gate.unknown_names(q)]
        self.assertEqual(missed, [], msg=f"near-miss questions not caught: {missed}")

    def test_no_test_question_is_caught(self):
        import questions as qs

        false_refusals = [q["question"] for q in qs.answered() if gate.unknown_names(q["question"])]
        self.assertEqual(false_refusals, [], msg=f"false refusals: {false_refusals}")

    def test_the_name_check_catches_three_of_the_five_out_of_scope_questions(self):
        # The other two are caught by distance, as they always were. Recorded
        # so that the README's "3 of 5" is a measurement and not a memory.
        import questions as qs

        caught = [q for q in qs.OUT_OF_SCOPE if gate.unknown_names(q)]
        self.assertEqual(len(caught), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
