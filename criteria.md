# Acceptance criteria — The Unofficial Guide

Corpus: `city_guides` (14 Markdown travel guides, 28,958 characters — nine town
guides and five that cut across all of them).

Five criteria that say what "working" means for this system, written in unit 1
**before** any results existed. Every target below is a number or something a
person can watch happen, and every reason points at something I measured in
this corpus or in this pipeline.

The five test questions these refer to are in `questions.py`. The five
out-of-corpus questions are in `OUT_OF_SCOPE` at the bottom of the same file.

---

## 1. Retrieved chunks contain the answer

For at least 4 of my 5 test questions, the retrieved chunks include one that
contains the answer.

**Why this target:** Four of my five questions have their answer sitting inside
a single `##` section, so retrieval only has to find one chunk. The fifth asks
what happened to Kestrelford's railway line and what the trackbed is used for
now, and no single document answers both halves: the 1963 closure is in
`guide_kestrelford.md`, and what the trackbed became is in `guide_walking.md`
and `guide_regional_transport.md`. I wrote that question knowing it was the
hard one, so 5 of 5 would be claiming my chunking solves a problem that is
really about retrieving from two documents at once. Four of five is the honest
target, and if the hard one comes back too, I want that to show as a surprise
rather than as the bar I set.

---

## 2. Every answer names a source

Every answer the system produces names at least one source document.

**Why this target:** All five, not four, because this one does not depend on
luck. `generate.py` never sees a bare question — `build_prompt` labels every
excerpt with `[from <filename>]` and `GROUNDING_INSTRUCTION` tells the model to
name the file, and on top of that the relevance gate means an answer is only
ever produced when at least one chunk came back. For this to fail, the model
would have to ignore a filename that is sitting in front of it, and that is a
defect I would want to see rather than tolerate at 4 of 5. Refusals are not
answers and are covered by criterion 3, so they do not count against this one.

---

## 3. The relevance gate stops out-of-corpus questions

When I ask a question my documents clearly don't cover, the relevance gate
stops it and the system returns "I don't have enough information about that" —
in at least 4 of 5 tries.

**Why this target:** Measured in Milestone 4, my five in-corpus questions came
back with best distances of 0.233 to 0.456 and the five `OUT_OF_SCOPE`
questions with 0.810 to 0.967 — a gap of 0.354 with nothing in it, and my
cutoff of 0.55 sits inside it. Against those five, 5 of 5 should happen every
time. I am still writing 4 of 5, because I also ran seven questions that are
travel-shaped but about real places my corpus has never heard of, and those
scored 0.443 to 0.697, straight through the middle of my in-corpus range. My
corpus is about towns, transport, eating and seasons, and a question with that
shape looks close no matter where it is about. The five in `OUT_OF_SCOPE` are
from a different world entirely and flatter the gate; the target has to survive
the questions I have not thought of yet, not just the easy five.

---

## 4. Chunks are whole sections, not fragments

Every chunk in the index is between 150 and 600 characters, and in a sample of
five printed with `python app.py chunks -n 5`, all five begin at the start of a
sentence and end at the end of one, with no sentence cut in half at either
edge.

**Why this target:** The starter's fixed 800-character windows turned these 14
documents into 51 chunks, and the shortest was 24 characters — the leftover
tail of a document that did not divide evenly, which is worth nothing to
anybody. The floor of 150 exists to make that specific failure impossible. The
ceiling of 600 comes from the corpus too: there are 84 `##` sections across the
14 files, averaging 311 characters with the longest at 708, so a 600-character
cap keeps an ordinary section whole while forcing apart the three long sections
that list several towns one after another. Both halves are checkable by anyone:
the range by reading the summary line `python app.py index` prints, the
sentence edges by reading the five chunks.

---

## 5. The source an answer cites is the file the fact is actually in

For all 5 of my test questions, the filename the answer names is a file that
genuinely contains the fact being stated. Checking it means opening that file
and finding the sentence.

**Why this target:** Naming a source and naming the right source are different
things, and this corpus punishes the difference. The `## Practical notes`
section is word-for-word identical in 9 of the 14 files, so nine chunks with no
distinguishing text compete for the same question and whichever one comes back
first decides which town gets blamed for the answer. Worse,
`guide_accessibility.md` says the nearest full hospital is in Marchwood while
that repeated boilerplate says it is in Brightwater, so a citation picked at
random can attach a real filename to a wrong claim. I set this at 5 of 5 rather
than 4 of 5 because a confidently wrong citation is the failure I would least
want a reader to hit, and because my chunker is built to prevent it — every
chunk carries a `Title: Heading` breadcrumb precisely so those nine identical
sections stop being identical. If the breadcrumb does not do that job, I want
this criterion to fail loudly.

> **Revised in unit 2:** For all 5 of my test questions, every file the answer
> cites contains a sentence that *supports* the fact, and none contradicts it.
> A paraphrase counts as support; identical wording is not required.
>
> **Why revised:** I could not measure the original the same way twice. It says
> the cited file "contains the fact", and my check reads that literally, so on
> question 1 it fails an answer that says "every two hours on Saturdays" and
> cites both `guide_kestrelford.md`, which uses those words, and
> `guide_regional_transport.md`, which says "two-hourly on Saturdays". Both
> files state the fact. Only one contains the sentence. I wrote the criterion
> thinking about a citation pointing at the wrong town, and never considered
> two files agreeing in different words, which is better behaviour rather than
> worse. This is a revision because the criterion could not be measured, not
> because I missed it: **the unit 2 verdict stays MISSED at 4 of 5**, against
> the original target, and the fix I attempted is written up in the README.

---

## Unit 2 note on criterion 3

Criterion 3 was met, 5 of 5 on every run, and it was too easy. The five
`OUT_OF_SCOPE` questions are about Mongolia, diesel engines, the World Cup,
ibuprofen and Rust, and every one lands at distance 0.810 or worse against a
0.55 cutoff — no version of this system fails that test.

The questions that do break it are travel-shaped ones about real places the
corpus has never heard of. Added this unit as `NEAR_MISS` in `questions.py` and
measured: **0 of 7 refused before the improvement, 7 of 7 after.** The original
target stays where I wrote it. Next unit it should read "at least 6 of 7
near-miss questions refused, and 5 of 5 out-of-scope", which is a target this
system could plausibly miss.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 2 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 1. Retrieved chunks contain the answer

         For at least 4 of my 5 test questions, the retrieved chunks include
         one that contains the answer.

         **Why this target:** ...

         > **Revised in unit 2:** For at least 4 of 5 questions, the top three
         > results contain the answer.
         >
         > **Why revised:** I couldn't judge "the chunks include one that
         > contains the answer" the same way twice — I scored two questions
         > differently on Monday than on Wednesday. The new version is
         > something I can actually check.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said 4 of 5 but got 2 of 5, so 2 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.

     The whole reason the originals stay visible is so someone can see what you
     said before you knew the answer.
     ───────────────────────────────────────────────────────────────────────── -->
