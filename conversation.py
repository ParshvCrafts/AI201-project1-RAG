"""
Stretch feature 2: conversational memory.

The problem. Ask "how often do buses run from Brightwater to Kestrelford?" and
then "how about on Sundays?", and the second question is embedded on its own,
with no idea that it is about buses or Kestrelford. Retrieval returns whatever
in the corpus happens to be about Sundays, which is not the same subject at all.

What this does. It keeps the last few turns, decides whether the new question
is a follow-up, and if it is, folds the previous question into the text used
for *retrieval only*. The question put to the model is still the one the reader
typed, and the previous turn is handed over separately as context.

Why the split matters. Rewriting the question itself would put words in the
reader's mouth and make the answer hard to check against what was asked. What
retrieval needs and what the model needs are different things, so they are
built separately.

Why a heuristic rather than a model call. Asking the model to rewrite the
question would cost an extra API call per turn on a rate-limited free tier,
and would make the pipeline non-deterministic: the same two questions could
retrieve differently on Tuesday. A rule I can read is a rule I can unit-test,
and `test_conversation.py` does. The cost of that choice is honest and stated
in the README: the rule is conservative, and a follow-up phrased as a full
sentence with its own proper noun is treated as a fresh question.
"""

import re
from dataclasses import dataclass, field

# Words that only make sense against something already said.
REFERRING_WORDS = {
    "it", "its", "it's", "they", "them", "their", "there", "that", "this",
    "those", "these", "one", "ones", "same", "instead", "else", "other",
    "another",
}

# Openers that announce a follow-up outright.
FOLLOW_UP_OPENERS = (
    "how about", "what about", "and ", "but ", "or ", "also ", "then ",
    "what if", "why not", "any others", "anything else", "same for",
)

# A follow-up is short. Anything longer than this is treated as a fresh
# question even if it contains a pronoun, because by then it usually carries
# enough of its own subject to retrieve on.
MAX_FOLLOW_UP_WORDS = 10

# How many turns to keep. Three is enough for "and on Sundays?" to work two
# turns after the question it refers to, and short enough that the prompt does
# not fill up with history the model has to read past.
DEFAULT_MEMORY_TURNS = 3

# The previous answer is summarised into the prompt, not pasted whole.
ANSWER_PREVIEW_CHARS = 240


@dataclass
class Turn:
    """One question and what the system said back."""

    question: str
    answer: str
    sources: list[str] = field(default_factory=list)
    refused: bool = False


@dataclass
class Resolution:
    """What the memory decided to do with a question, and why."""

    question: str          # what the reader typed, unchanged
    retrieval_query: str   # what gets embedded
    is_follow_up: bool
    reason: str

    @property
    def explanation(self) -> str:
        if not self.is_follow_up:
            return f"treated as a new question ({self.reason})"
        return f"read as a follow-up ({self.reason}); retrieving on: {self.retrieval_query!r}"


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def looks_like_follow_up(question: str) -> tuple[bool, str]:
    """
    Decide whether a question leans on the one before it.

    Two ways to qualify, and both are deliberately narrow:
      • it opens with a phrase that announces a follow-up ("how about ...")
      • it is short AND contains a referring word ("is it open on Sundays?")

    A false positive costs more than a false negative here. Treating a fresh
    question as a follow-up drags the previous subject into retrieval and can
    answer the wrong question entirely; treating a follow-up as fresh only
    gives the reader what they would have got without this feature at all.
    """
    text = question.strip().lower()
    if not text:
        return False, "empty"

    for opener in FOLLOW_UP_OPENERS:
        if text.startswith(opener):
            return True, f"starts with {opener.strip()!r}"

    words = _words(text)
    if len(words) > MAX_FOLLOW_UP_WORDS:
        return False, f"{len(words)} words, too long to be leaning on the last one"

    referring = sorted(set(words) & REFERRING_WORDS)
    if referring:
        return True, f"short and refers back with {referring[0]!r}"

    return False, "no referring word and no follow-up opener"


class Conversation:
    """The last few turns, and the decision about what to do with a new one."""

    def __init__(self, max_turns: int = DEFAULT_MEMORY_TURNS, enabled: bool = True):
        if max_turns < 1:
            raise ValueError("max_turns has to be at least 1")
        self.max_turns = max_turns
        self.enabled = enabled
        self.turns: list[Turn] = []

    # ── state ────────────────────────────────────────────────────────────────

    def add(self, question: str, answer: str, sources=None, refused: bool = False) -> None:
        """
        Remember a turn.

        A refused turn is remembered too, and on purpose: without it, "how
        about on Sundays?" after a refusal would attach itself to whatever was
        asked before the refusal, which is two subjects ago.
        """
        self.turns.append(
            Turn(question=question, answer=answer, sources=list(sources or []), refused=refused)
        )
        del self.turns[: -self.max_turns]

    def reset(self) -> None:
        self.turns.clear()

    @property
    def last(self) -> Turn | None:
        return self.turns[-1] if self.turns else None

    # ── the two things the pipeline asks for ─────────────────────────────────

    def resolve(self, question: str) -> Resolution:
        """What to embed for this question."""
        if not self.enabled:
            return Resolution(question, question, False, "memory is off")
        if not self.turns:
            return Resolution(question, question, False, "nothing said yet")

        is_follow_up, reason = looks_like_follow_up(question)
        if not is_follow_up:
            return Resolution(question, question, False, reason)

        previous = self.turns[-1].question
        return Resolution(question, f"{previous} {question}", True, reason)

    def context_block(self) -> str | None:
        """
        The history as the model sees it, or None when there is none.

        Only the questions and a short preview of each answer. The chunks that
        produced those answers are not repeated: retrieval has already run for
        this turn and whatever still matters should have come back again. This
        is context, not a second source of facts, and the prompt says so.
        """
        if not self.enabled or not self.turns:
            return None

        lines = []
        for turn in self.turns:
            answer = " ".join(turn.answer.split())
            if len(answer) > ANSWER_PREVIEW_CHARS:
                answer = answer[:ANSWER_PREVIEW_CHARS].rstrip() + "..."
            lines.append(f"Q: {turn.question}\nA: {answer}")
        return "\n\n".join(lines)
