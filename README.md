# The Unofficial Guide

Parshv Patel. Corpus: `city_guides`.

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

The `## Practical notes` section is byte-for-byte identical
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
its midpoint is 0.633.

I put the cutoff at 0.55 instead, lower than the middle, and the reason is a
third group of questions. The five out-of-scope
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

**3. In unit 2 I used it to argue against my own verdict.** I had criterion 5
at 4 of 5 and I wanted to call it met, because the citation is arguably
correct. I pasted the criterion, the target, the three runs and my reasoning in
and asked it to argue the opposite verdict as hard as it could. The argument
for "met" was decent — the second file really does state the fact — but it also
made the weakness obvious, which is that I was about to reinterpret a criterion
after seeing the result. So the verdict stayed MISSED and the reinterpretation
became a revision written underneath the original, where a reader can see both.

**4. It talked me out of the fix I was going to pick.** I was going to add
hybrid BM25 search, because it is the headline option on the menu and it sounds
like the sort of thing that fixes retrieval. I asked it to tell me why that
might not work, and the useful answer was to go and measure first. BM25 scores
the Lake District question at 13.90 and my real Marchwood trams question at
10.93, so it ranks a question about the wrong country higher than one the
corpus answers. That took ten minutes and saved me from a fix with a good story
and no effect.

## Stretch Features

**1. Metadata filtering.** Narrow retrieval to one town, one kind of section, or
one file, so `ask "where do I eat" --place kestrelford` searches nine chunks
instead of 97.

**2. Conversational memory.** Let a follow-up question like "how about on
Sundays?" resolve against the question before it, instead of being embedded as
if it arrived out of nowhere.

## Stretch Features in Detail

### 1. Metadata filtering

**What it does.** `ask` and `retrieve` take `--place`, `--section` and
`--source`, which narrow retrieval before any distance is measured.
`python app.py facets` lists every value they accept, read back out of the
index rather than out of the corpus folder, so the list is always what is
really searchable.

```
python app.py ask "where do I eat" --place kestrelford
python app.py retrieve "when should I visit" --section when_to_go
python app.py ask "what should I know" --source guide_halden_bay.md
```

**Why this feature and not another.** It fixes a problem I had already
measured and written into criterion 5. The `## Practical notes` section is
byte-identical in nine files, so ask about it unfiltered and this is what
comes back:

```
$ python app.py retrieve "what are the practical notes" --top-k 3

1   0.5521     guide_kestrelford.md    Kestrelford: Practical notes  Cash is still useful a...
2   0.5527     guide_corry_vale.md     Corry Vale: Practical notes  Cash is still useful at...
3   0.5598     guide_givens_mill.md    Givens Mill: Practical notes  Cash is still useful a...
```

Six ten-thousandths of a distance separate first place from second. That
ordering is noise, and whichever file wins gets cited. With a filter the
question has one possible answer:

```
$ python app.py retrieve "what are the practical notes" --place kestrelford --top-k 3

1   0.5521     guide_kestrelford.md    Kestrelford: Practical notes  Cash is still useful a...
2   0.9001     guide_kestrelford.md    Kestrelford: What to see  The market square on a Sat...
3   0.9486     guide_kestrelford.md    Kestrelford: Getting around  Everything is within a ...
```

**How it works.** `chunker.py::section_split` already knew the title and the
heading of every chunk, so I gave `Chunk` two fields to carry them and
`store.py::build_index` writes them into the vector store as metadata, both as
written and as a slug (`Elder Ness` becomes `elder_ness`). Chroma's `where`
clause is exact-match only, with no substring matching and no case folding, so
normalising at write time is what makes a command line flag usable at all.
`store.py::build_where` turns the flags into the clause Chroma wants, which is
a bare `{"key": value}` for one condition and an explicit `{"$and": [...]}` for
several.

A filter that matches nothing raises
`NoMatchingChunks` instead of returning an empty list. An empty list would
travel down the pipeline, hit the relevance gate, and come back as "I don't
have enough information about that", which tells the reader their question is
unanswerable when the truth is that they mistyped a town. Those two outcomes
mean opposite things and they should not look the same:

```
$ python app.py ask "where do I eat" --place kestrelfrd

No chunks match the filter {'place': 'kestrelfrd'}.
Available places:   brightwater, corry_vale, eating_across_the_region, elder_ness, ...
```

**What it costs.** The slug for a thematic guide is ugly:
`--place getting_around_the_region_with_limited_mobility` is nobody's idea of a
command. Prefix matching would fix that and would also make `--place kestrel`
work, at the price of an ambiguous prefix quietly picking a town for you. I
left it exact, because a filter that guesses is worse than a filter that makes
you type, and `app.py facets` means you never have to remember a value.

### 2. Conversational memory

**What it does.** In the interactive loop (`python app.py ask` with no
question), a follow-up resolves against the question before it. `/reset`
forgets the conversation and `--no-memory` turns the whole thing off.

**The evidence.** Same two questions, memory off and memory on:

```
$ python app.py ask --no-memory
> How often do buses run from Brightwater to Kestrelford on Saturdays?
  (best distance 0.233, cutoff 0.55)
Buses run from Brightwater to Kestrelford every two hours on Saturdays
(guide_kestrelford.md and guide_regional_transport.md).

> how about on Sundays?
  (best distance 0.567, cutoff 0.55)
I don't have enough information about that.
```

```
$ python app.py ask
> How often do buses run from Brightwater to Kestrelford on Saturdays?
  (best distance 0.233, cutoff 0.55)
Buses run from Brightwater to Kestrelford every two hours on Saturdays
(guide_kestrelford.md and guide_regional_transport.md).

> how about on Sundays?
  (memory: read as a follow-up (starts with 'how about'); retrieving on:
   'How often do buses run from Brightwater to Kestrelford on Saturdays? how about on Sundays?')
  (best distance 0.223, cutoff 0.55)
Buses from Brightwater to Kestrelford do not run at all on Sundays
(guide_regional_transport.md and guide_kestrelford.md).
```

Without memory the follow-up scores 0.567, lands the wrong side of my 0.55
cutoff, and gets refused. With memory it scores 0.223 and the answer is right.

**The design decision.** The previous question is folded into the text used for
**retrieval only**. The question put to the model is still the one that was
typed, and the earlier turns go into the prompt separately, under a line that
says they are context and not a document that may be cited. Rewriting the
question itself would have been simpler, but then the answer would be answering
something the reader never asked, and there would be no honest way to check it
against what was on screen. What retrieval needs and what the model needs are
different things, so they are built separately.

**Why a rule rather than a model call.** The obvious implementation is to ask
the model to rewrite the follow-up into a standalone question. I did not, for
two reasons. It would add an API call per turn on a rate-limited free tier,
doubling the cost of a conversation. And it would make retrieval
non-deterministic, so the same two questions could retrieve differently on
different days, which makes every measurement in this README softer. The rule
in `conversation.py::looks_like_follow_up` is deterministic, free, and
unit-tested: a question counts as a follow-up if it opens with a phrase like
"how about", or if it is ten words or fewer and contains a referring word like
"it" or "that".

**What it costs, honestly.** The rule is deliberately conservative, because a
false positive is worse than a false negative here. Treating a fresh question
as a follow-up drags the old subject into retrieval and can answer the wrong
question entirely; treating a follow-up as fresh only gives you what you would
have had without the feature. So a follow-up phrased as a full sentence, like
"and what does the same journey cost on a weekday morning in winter", is
treated as new. Memory also holds three turns and no more, which means a
reference back to something four questions ago is lost. Both are things I would
measure before changing, not guess at.

### Tests

```
python -m unittest test_chunker test_stretch test_gate test_scorer
# 103 tests, offline, no API calls
```

`test_gate.py` and `test_scorer.py` were added in unit 2: the first covers the
unknown-name check, including its capitalisation blind spot, written as a test
so it cannot be forgotten; the second covers the scorer every verdict in this
README rests on, including the paraphrase case that produced the criterion 5
miss.

`test_stretch.py` covers both features: slugs, the `where` clause shapes, the
chunk metadata they depend on, filtered search against the real index, the
loud failure on a filter that matches nothing, follow-up detection in both
directions, the three-turn window, and the fact that history goes into the
prompt labelled as context rather than as a source. The filtering tests skip
themselves with a clear message if no index has been built yet.


---

# Unit 2

## What I'm Claiming This Unit

**Extra credit: a second improvement.** Claimed before building it, as the
brief asks. The required improvement is a change to the relevance gate; the
second is a change to the grounding prompt. Each one is measured on its own
run, so the two are never mixed together in the same set of numbers.

No new features this unit. Metadata filtering and conversational memory were
unit 1's stretch options and stay where they are.

## Run Log — Before

`python run_eval.py --label before`. Five questions, three runs each, caching
off, 15 real model calls. Raw log:
`results/run_2026-09-23_1744_before.md`. Per-run scorecards:
`results/scorecard_before.jsonl`, written by `scorer.py::judge`.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 2. Every answer names a source | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 4. Every chunk 150–600 chars, whole sentences | all chunks | 97/97 | 97/97 | 97/97 | MET |
| 5. Cited file contains the fact | 5 of 5 | 4/5 | 4/5 | 4/5 | MISSED |

Criteria 3 and 4 are the same in all three columns and that is correct rather
than lazy. Criterion 3 is a deterministic pass over `OUT_OF_SCOPE` by
`run_eval.py::check_out_of_scope`, and criterion 4 is a property of the index,
measured once by `scorer.py::chunk_shape` from
`chunker.py::section_split`. Neither involves the model, so neither can vary.

### Real output

**Criterion 1** — the answer-bearing chunk was retrieved for all five
questions, judged by `scorer.py::retrieved_contains_answer`, which checks the
chunk text rather than the answer text. Question 5, retrieved by
`store.py::search` from chunks made by `chunker.py::section_split`:

```
Q: What happened to Kestrelford's railway line, and what is the old trackbed used for now?
   best distance 0.338 | sources: guide_kestrelford.md, guide_walking.md

Kestrelford's railway line was closed in 1963 (guide_kestrelford.md,
guide_walking.md). The old trackbed is now used as a walking route
(guide_kestrelford.md), specifically following the closed railway line for six
miles to the next village, providing the best walking in the region for the
effort involved (guide_walking.md).
```

**Criterion 2** — every answer named at least one file, in all 15 runs.
Produced by `generate.py::answer_from_chunks`:

```
Marchwood's trams run every 8 minutes on weekdays (guide_marchwood.md).
```

**Criterion 3** — `run_eval.py::check_out_of_scope`, cutoff 0.55:

```
refused  (best distance 0.810)  What is the capital of Mongolia?
refused  (best distance 0.883)  How do I change the oil in a diesel engine?
refused  (best distance 0.967)  Who won the 1994 World Cup?
refused  (best distance 0.834)  What is the recommended dosage of ibuprofen for a headache?
refused  (best distance 0.847)  How do I write a for loop in Rust?
  -> gate refused 5 of 5
```

**Criterion 4** — `scorer.py::chunk_shape` over `chunker.py::split_documents`:

```
count 97 | min 152 | max 565 | mean 310
too_short: []   too_long: []   starts_mid_sentence: []   ends_mid_sentence: []
passes: True
```

**Criterion 5** — the miss, identical on all three runs. Produced by
`generate.py::answer_from_chunks`, judged by `scorer.py::citation_check`:

```
Q: How often do buses run from Brightwater to Kestrelford on Saturdays?

Buses run from Brightwater to Kestrelford every two hours on Saturdays
(guide_kestrelford.md and guide_regional_transport.md).

  cited:      guide_kestrelford.md, guide_regional_transport.md
  supporting: guide_kestrelford.md
  strict: False
```

`guide_kestrelford.md` says "every two hours on Saturdays".
`guide_regional_transport.md` says "two-hourly on Saturdays". Same fact,
different words. Open the second file looking for the sentence the answer gave
and you will not find it.

## Verdicts

| # | Criterion | Verdict | How I decided |
|---|---|---|---|
| 1 | Retrieved chunk contains the answer | **MET** | Target was 4 of 5. All three runs came out 5 of 5, and the answer-bearing chunk was at rank 1 or 2 every time. Not close. |
| 2 | Every answer names a source | **MET** | Target was 5 of 5 and all 15 answers named a file. I counted filenames with a regex rather than by eye, so the number is the same however many times I read it. |
| 3 | Gate stops out-of-corpus questions | **MET** | Target was 4 of 5 and the gate refused 5 of 5, every question at 0.810 or worse against a 0.55 cutoff. Met, and too easily — see the diagnoses. |
| 4 | Every chunk 150–600 chars, whole sentences | **MET** | 97 of 97 chunks inside the range, none starting or ending mid-sentence. Deterministic, and `test_chunker.py` asserts the same numbers, so it cannot drift without a test failing. |
| 5 | Cited file contains the fact | **MISSED** | Target was 5 of 5 and every run gave 4 of 5. The miss is the same question each time. I thought hard about calling this met, because the citation is arguably correct — the second file does state the fact, in different words. But the criterion I wrote says the file contains the fact being stated, and a reader checking it would not find that sentence. Rewriting the target so it passes is the exact move the brief warns about, so the number stands. |

## Diagnoses

### Criterion 5, the one miss

**Stage: generation, with a measurement problem sitting on top of it.**

The mechanism: `generate.py::build_prompt` hands the model five chunks, two of
which answer the question. The model states the fact in the wording of the
first file and then attaches both filenames to it, because both chunks support
what it said. `scorer.py::citation_check` asks whether each cited file contains
the fact as stated, and `guide_regional_transport.md` does not — it says
"two-hourly" where the answer says "every two hours".

So there are two readings, and they matter differently:

- **The system's behaviour is defensible.** Citing a second file that
  corroborates the fact is more useful than citing one, not less.
- **My criterion is not measurable as written.** "The file contains the fact"
  and "the file supports the fact" are different tests, and a substring check
  can only perform the first one. I did not notice the difference when I wrote
  the criterion, because I was thinking about a citation pointing at the wrong
  town, not about two files agreeing in different words.

That is a measurement revision, which is why criteria.md now carries a revised
line underneath the original. The verdict for this unit is still MISSED,
because the target I set was 5 of 5 and I got 4 of 5 three times.

### The pattern: four criteria that were too safe

Four of five passed on the first attempt and never wobbled. That usually means
the targets were comfortable rather than the system being excellent, and I
think that is what happened here.

The clearest case is criterion 3. The five `OUT_OF_SCOPE` questions are about
Mongolia, diesel engines, the World Cup, ibuprofen and Rust, and every one of
them lands at 0.810 or worse against a 0.55 cutoff. There is no version of this
system that fails that test. Meanwhile I already had evidence, written into the
unit 1 README, that the gate leaks badly on a class of question the test never
tries: travel-shaped questions about real places the corpus has never heard of.

I added those seven questions to `questions.py` as `NEAR_MISS` and put them
through the same gate. Before any change this unit:

```
run_eval.py::check_near_miss, cutoff 0.55 — refused 0 of 7

When is the best season to visit the Lake District?      0.443  let through
Is there parking near the beach in Brighton?             0.529  let through
What time do the buses run in Copenhagen on Sundays?     0.554  let through
What are the best restaurants in Paris?                  0.578  let through
How do I get from Manchester to Liverpool by train?      0.658  let through
How much is a ticket to climb the Eiffel Tower?          0.684  let through
Where can I hire a bike in Amsterdam?                    0.697  let through
```

**Stage: retrieval, and the gate that reads it.** The mechanism is not a bug in
anything. Cosine distance measures how alike two pieces of text are in shape
and topic. "When is the best season to visit X" has the same shape whatever X
is, and the place name is one token in ten, so it barely moves the vector. No
cutoff separates 0.443 from my real questions at 0.233 to 0.456, because the
signal the cutoff reads does not contain the distinction. That is what
criterion 3 should have been testing, and the improvement below is aimed at it.

## The Improvement

### Improvement 1: refuse questions that name a place the corpus never mentions

**What I changed.** `gate.py::check` now runs a second check, first, which does
not look at distance at all. `gate.py::unknown_names` pulls the capitalised
words out of the question, skips the first word and the obvious question words,
and refuses if any of them appear nowhere in the corpus text.
`gate.py::corpus_vocabulary` builds that word set once and caches it.

**Why I picked it.** The diagnosis says the distance signal cannot tell subject
from shape, so I added a signal that can: a place name the corpus has never
heard of is a fact about the question, not about the vector.

**What I tried first and rejected, with numbers.** The menu's headline option
is hybrid search, so I prototyped BM25 over the 97 chunks before proposing
anything. It scores the Lake District question at 13.90 and my real Marchwood
trams question at 10.93 — it ranks a question about the wrong country *above* a
question the corpus answers, because both are full of generic words like
"buses" and "visit". It would not have fixed this. I also tried the obvious
broader rule, flagging any word in the question that is absent from the corpus,
and it refuses three of my own five test questions, because "trams", "cost" and
"flood" do not appear in those exact word forms. Both measurements are why the
rule is as narrow as it is.

**Result.**

| Measure | Before | After improvement 1 |
|---|---|---|
| Near-miss questions refused (`NEAR_MISS`, 7) | 0 of 7 | **7 of 7** |
| Out-of-scope questions refused (`OUT_OF_SCOPE`, 5) | 5 of 5 | 5 of 5 |
| Test questions falsely refused (of 15 runs) | 0 | **0** |
| Criteria 1, 2, 4, 5 | 5/5, 5/5, pass, 4/5 | unchanged |

Real output, `run_eval.py::check_near_miss`:

```
refused  (best distance 0.443, unknown name)  When is the best season to visit the Lake District?
refused  (best distance 0.529, unknown name)  Is there parking near the beach in Brighton?
refused  (best distance 0.554, unknown name)  What time do the buses run in Copenhagen on Sundays?
  -> gate refused 7 of 7
```

**Did it help?** Yes, and the part I care about most is the row that did not
move. A gate that refuses more is easy to build and worthless if it also
refuses real questions. Three runs of five questions produced zero false
refusals, and criteria 1 and 2 stayed at 5 of 5, so the extra refusals came out
of the right pile.

### Improvement 2 (extra credit): tell the model to cite what it quoted

**What I changed.** One rule added to `GROUNDING_INSTRUCTION` in
`generate.py`: cite the document whose wording you actually used, and if a
second document says the same thing in different words, mention it separately
rather than attaching its name to that fact.

**Why I picked it.** It is aimed straight at the only miss. Criterion 5 came
out 4 of 5 three times, always on question 1, always because two filenames were
attached to one sentence and only one of them contains that sentence.

**Result: it did not work.**

| Criterion | Target | Before | After improvement 2 |
|---|---|---|---|
| 5. Cited file contains the fact | 5 of 5 | 4/5, 4/5, 4/5 | **4/5, 4/5, 4/5** |

All three runs after the change still attach both files:

```
run 1: Buses run from Brightwater to Kestrelford every two hours on Saturdays
       (guide_kestrelford.md and guide_regional_transport.md).
run 2: Buses run from Brightwater to Kestrelford every two hours on Saturdays
       (*guide_kestrelford.md* / *guide_regional_transport.md*).
run 3: Buses run from Brightwater to Kestrelford every two hours on Saturdays
       (guide_kestrelford.md and guide_regional_transport.md).
```

**Did it help? No.** The number did not move on any run, and the only thing
that changed was the punctuation the model used between the two filenames.

I think the reason is the same one that made the relevance gate necessary in
the first place. Asking the model politely to behave a certain way works most
of the time and fails quietly the rest of it, and this is a case where the
model's own judgment — both files support this, so cite both — is reasonable
enough that an instruction does not override it. The fix that would actually
work is the one that does not ask: have the model return each fact with the
single file it came from as structured output, then check in code that the
quoted wording appears in that file before printing the citation. That is code
deciding rather than a prompt requesting, which is the lesson the gate already
taught me and which I clearly had not finished learning.

## Run Log — After

Both improvements in place. `python run_eval.py --label after-both`, same five
questions, three runs each, caching off. Raw log:
`results/run_2026-09-24_0053_after-both.md`. Scorecards:
`results/scorecard_after-both.jsonl`. The gate-only run is also committed, as
`results/run_2026-09-24_0052_after-gate.md`, so the two changes can be told
apart.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 2. Every answer names a source | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 3b. Gate stops near-miss questions (added this unit, not part of the original target) | — | 7/7 | 7/7 | 7/7 | — |
| 4. Every chunk 150–600 chars, whole sentences | all chunks | 97/97 | 97/97 | 97/97 | MET |
| 5. Cited file contains the fact | 5 of 5 | 4/5 | 4/5 | 4/5 | MISSED |

Row 3b is the new evidence, not a new target. Criterion 3's target stays where
I wrote it in unit 1.

## What's Still Broken

**Criterion 5 is still missed, 4 of 5.** What I would do: stop asking the model
to cite carefully and make the citation checkable in code. Have generation
return facts and filenames as structured output, verify that the quoted wording
appears in the named file, and drop or re-label a citation that fails the
check. I stopped short of building that this unit because it changes the shape
of what `generate.py` returns, and the brief asks for one change measured
properly rather than a rewrite measured vaguely. The prompt attempt was the
cheap version, it failed, and the failure is the useful part.

**The gate's name check is capitalisation-dependent.** "is there parking in
brighton?" typed in lower case still gets through, and
`test_gate.py::KnownBlindSpot` asserts exactly that so nobody discovers it by
accident. The obvious fix, ignoring capitalisation, refuses three of my own
five questions, so it is worse than the disease. What I would try next is a
frequency-based version: flag a word that is absent from the corpus *and* rare
in ordinary English, which would catch "brighton" without catching "trams". I
stopped because that needs a word-frequency list I do not have offline and a
false-refusal measurement bigger than five questions.

**I have not tested the near-miss set for false refusals at scale.** Seven
near-miss questions and nine in-corpus probes is enough to show the rule works
and nowhere near enough to know its error rate. A question about a person's
name, a business name, or a street the corpus does not happen to mention would
be refused even when the corpus could answer the rest of it. I would want
thirty in-corpus questions with proper nouns in them before I trusted the rule
outside this test set.

## What I'd Do Differently

**Criterion 5 is the one I would rewrite.** It says the cited file must contain
the fact being stated, and I meant it to catch a citation pointing at the wrong
town. What it actually catches is two files agreeing in different words, which
is good behaviour being marked wrong. I would write it as: *for each of my five
questions, every file the answer cites contains a sentence that supports the
fact, and none contradicts it* — and I would decide up front how a paraphrase
is judged, because that is the part that made it unmeasurable.

**Criterion 3 is the one I would tighten.** A target of 4 of 5 against five
questions from a different world entirely cannot fail. It should be measured
against questions that are the same shape as real ones, which is what
`NEAR_MISS` is for. Next time I would write it as: *at least 6 of 7
travel-shaped questions about places the corpus does not cover are refused,
and 5 of 5 of the obvious out-of-scope ones*. That is a target the system could
plausibly miss, which is the whole point of writing one.

**And I would stop writing criteria that only a passing system can produce
evidence for.** Criteria 1, 2 and 4 all passed three times without moving. They
are not useless, since they would catch a regression, but not one of them told
me anything I did not already know. The two criteria that taught me something
were the one I missed and the one I discovered was too easy.

