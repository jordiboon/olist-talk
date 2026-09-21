from . import llm, sql

SYSTEM = """You explain the result of a database query to the person who asked.

- Answer the question directly, in two to four sentences. No preamble, no restating the
  question.
- Use only numbers that appear in the rows. Never estimate, extrapolate, or introduce a
  figure that is not there.
- If the query's assumptions change how the answer should be read, say so plainly.
- If a result rests on few rows, say how many."""


def rows_as_text(result: sql.Result) -> str:
    header = " | ".join(result.columns)
    body = "\n".join(" | ".join(str(v) for v in row) for row in result.rows)
    return f"{header}\n{body}"


def explain(question: str, result: sql.Result) -> str:
    user = (
        f"Question: {question}\n\n"
        f"SQL:\n{result.sql}\n\n"
        f"Assumptions: {result.assumptions}\n\n"
        f"Rows ({len(result.rows)}):\n{rows_as_text(result)}"
    )
    return llm.text(SYSTEM, user)
