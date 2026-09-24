from . import llm, search, sql

SYSTEM = """You answer a question about a Brazilian e-commerce marketplace from the evidence \
given: query results, customer reviews, or both.

- Answer directly, in a short paragraph or a few bullets. No preamble.
- Numbers: use only numbers that appear in the query rows. Never estimate, extrapolate,
  or introduce a figure that is not there. Write rates and shares as percentages
  (12.2%, not 0.122).
- Reviews are a sample retrieved *because they are relevant*, not a random sample. Never
  turn them into counts or percentages ("most customers say", "60% complain"). Describe
  recurring themes, and say they come from the retrieved reviews.
- When reviews are given, quote two to four of them verbatim in the original Portuguese,
  each followed by a translation in brackets.
- If the query's assumptions change how the answer should be read, say so plainly.
- If a result rests on few rows, say how many."""


def rows_as_text(result: sql.Result) -> str:
    header = " | ".join(result.columns)
    body = "\n".join(" | ".join(str(v) for v in row) for row in result.rows)
    return f"{header}\n{body}"


def explain(
    question: str,
    result: sql.Result | None = None,
    reviews: list[search.Review] | None = None,
    language: str = "English",
) -> str:
    parts = [f"Question: {question}"]
    if result:
        parts.append(
            f"SQL:\n{result.sql}\n\nAssumptions: {result.assumptions}\n\n"
            f"Rows ({len(result.rows)}):\n{rows_as_text(result)}"
        )
    if reviews:
        listed = "\n".join(f"- [{r.score} stars, {r.state}] {r.text}" for r in reviews)
        parts.append(f"Retrieved reviews, most relevant first ({len(reviews)}):\n{listed}")
    parts.append(f"Write the entire answer, including the translations, in {language}.")
    return llm.text(SYSTEM, "\n\n".join(parts))
