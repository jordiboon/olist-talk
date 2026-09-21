from dataclasses import dataclass

import duckdb
from pydantic import BaseModel

from . import db, llm

MAX_ROWS = 200
MAX_ATTEMPTS = 3


class Query(BaseModel):
    sql: str
    assumptions: str


@dataclass
class Result:
    sql: str
    columns: list[str]
    rows: list[tuple]
    assumptions: str
    attempts: int


class UnsafeSQL(Exception):
    pass


SYSTEM = """You write DuckDB SQL to answer questions about a Brazilian e-commerce dataset.

Rules:
- Exactly one statement, and it must be a SELECT (a leading WITH is fine).
- Never write DDL or DML. The connection is read-only and will reject it anyway.
- Use only the tables and columns in the schema below. If the question needs something
  that is not there, write the closest honest query rather than inventing a column.
- When you rank or compare groups, include the row count per group in the output, so the
  answer can say whether a result rests on enough data.
- Prefer returning a few summary rows over thousands of detail rows.

`assumptions` records the choices you made that a reader would want to know: which rows
you counted, how you defined a derived measure, anything you excluded. One or two
sentences, plain language. Write "none" if there were no real choices to make.

Schema:
{schema}

Facts about the data:
{facts}"""


def validate(sql: str) -> None:
    statements = duckdb.extract_statements(sql)
    if len(statements) != 1:
        raise UnsafeSQL(f"expected one statement, got {len(statements)}")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise UnsafeSQL(f"expected a SELECT, got {statements[0].type.name}")


def run(question: str, con: duckdb.DuckDBPyConnection) -> Result:
    system = SYSTEM.format(schema=db.schema_text(con), facts=db.data_facts(con))
    prompt = question
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        query = llm.structured(system, prompt, Query, max_tokens=2048)
        try:
            validate(query.sql)
            cursor = con.execute(query.sql)
            rows = cursor.fetchmany(MAX_ROWS)
            columns = [d[0] for d in cursor.description or []]
            return Result(query.sql, columns, rows, query.assumptions, attempt)
        except Exception as e:
            last_error = e
            prompt = (
                f"{question}\n\nYour previous SQL failed.\n"
                f"SQL:\n{query.sql}\n\nError: {type(e).__name__}: {e}\n\n"
                "Write a corrected query."
            )

    raise RuntimeError(f"no valid SQL after {MAX_ATTEMPTS} attempts: {last_error}")
