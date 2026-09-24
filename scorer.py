"""
Deciding what counts as correct.

`run_eval.py` picks this file up automatically and calls `judge` once per
question per run. It has room for exactly one true/false per run, so `judge`
answers the question criterion 1 asks — did retrieval bring back a chunk that
actually contains the answer — and, because it is handed everything the other
criteria need at the same moment, it also writes a full scorecard for that run
into `results/`.

That side effect is deliberate and it is the one design decision in this file
worth arguing about. The alternative was to parse the answers back out of the
Markdown run log afterwards, which means a regex against a report format I do
not control, breaking silently the first time that format changes. Writing the
scorecard at the point where the data already exists is uglier to read and
harder to get wrong. The scorecard is committed alongside the run log.

What this file does NOT do is decide anything subtle. Every check here is a
normalised substring test. That is blunt on purpose: the same answer has to
score the same way on Monday and Wednesday, and a human reading fifteen answers
will not manage that. Where the blunt check disagrees with what a person would
say, the README records the disagreement rather than hiding it, because a
criterion I cannot measure the same way twice is a criterion worth revising.
"""

import json
import os
import re
import unicodedata
from pathlib import Path

import config

SCORECARD_PATH = config.RESULTS_DIR / "scorecard.jsonl"

# A filename as it appears in an answer: guide_kestrelford.md, possibly wrapped
# in backticks, brackets or parentheses.
FILENAME_RE = re.compile(r"[A-Za-z0-9_\-]+\.(?:md|txt)")


def normalise(text: str) -> str:
    """
    Fold text down to something two spellings of the same fact can share.

    Lowercased, accents stripped, every run of whitespace collapsed to one
    space, and the curly punctuation the corpus uses replaced with the straight
    kind. Without the last part, "Kestrelford's" in a question never matches
    "Kestrelford's" in a document when one of them uses a typographic
    apostrophe.
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def contains(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return normalise(needle) in normalise(haystack)


# ─── Criterion 1: did retrieval find the answer ──────────────────────────────


def retrieved_contains_answer(expects: str, results) -> bool:
    """True when at least one retrieved chunk contains the expected fact.

    This is a claim about retrieval, not about the answer. It is what criterion
    1 says, and it is worth keeping separate: an answer can be right because the
    model knew something, which is exactly the failure grounding is meant to
    prevent.
    """
    return any(contains(r.text, expects) for r in results)


# ─── Criterion 2: did the answer name a source ───────────────────────────────


def cited_files(answer: str) -> list[str]:
    """Every filename the answer mentions, in order, without duplicates."""
    seen: list[str] = []
    for match in FILENAME_RE.findall(answer or ""):
        if match not in seen:
            seen.append(match)
    return seen


def names_a_source(answer: str) -> bool:
    return bool(cited_files(answer))


# ─── Criterion 5: is the source it named the right one ───────────────────────


def _corpus_text(source: str, corpus: str | None = None) -> str:
    path = config.corpus_path(corpus) / source
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def citation_check(answer: str, expects: str, corpus: str | None = None) -> dict:
    """
    Two readings of criterion 5, because they disagree and the difference is
    the interesting part.

    `lenient`: at least one file the answer cites really does contain the fact.
    `strict`:  every file the answer cites contains it.

    Strict is closer to what criterion 5 says. It is also unfair in a way I did
    not foresee when I wrote the criterion: two documents can state the same
    fact in different words, and an answer that cites both is more honest than
    one that cites one. "Every two hours on Saturdays" in guide_kestrelford.md
    and "two-hourly on Saturdays" in guide_regional_transport.md are the same
    fact, and a substring test can only see one of them.
    """
    files = cited_files(answer)
    if not files:
        return {"files": [], "lenient": False, "strict": False, "supporting": []}

    supporting = [f for f in files if contains(_corpus_text(f, corpus), expects)]
    return {
        "files": files,
        "supporting": supporting,
        "lenient": bool(supporting),
        "strict": len(supporting) == len(files),
    }


# ─── What run_eval.py calls ──────────────────────────────────────────────────


def scorecard(question: str, expects: str, answer: str, results) -> dict:
    """Every criterion this run can speak to, in one dictionary."""
    from gate import REFUSAL

    refused = normalise(answer) == normalise(REFUSAL)
    citation = citation_check(answer, expects)

    return {
        "question": question,
        "expects": expects,
        "refused": refused,
        "answer": answer,
        "best_distance": min((r.distance for r in results), default=None),
        "retrieved_sources": sorted({r.source for r in results}),
        # criterion 1
        "c1_retrieved_contains_answer": retrieved_contains_answer(expects, results),
        # criterion 2 — a refusal is not an answer, so it is not counted here
        "c2_names_a_source": (None if refused else names_a_source(answer)),
        # criterion 5, both readings
        "c5_cited_files": citation["files"],
        "c5_supporting_files": citation["supporting"],
        "c5_lenient": (None if refused else citation["lenient"]),
        "c5_strict": (None if refused else citation["strict"]),
        # useful for reading the log later
        "answer_contains_expected": contains(answer, expects),
    }


def judge(question: str, expects: str, answer: str, results) -> bool:
    """
    The one boolean `run_eval.py` has room for: criterion 1.

    Also appends the full scorecard for this run to results/scorecard.jsonl —
    see the module docstring for why that happens here rather than afterwards.
    Set AI201_NO_SCORECARD=1 to turn the writing off; the return value never
    changes.
    """
    card = scorecard(question, expects, answer, results)

    if os.getenv("AI201_NO_SCORECARD") != "1":
        config.RESULTS_DIR.mkdir(exist_ok=True)
        with open(SCORECARD_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(card, ensure_ascii=False) + "\n")

    return card["c1_retrieved_contains_answer"]


# ─── Criterion 4, which has nothing to do with a run ─────────────────────────


def chunk_shape(chunks) -> dict:
    """
    Criterion 4 measured: every chunk between 150 and 600 characters, and no
    chunk starting or ending mid-sentence.

    This one is deterministic and belongs to the index rather than to a run, so
    it is computed once from the chunker rather than three times from answers.
    """
    lengths = [len(c.text) for c in chunks]
    too_short = [c.label for c in chunks if len(c.text) < 150]
    too_long = [c.label for c in chunks if len(c.text) > config.CHUNK_SIZE]

    starts_mid = []
    ends_mid = []
    for chunk in chunks:
        body = chunk.text.split("\n\n", 1)[-1].strip()
        if body and body[0].islower():
            starts_mid.append(chunk.label)
        if body and body[-1] not in ".!?\"')":
            ends_mid.append(chunk.label)

    return {
        "count": len(chunks),
        "min": min(lengths, default=0),
        "max": max(lengths, default=0),
        "mean": (sum(lengths) // len(lengths)) if lengths else 0,
        "too_short": too_short,
        "too_long": too_long,
        "starts_mid_sentence": starts_mid,
        "ends_mid_sentence": ends_mid,
        "passes": not (too_short or too_long or starts_mid or ends_mid),
    }


def read_scorecards(path: Path | None = None) -> list[dict]:
    """Every scorecard written so far, oldest first."""
    path = Path(path or SCORECARD_PATH)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
