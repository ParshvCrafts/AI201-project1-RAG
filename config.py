"""
Settings for The Unofficial Guide.

Everything you're likely to change lives here, at the top, on purpose.
You'll edit THRESHOLD in Milestone 4 and the chunking numbers in Milestone 3.

Anything you set in your .env file wins over the defaults here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


# ─── The corpus you're working with ──────────────────────────────────────────
# Change this to switch corpora, or pass --corpus on the command line.
# Options are the folder names inside corpora/. See corpora/README.md.

CORPUS = os.getenv("AI201_CORPUS", "city_guides")


# ─── Chunking (Milestone 3) ──────────────────────────────────────────────────
# Measured against city_guides: 14 documents, 84 `##` sections, mean section
# 311 characters, longest 708, shortest 173.
#
# CHUNK_SIZE is a CAP, not a window. chunker.py::section_split cuts on section
# headings first and only splits a section when it exceeds this. 600 is roughly
# twice the median section, so 81 of the 84 sections stay whole and only three
# come apart — the long list-style sections in guide_accessibility.md,
# guide_eating.md and guide_walking.md that run through several towns one after
# another. Splitting those is the point: one town per chunk retrieves better
# than five.
CHUNK_SIZE = 600        # maximum characters per chunk, breadcrumb included

# Only used when a single section has to be split. Neighbouring sections never
# overlap — they are different subjects. 100 characters is about one sentence
# in this corpus, enough to keep a fact that straddles the cut in one piece.
CHUNK_OVERLAP = 100     # characters carried between pieces of one split section


# ─── Retrieval (Milestone 4) ─────────────────────────────────────────────────

# Measured: the chunk holding the answer comes back at rank 1 or 2 for all five
# test questions, so 3 would do for four of them. It is 5 because the fifth
# question needs two documents — the Kestrelford line closure is in the town
# guide and what the trackbed became is in guide_walking.md — and the second
# half only appears by rank 5. Five chunks of ~310 characters is about 1,550
# characters of context, which is cheap.
TOP_K = 5               # how many chunks to pull back per question

# The relevance gate. If the best chunk is further away than this, the system
# refuses to answer instead of handing the model thin material.
#
# LOWER IS BETTER: 0.3 is a close match, 0.9 is unrelated.
#
# Measured in Milestone 4 against the 97-chunk section_split index:
#   my five test questions   0.233 - 0.456
#   the five OUT_OF_SCOPE    0.810 - 0.967
#   seven travel-shaped questions about real places this corpus
#   has never heard of       0.443 - 0.697
#
# The first two groups leave a gap of 0.354 and the midpoint of that gap is
# 0.633. I went lower, to 0.55, because the third group is the failure that
# actually happens: "when is the best season to visit the Lake District" looks
# like a question this corpus answers. 0.55 keeps 0.094 of headroom over my
# hardest real question and still refuses four of those seven. The three it
# lets through are caught, if at all, by GROUNDING_INSTRUCTION in generate.py,
# which is why that instruction names places rather than just saying "be
# grounded".
THRESHOLD = 0.55


# ─── Models ──────────────────────────────────────────────────────────────────
# Embeddings run on your own machine and cost no API quota.
# Only generation calls out to a service.

# This is the model Chroma bundles, and leaving it alone is the fast path: it
# downloads about 80 MB from Chroma's own CDN and needs nothing else installed.
#
# Setting it to any other name — unit 2's "try a second embedding model"
# stretch option — switches to loading that model from Hugging Face instead,
# which needs `pip install 'sentence-transformers>=3.4,<3.5'` first. store.py
# says so with a real error message rather than a stack trace if you forget.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MODEL = os.getenv("AI201_MODEL", "gemini-3.5-flash-lite")


# ─── Rate limiting and quota guards ──────────────────────────────────────────
# You should not need to touch these. They exist so that a runaway loop costs
# you a warning instead of your whole day's allowance.

REQUESTS_PER_MINUTE = 30       # outgoing calls the limiter will allow per minute
SESSION_REQUEST_BUDGET = 300   # stop and warn rather than draining the daily quota
MAX_RETRIES = 4                # on 429 / resource-exhausted, with backoff

CACHE_ENABLED = os.getenv("AI201_CACHE", "1") != "0"
CACHE_DIR = ROOT / ".cache"


# ─── Paths ───────────────────────────────────────────────────────────────────

CORPORA_DIR = ROOT / "corpora"
CHROMA_DIR = ROOT / "chroma_db"
RESULTS_DIR = ROOT / "results"


def corpus_path(name: str | None = None) -> Path:
    """Folder holding the documents for a corpus."""
    return CORPORA_DIR / (name or CORPUS) / "documents"


def collection_name(name: str | None = None, variant: str = "default") -> str:
    """
    Name of the vector-store collection for a corpus.

    `variant` lets you index the same corpus two different ways and query both
    without deleting anything — you'll want that in unit 2 when you compare
    chunking strategies.

    Chroma is fussy about collection names: 3 to 63 characters, starting and
    ending with a letter or digit, and nothing but letters, digits, underscores
    and hyphens in between. If you bring your own corpus and name the folder
    something Chroma won't accept, this cleans it up rather than failing.
    """
    import re

    raw = f"{name or CORPUS}__{variant}"
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", raw)
    cleaned = cleaned.strip("_-")          # must start and end alphanumeric
    if not cleaned or not cleaned[0].isalnum():
        cleaned = f"c{cleaned}"
    if not cleaned[-1].isalnum():
        cleaned = f"{cleaned}0"
    return cleaned[:63].rstrip("_-") or "collection"
