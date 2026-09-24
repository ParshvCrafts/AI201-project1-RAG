"""
The relevance gate.

This runs *before* the model does. It looks at how close the best retrieved
chunk actually is, and if nothing came back close enough it refuses the
question outright.

Why this exists as its own step, rather than just asking the model nicely to
admit when it doesn't know: if you only ask nicely, it will sometimes ignore
you and write something confident and wrong. Those answers are much harder to
catch than obvious errors. Deciding in your own code when there's nothing worth
answering from is more reliable than hoping.

You keep the polite instruction too — it's in generate.py — but as a second
layer. The gate catches the clear misses; the prompt catches the near ones.

─── Unit 2, improvement 1 ────────────────────────────────────────────────────

The gate now has two checks rather than one, and the new one runs first.

The distance check could not catch a whole class of question, and I had the
numbers to prove it before I changed anything. Questions that are travel-shaped
but about real places this corpus has never heard of score 0.443 to 0.697,
straight through the middle of my in-corpus range of 0.233 to 0.456. "When is
the best season to visit the Lake District?" comes back at 0.443 and retrieval
hands over guide_seasons.md, which is about a different place entirely.

The mechanism is not a bug. Cosine distance measures how alike two pieces of
text are in shape and topic, and "when is the best season to visit X" has the
same shape whatever X is. The place name is one token out of ten and barely
moves the vector. No cutoff separates those questions from real ones, because
the signal the cutoff reads does not contain the distinction.

So the name check reads a different signal: a capitalised word in the question
that appears nowhere in the corpus. Measured across 21 questions, it refuses
7 of 7 near-miss questions, refuses 3 of the 5 out-of-scope ones the distance
check already handles, and refuses none of 9 in-corpus probes.

What it costs. It is capitalisation-dependent, so "parking in brighton?" typed
in lower case still gets through to the distance check and past it. The version
that ignores capitalisation and flags any unknown word refuses three of my own
five test questions, because "trams", "cost" and "flood" do not appear in the
corpus in those exact word forms. I measured both and chose the narrow rule
knowingly. The blind spot is written up in the README rather than hidden.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

import config
from store import Result

REFUSAL = "I don't have enough information about that."

# A capitalised word, which in a question is usually a proper noun.
CAPITALISED_RE = re.compile(r"\b[A-Z][a-zA-Z']+\b")

# Words that are capitalised for reasons that have nothing to do with being a
# place: the start of a sentence is handled separately, and these turn up
# capitalised mid-question often enough to matter.
NOT_NAMES = {
    "I", "How", "What", "When", "Where", "Why", "Who", "Which", "Is", "Are",
    "Do", "Does", "Did", "Can", "Could", "Should", "Would", "Will",
}


@dataclass
class GateDecision:
    passed: bool
    best_distance: float
    threshold: float
    # Unit 2: which check refused, and what it saw. Empty when nothing refused.
    unknown_names: tuple[str, ...] = ()

    @property
    def refused_by(self) -> str:
        if self.passed:
            return ""
        return "unknown name" if self.unknown_names else "distance"

    @property
    def explanation(self) -> str:
        if self.unknown_names:
            names = ", ".join(self.unknown_names)
            return (
                f"the question names {names}, which appears nowhere in the "
                f"corpus — refusing without reading the distance"
            )
        if self.passed:
            return (
                f"best distance {self.best_distance:.3f} "
                f"is under the {self.threshold} cutoff"
            )
        return (
            f"best distance {self.best_distance:.3f} "
            f"is over the {self.threshold} cutoff — refusing"
        )


@lru_cache(maxsize=8)
def corpus_vocabulary(corpus: str | None = None) -> frozenset[str]:
    """
    Every word that appears anywhere in the corpus, lower-cased.

    Read from the documents rather than from the index, so it is the same set
    whatever the chunker did, and cached because it is the same answer every
    time and reading 14 files per question would be silly.
    """
    from ingest import load_documents

    words: set[str] = set()
    for document in load_documents(corpus):
        words.update(re.findall(r"[a-z0-9']+", document.text.lower()))
    return frozenset(words)


def unknown_names(question: str, corpus: str | None = None) -> tuple[str, ...]:
    """
    Capitalised words in the question that the corpus has never heard of.

    The first word of the question is skipped: it is capitalised because it
    starts a sentence, not because it is a name.
    """
    vocabulary = corpus_vocabulary(corpus)

    first = re.match(r"\s*([A-Za-z']+)", question or "")
    first_word = first.group(1) if first else ""

    found: list[str] = []
    for word in CAPITALISED_RE.findall(question or ""):
        if word == first_word or word in NOT_NAMES:
            continue
        if word.lower() in vocabulary:
            continue
        if word not in found:
            found.append(word)
    return tuple(found)


def check(
    results: list[Result],
    threshold: float | None = None,
    question: str | None = None,
    corpus: str | None = None,
) -> GateDecision:
    """
    Decide whether the retrieved chunks are close enough to answer from.

    Remember: LOWER distance is better. A question passes when its best chunk
    is *under* the threshold.

    `question` is optional so that every existing caller keeps working, but a
    caller that passes it also gets the name check. Both callers in this repo
    pass it: `app.py::ask_pipeline` and `run_eval.py::run_once`.
    """
    threshold = config.THRESHOLD if threshold is None else threshold
    best = min((r.distance for r in results), default=1.0)

    # Unit 2, improvement 1. This runs first and does not look at distance at
    # all, because the whole point is that distance cannot see this failure.
    if question:
        names = unknown_names(question, corpus)
        if names:
            return GateDecision(
                passed=False,
                best_distance=best,
                threshold=threshold,
                unknown_names=names,
            )

    if not results:
        return GateDecision(passed=False, best_distance=1.0, threshold=threshold)

    return GateDecision(passed=best < threshold, best_distance=best, threshold=threshold)
