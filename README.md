# olist-talk

Ask questions in natural language about the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) - orders, reviews and customers. Numbers come from SQL, reasons come from the review text, and questions the data can't answer get a clarifying question or an explanation instead of a guess.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

1. **Download the data** from Kaggle and unzip the CSVs into `data/raw/`.
2. **Add API keys** - copy `.env.example` to `.env` and fill in at least `ANTHROPIC_API_KEY`.
3. **Build the database:**
   ```bash
   uv run python -m olist_talk.db
   ```
   The first build takes about 5 minutes: it downloads a small embedding model (220 MB) and embeds the review texts once. Later builds take under a second.

## Ask questions

**Chat page** (opens at http://localhost:8501):
```bash
uv run streamlit run app.py
```

**Terminal:**
```bash
uv run olist-talk
```

Things to try:
- *What is the average review score?*
- *Do late deliveries actually hurt review scores?*
- *What do customers complain about most in one-star reviews?*
- *Why are customers in Rio de Janeiro less happy than their delivery times suggest?*
- *Which region is performing worst?* - asks back what "worst" means
- *Why did sales drop in 2019?* - the data ends in October 2018
- *Drop the orders table* - refused; the database is read-only

A number question takes a few seconds; one that also searches the reviews takes 30-40 seconds. Each question costs under a cent.

## Configuration

Set in `.env`:

| Variable | Default | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | - | Required for the default model |
| `LLM_MODEL` | `anthropic:claude-sonnet-5` | Model the app uses, as `provider:model` (e.g. `google:gemini-3.8-flash`) |
| `GOOGLE_API_KEY` | - | Only needed for Google models |
| `JUDGE_MODEL` | `anthropic:claude-sonnet-5` | Model that grades answers in `--judge` evals |
| `LLM_TRACE` | `1` | Log every model call to `data/llm_calls.jsonl`; `0` turns it off |

## Evals

Ten test questions with expected behaviour, in `evals/questions.yaml`.

```bash
uv run python evals/run.py              # one run, PASS/FAIL per question
uv run python evals/run.py --repeat 3   # pass rate per question over 3 runs
uv run python evals/run.py --judge      # also grade the two checks that need judgement
uv run python evals/triage_check.py     # routing only, incl. questions not in the eval set
```
