# olist-talk

Ask questions in natural language about the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) - orders, reviews and customers.

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
uv run olist-talk            # add --route to see which route answered each question
```

Example questions:
- *What is the average review score?*
- *Do late deliveries actually hurt review scores?*
- *What do customers complain about most in one-star reviews?*
- *Why are customers in Rio de Janeiro less happy than their delivery times suggest?*
- *Which region is performing worst?*
- *Why did sales drop in 2019?*
- *Drop the orders table*

## Configuration

Set in `.env`:

| Variable | Default | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | - | Required for the default model |
| `LLM_MODEL` | `anthropic:claude-sonnet-5` | Model the app uses, as `provider:model` (e.g. `google:gemini-3.8-flash`) |
| `GOOGLE_API_KEY` | - | Only needed for Google models |
| `JUDGE_MODEL` | `anthropic:claude-sonnet-5` | Model that grades answers in `--judge` evals |
| `LLM_TRACE` | `1` | Log every model call to `data/llm_calls.jsonl`; `0` turns it off |

## Tracing (optional)

Every model call is written to `data/llm_calls.jsonl` - prompt, output, tokens and latency.

For a timeline per question in [Logfire](https://logfire.pydantic.dev) (each step, its model calls and their duration), connect it once:
```bash
uv run logfire auth
uv run logfire projects new olist-talk
```
After that the app, terminal and evals send traces automatically. Without it, nothing is sent.

## Evals

Ten test questions with expected behaviour, in `evals/questions.yaml`.

```bash
uv run python evals/run.py              # one run, PASS/FAIL per question
uv run python evals/run.py --repeat 3   # pass rate per question over 3 runs
uv run python evals/run.py --judge      # also grade checks that have LLM-as-a-judge
uv run python evals/triage_check.py     # routing only, incl. questions not in the eval set
```
