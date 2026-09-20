# The Unofficial Guide

Parshv Shah. Corpus: `city_guides`.

---

# Unit 1

## What This Does

This is a retrieval-augmented question answering system over `city_guides`, a
set of fourteen Markdown travel guides for an invented region: nine town guides
(Brightwater, Kestrelford, Marchwood, Halden Bay, Pellew Sands, Corry Vale,
Elder Ness, Givens Mill, Thornby Wells) and five guides that cut across all of
them on eating, walking, regional transport, seasons and accessibility. It
answers the kind of practical question you would ask a friend who lives there:
how often the Saturday bus to Kestrelford runs, why the road to Elder Ness
floods, what the church tower costs to climb, when the Marchwood trams run.

Ask a question and it embeds it, pulls back the five closest chunks, checks how
close the best one actually is, and either answers from those chunks with the
filename attached to each fact or says "I don't have enough information about
that" and stops. The refusal is a decision made in my own code before the model
is ever called, not a request that the model be honest. Questions the documents
do not cover get refused rather than answered from whatever the model happens to
know about real towns with similar names.

## Chunking Strategy

**Chunk size:** 600 characters, as a cap rather than a window
**Overlap:** 100 characters, and only inside a section that had to be split

The starter cut fixed 800-character windows and paid no attention to where
anything ended. On these fourteen documents that produced 51 chunks averaging
650 characters, the shortest of them 24 characters long, which is the leftover
tail of a document that did not divide evenly and is worth nothing to anybody.

What I noticed reading the documents is that they are already chunked. Every
file opens with a `# Title` and then runs through `## Getting there`,
`## Getting around`, `## Eat and drink`, `## What to see`, `## Where to stay`,
`## When to go`, `## Practical notes`. I counted 84 of those sections across the
fourteen files. They average 311 characters, the shortest is 173 and the longest
is 708. That is already the size a chunk wants to be, so my chunker
(`chunker.py::section_split`) cuts on the headings and leaves the section alone.

Two things I found while reading pushed the design past "split on headings".

The first is that a section almost never repeats the name of the town it belongs
to. "Getting there" under `# Kestrelford` talks about the bus from Brightwater
and never says Kestrelford once. Embedded on its own, the chunk has lost the one
word the question will be phrased with. So every chunk carries a `Title: Heading`
breadcrumb as its first line, and the section text sits underneath it.

The second is worse. The `## Practical notes` section is byte-for-byte identical
in nine of the fourteen files, all 279 characters of it, about cash at the market
and patchy mobile coverage. Without the breadcrumb that is nine indistinguishable
chunks competing for the same question, and whichever one comes back first
decides which town gets cited. That copy also says the nearest full hospital is
in Brightwater, while `guide_accessibility.md` says it is in Marchwood, so an
arbitrary pick can attach a real filename to the wrong claim. The breadcrumb is
what makes those nine chunks different from each other, and it is why criterion 5
is about the source being right rather than merely present.

The 600-character cap is where the two ideas meet. It is roughly twice the median
section, so 81 of the 84 sections stay whole. The three that do not are the long
ones in `guide_accessibility.md`, `guide_eating.md` and `guide_walking.md` that
run through several towns one after another, and those I want split: one town per
chunk retrieves better than five. Splitting happens at a paragraph boundary, or a
sentence boundary if a paragraph is itself too long, and only those pieces carry
the 100-character overlap. Two neighbouring sections never overlap, because they
are two different subjects and carrying Kestrelford's opening hours into
Marchwood's chunk is exactly the mistake the breadcrumb exists to prevent.

The result is 97 chunks: 84 sections, plus the 10 opening paragraphs that sit
above the first heading, plus 3 extra pieces from the sections that were split.
They average 310 characters, the shortest is 152 and the longest is 565. Nothing
is a scrap and nothing is a grab bag.

`test_chunker.py` pins all of this down. Thirty-two tests, no network, run with
`python -m unittest test_chunker`. Some of them check behaviour (a heading with
no body is dropped, a sentence longer than the cap is kept whole rather than cut
mid-word, overlap is carried between pieces of one section and never between two
sections) and some of them check the claims on this page against the real corpus,
so if I change the chunker and forget to update the numbers here, the tests fail.

## Sample Chunks

Printed with `python app.py chunks -n 5`.

**Chunk 1** — source: `guide_accessibility.md#0` — produced by: `chunker.py::section_split`

```
Getting around the region with limited mobility: Overview

An honest assessment rather than a promotional one. Some of these places are
difficult and it is better to know in advance.
```

**Chunk 2** — source: `guide_corry_vale.md#5` — produced by: `chunker.py::section_split`

```
Corry Vale: Where to stay

Perhaps thirty beds in the entire valley, spread across two pubs and a handful of farmhouse rooms. In summer these are booked months ahead. Camping is permitted on two marked fields and nowhere else.
```

**Chunk 3** — source: `guide_givens_mill.md#2` — produced by: `chunker.py::section_split`

```
Givens Mill: Getting around

Everything is on one street along the river. The mill is at one end and the church at the other, eight minutes apart. The riverside path continues in both directions for as far as you want to walk.
```

**Chunk 4** — source: `guide_kestrelford.md#5` — produced by: `chunker.py::section_split`

```
Kestrelford: Where to stay

Two inns on the square and a handful of rooms above the pubs. Booking ahead matters between May and September and not at all otherwise. There is no accommodation of any kind within four miles of the town in either direction.
```

**Chunk 5** — source: `guide_regional_transport.md#0` — produced by: `chunker.py::section_split`

```
Getting around the region: The railway

The line runs along the river valley, connecting Brightwater to the regional
hub in 50 minutes. Eleven services a day on weekdays, six on Sundays. The line
north of Brightwater closed in 1963 and everything beyond it is bus or car.

Tickets are cheaper booked the day before than on the day, and considerably
cheaper than that booked a week ahead. There is no ticket office at
Brightwater station outside weekday mornings; the machine on the platform takes
cards only.
```

Chunks 2, 3 and 4 are the ordinary case: one section, one complete thought, and
the breadcrumb tells you whose thought it is without reading anything else.
Chunk 5 is a two-paragraph section that stayed whole because it fits under the
cap, and it is the one I would watch: the second paragraph about ticket machines
is a different subject from the first about journey times, and if this corpus
grew I would want that section split. Chunk 1 is the shortest kind I produce, an
opening paragraph with no heading above it. On its own it says little, but it is
152 characters rather than the starter's 24, and the breadcrumb still says what
document it introduces.

## Sample Answer

**Question:** What happened to Kestrelford's railway line, and what is the old trackbed used for now?

**Answer:**

```
$ python app.py ask "What happened to Kestrelford's railway line, and what is the old trackbed used for now?"

  (best distance 0.338, cutoff 0.55)

Kestrelford's railway line was closed in 1963 ([guide_kestrelford.md],
[guide_walking.md]). The old trackbed is now used as a walking route
([guide_kestrelford.md]) and provides a six-mile walk to the next village
([guide_walking.md], [guide_kestrelford.md]).

Sources retrieved: guide_kestrelford.md, guide_walking.md
```

This is the question I wrote expecting to miss, because no single document
answers both halves of it. The closure year is in the town guide and what the
trackbed became is in the walking guide, and the second one only shows up at
rank 5, which is why `TOP_K` is 5 and not 3.

**My relevance cutoff:** 0.55

I ran all ten questions through `python app.py retrieve` and wrote down the best
distance for each.

| Question | In corpus? | Best distance |
|---|---|---|
| How often do buses run from Brightwater to Kestrelford on Saturdays? | yes | 0.233 |
| How often do Marchwood's trams run on weekdays? | yes | 0.236 |
| Why does the road to Elder Ness flood, and how often does it happen? | yes | 0.281 |
| What happened to Kestrelford's railway line, and what is the old trackbed used for now? | yes | 0.338 |
| How much does it cost to climb the church tower in Kestrelford? | yes | 0.456 |
| What is the capital of Mongolia? | no | 0.810 |
| What is the recommended dosage of ibuprofen for a headache? | no | 0.834 |
| How do I write a for loop in Rust? | no | 0.847 |
| How do I change the oil in a diesel engine? | no | 0.883 |
| Who won the 1994 World Cup? | no | 0.967 |

The two groups are 0.233 to 0.456 and 0.810 to 0.967. The gap is 0.354 wide and
its midpoint is 0.633, which is where the milestone points you.

I put the cutoff at 0.55 instead, lower than the middle, and the reason is a
third group of questions I ran that nobody asked me for. The five out-of-scope
questions are from a different world entirely, and they make the gate look
better than it is. So I asked seven questions that are travel-shaped but about
real places this corpus has never heard of:

| Question | Best distance | Refused at 0.55? |
|---|---|---|
| When is the best season to visit the Lake District? | 0.443 | no |
| Is there parking near the beach in Brighton? | 0.529 | no |
| What time do the buses run in Copenhagen on Sundays? | 0.554 | yes, barely |
| What are the best restaurants in Paris? | 0.578 | yes |
| How do I get from Manchester to Liverpool by train? | 0.658 | yes |
| How much is a ticket to climb the Eiffel Tower? | 0.684 | yes |
| Where can I hire a bike in Amsterdam? | 0.697 | yes |

Those run from 0.443 to 0.697, straight through the middle of my in-corpus
range. No cutoff separates them, because "when is the best season to visit X"
is the same shape as a question this corpus really does answer. Distance
measures shape, not subject.

So 0.55 is a compromise I can defend in both directions. It sits 0.094 above my
hardest real question, which is about twenty percent of headroom, so an
awkwardly worded question I have not thought of still gets answered. It refuses
four of the seven near misses and all five out-of-scope questions. Going to
0.633 would let three more near misses through; going to 0.50 would leave only
0.044 of headroom over a question I know is legitimate, which is thinner than
the difference between two phrasings of the same question.

The three near misses that still get through are the prompt's job, and this is
where the second layer earns its place. I tightened `GROUNDING_INSTRUCTION` in
`generate.py` with three rules, each one for something I had actually seen:
refuse when the question names a place the documents never mention, answer only
the half of a question the documents cover and say which half is missing, and
report a disagreement between documents instead of quietly picking a side. The
first rule is what produces this, on a question that sailed through the gate at
0.443:

```
$ python app.py ask "When is the best season to visit the Lake District?"

  (best distance 0.443, cutoff 0.55)

I don't have enough information about the Lake District, as it is not
mentioned in the documents.
```

And the third rule is what produces this, which is my favourite output the
system makes:

```
$ python app.py ask "Where is the nearest full hospital?"

The documents disagree on the location of the nearest full hospital. According
to guide_accessibility.md, the nearest full hospital is in Marchwood. However,
guide_givens_mill.md, guide_halden_bay.md, guide_kestrelford.md, and
guide_marchwood.md state that the nearest full hospital is in Brightwater.
```

Both files really do say that. Before I added the rule, the system picked one and
sounded certain.

## How I Used AI

**1. I used Claude to read the corpus, then checked what it told me.** Fourteen
documents is more than I wanted to read line by line before deciding on a chunk
size, so I asked it for the exact section headings, the paragraph lengths per
file, and any fact that appeared in more than one document. Two things came back
that I would not have found by skimming: that `## Practical notes` is identical
across nine files, and that one of those copies contradicts
`guide_accessibility.md` about where the nearest hospital is. I did not take
either on trust. I hashed every section with a short script to confirm the nine
were byte-identical, and I opened both files to read the hospital sentences
myself. Both held up, and those two facts are why my chunks carry a breadcrumb
and why criterion 5 is about the source being correct rather than present.

**2. I asked it to write the chunker from my notes, and my own tests caught two
things it got wrong.** The first version looked for the `# Title` line anywhere
in the document, so a file whose first line was ordinary text and which happened
to contain a `#` further down would take that line as its title. My test for it
failed, and the fix was to make the title lookup and the section splitting share
one rule about where a title is allowed to be, instead of each having their own.
The second was a number rather than a bug: it told me the chunker would produce
84 chunks, one per section, and I wrote that into a test. The real figure is 97,
because ten documents have an opening paragraph above the first heading and three
long sections get split by the cap. The test failed, I went and counted, and the
test now pins 97 with the arithmetic written next to it. That is the main thing I
would say about using a model for this: it is fast at reading and it is confident
about numbers it has not run, so the numbers have to come from running the code.

<!-- ── Stretch features ─────────────────────────────────────────────────────
     Doing one? Say so here BEFORE you start. A feature this README never
     claims earns nothing.
     ───────────────────────────────────────────────────────────────────────── -->

---

# Unit 2

<!-- These sections get ADDED to what's already above. Don't delete or rewrite
     unit 1 — the point is that someone can see what you said before you knew
     how it went. -->

## Run Log — Before

<!-- Your five criteria, three runs each. `python run_eval.py --label before`
     runs the questions, puts the OUT_OF_SCOPE ones through the gate, and
     writes it all into results/ for you. Targets come from criteria.md; the
     verdict column is your call.

     Criterion 3 is measured in one deterministic pass rather than three, so
     the same number goes in all three run columns. That's correct, not lazy.

     Milestone 1. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

<!-- Underneath, paste the REAL output for each criterion from one of your
     runs — the actual text your system produced, not a description of it.
     Name the file and function that produced it. -->

## Verdicts

<!-- MET or MISSED for each of the five, against the target you wrote last
     unit — not a new one. Plus a sentence on how you decided. That sentence
     matters most where it was close.

     If your target said 4 of 5 and your runs came out 4, 3, 4, that's a MISS.
     The target has to hold, not show up occasionally.

     Milestone 2. -->

| # | Criterion | Verdict | How I decided |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 |  |  |  |

## Diagnoses

<!-- For each miss: which stage caused it, and how. The stage alone isn't
     enough — you need the mechanism.

     Not a diagnosis: "Question 3 didn't work."
     A diagnosis:     "Question 3 asks about laundry costs. The answer is in
                       one sentence that got split across two chunks, so
                       neither chunk on its own contains it."

     The five stages: loading → chunking → embedding → retrieval → generation.

     Look for a pattern. If three misses all ask about numbers, that's one
     problem, not three.

     Missed nothing? Say so, then say honestly whether your targets were set
     low, and which one you'd tighten and to what.

     Milestone 3. -->

## The Improvement

**What I changed:**

**Why I picked it:**

<!-- Connect it to a specific diagnosis above in one sentence. If you can't,
     you picked a fix because it sounded impressive. -->

### Run Log — After

<!-- Same format, same five criteria, three runs each.
     `python run_eval.py --label after` -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

**Did it help?**

<!-- Say plainly whether it did, and how you know. If it made things worse,
     say that — a change that backfired, honestly reported, earns full credit
     and is more interesting than one that worked. What matters is that you can
     tell.

     Milestone 4. -->

## What's Still Broken

<!-- For each criterion still missed after your fix: what you'd do about it,
     and why you stopped where you did.

     "I ran out of time" is fine if it's true. Pretending nothing is left is
     not.

     Milestone 5. -->

## What I'd Do Differently

<!-- Knowing what you know now — which of your five criteria would you write
     differently, and why?

     Milestone 5. -->
