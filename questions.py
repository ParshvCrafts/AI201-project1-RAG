"""
Your test questions.

Milestone 2 asks you to write five questions your system should be able to
answer from your corpus, specific enough to have a right answer.

  ✗ "What are good dining halls?"          — no right answer
  ✓ "What do students say about wait times at Commons during lunch?"

Fill in `QUESTIONS` below. `expects` is a word or short phrase you'd expect a
correct answer to contain — you'll use it in unit 2 when you build a scorer,
and having written it now means you decided what "correct" meant before you saw
any results.

`OUT_OF_SCOPE` holds five questions your documents clearly don't cover. You
need these in Milestone 4 to find where your relevance cutoff belongs, and
again in unit 2, where `run_eval.py` runs them through the gate and writes what
happened into your run log — that's the evidence for criterion 3.

Swap them for your own if you like. Keep five of them either way: criterion 3
names a target of "4 of 5", and four of three is not a thing.
"""

QUESTIONS = [
    # Five questions about city_guides. Each one has a single right answer that
    # is stated in the documents, and `expects` is the shortest string a
    # correct answer has to contain for me to count it.
    {
        "question": "How often do buses run from Brightwater to Kestrelford on Saturdays?",
        "expects": "two hours",
    },
    {
        "question": "How much does it cost to climb the church tower in Kestrelford?",
        # The pound sign is part of it: bare "2" would match almost any answer.
        "expects": "£2",
    },
    {
        "question": "Why does the road to Elder Ness flood, and how often does it happen?",
        "expects": "spring tides",
    },
    {
        "question": "How often do Marchwood's trams run on weekdays?",
        "expects": "8 minutes",
    },
    {
        # The hard one on purpose: no single document holds the whole answer.
        # The closure year is in guide_kestrelford.md, what the trackbed is used
        # for now is in guide_walking.md and guide_regional_transport.md.
        "question": "What happened to Kestrelford's railway line, and what is the old trackbed used for now?",
        "expects": "1963",
    },
]

# Questions from a different world entirely. Your gate should refuse all five.
#
# There are five of these because criterion 3 in criteria.md names a target of
# "at least 4 of 5" — you need five things to try before you can report 4 of 5.
# `run_eval.py` runs these through retrieval and the gate on every eval and
# records what happened, so criterion 3 has evidence in the run log alongside
# the others. They cost no model calls: a refusal never reaches the model.
OUT_OF_SCOPE = [
    "What is the capital of Mongolia?",
    "How do I change the oil in a diesel engine?",
    "Who won the 1994 World Cup?",
    "What is the recommended dosage of ibuprofen for a headache?",
    "How do I write a for loop in Rust?",
]


# Unit 2. Travel-shaped questions about real places this corpus has never heard
# of. OUT_OF_SCOPE above is from a different world entirely — capitals, engines,
# football — and every one of those sits at distance 0.81 or worse, which makes
# the relevance gate look better than it is. These are the hard ones: same
# shape as a question the corpus really answers, different subject. Before
# unit 2's improvement they scored 0.443 to 0.697 and all seven were answered.
# `run_eval.py::check_near_miss` puts them through retrieval and the gate on
# every run and writes what happened into the run log.
NEAR_MISS = [
    "When is the best season to visit the Lake District?",
    "Is there parking near the beach in Brighton?",
    "What time do the buses run in Copenhagen on Sundays?",
    "What are the best restaurants in Paris?",
    "How do I get from Manchester to Liverpool by train?",
    "How much is a ticket to climb the Eiffel Tower?",
    "Where can I hire a bike in Amsterdam?",
]


def answered() -> list[dict]:
    """The questions you've actually filled in."""
    return [q for q in QUESTIONS if q.get("question", "").strip()]
