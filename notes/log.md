# Build log — olist-talk

A running lab notebook: decisions, tradeoffs, and things that surprised me.
Kept live while building, not reconstructed afterwards.

---

## How I'm working

- **Tooling:** Claude Code (Opus) in the desktop app, one long session per work block.
- **Mode:** guided, not generated. I make the design decisions and review every diff
  before it lands. The assistant explains, drafts, and pokes holes; I stay the owner
  of the code. The point is being able to defend any line of it.
- **Gate:** the eval set (see below) decides whether a change was actually correct,
  not whether it looked right.
- **Context management:** notes live in this file rather than in chat history, so a
  fresh session can be brought up to speed by reading the repo.

---

## 2026-09-20 — Decision: build the take-home, not present existing work

Two options were offered for the second interview: present a project from my current
work, or build the "talk with your data" assessment.

Chose the assessment. It produces a fresh artifact I own end to end, which is what an
evaluation centred on process and code mastery actually probes. A work project would
have carried more seniority signal, but I can only talk about it from the outside —
here I can open any file and explain it.

**Tradeoff accepted:** less "real stakeholders" weight, more depth of ownership.

---

## 2026-09-20 — Decision: eval-driven development as the new practice

The assignment asks for at least one technique I haven't used before. Picked
eval-driven development: write the eval set *before* the app works, then build until
it goes green.

Why this one:
- It forces "what is correct?" to be answered up front — including what the app should
  *refuse* or *ask back*, which is otherwise an afterthought.
- It gives a number that moves, instead of a demo that happens to work.
- It directly covers the requirement to handle ambiguous and broken questions.

**Tradeoff accepted:** slower to a first working demo. No answers at all until the
plumbing exists, and time goes into test design before feature work.

*(to fill in after: what eval-driven actually felt like vs. what I expected)*

---

## 2026-09-20 — Decision: framing the app as a CX analyst, not a SQL box

The interesting signal in the Olist data is that review scores track delivery lateness,
and the free-text reviews say *why*. So the app answers "why are customers unhappy?"
rather than being a generic natural-language SQL front end.

Consequences:
- Uses the three required tables (`orders`, `order_reviews`, `customers`) naturally.
- Makes hybrid SQL + semantic search over review text integral to the story rather
  than a bolted-on bonus: numbers come from SQL, reasons come from the review text.
- Narrows scope, which is the point — 4-8 hours.

**Tradeoff accepted:** the app is deliberately worse at questions outside the
customer-experience story. That is a design choice, and it should be visible in how
the app declines them.

---

## 2026-09-20 — Decision: DuckDB as storage

Single file, reads the CSVs directly, no server to run, fast enough that the whole
dataset is queryable interactively.

Alternative considered: Postgres + pgvector, which I have used before. Rejected for
setup cost, and because "new tool" was worth spending here.

**Open question:** dropping pgvector means the semantic-search half needs another
approach for embeddings — DuckDB VSS extension, or just an in-memory index given the
corpus is ~40k non-empty review comments. To decide when I get there.

Also pinned Python 3.12 rather than the system 3.14, since torch / sentence-transformers
wheels lag behind the newest release and the semantic half may need them.

---

## 2026-09-20 — Finding: the review CSV lies about its row count

`wc -l` reports 104,719 lines in `olist_order_reviews_dataset.csv`, but DuckDB parses
99,224 rows. The difference is 5,495 lines that are continuations inside quoted
`review_comment_message` fields — customers pressed enter while writing reviews.

Why it matters: a naive line-based loader silently corrupts ~5% of the review text,
and the review text is exactly the corpus the semantic-search half depends on. Found it
by checking the row count against the known dataset size instead of assuming.

DuckDB's CSV reader handles it correctly out of the box.

---

## Open questions

- Embedding/vector approach for the review text (see DuckDB entry).
- How the app should distinguish "ambiguous, ask back" from "out of scope, decline" —
  needs to be defined as expected behaviour in the eval set, not discovered later.
- Whether to model the data as views over the CSVs or materialise typed tables.

## Next

- Write the ten eval questions against the real column names.
- Load the data into DuckDB.
- Minimal question -> SQL -> answer loop, run red to green against the evals.
