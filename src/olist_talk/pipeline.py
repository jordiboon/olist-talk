from dataclasses import dataclass, field

import logfire

from . import db, sql, synth, triage

ANSWERED_BY_TRIAGE = {"clarify", "decline", "refuse"}


@dataclass
class Trace:
    question: str
    route: str = ""
    sql: str | None = None
    rows: list | None = None
    answer: str = ""
    quoted_reviews: list[str] = field(default_factory=list)
    error: str | None = None


def answer(question: str) -> Trace:
    with logfire.span("answer", question=question) as span, db.connect() as con:
        with logfire.span("triage"):
            t = triage.triage(question, con)
        span.set_attribute("route", t.route.value)

        trace = Trace(question=question, route=t.route.value, answer=t.reply)
        if t.route.value in ANSWERED_BY_TRIAGE:
            return trace

        if t.route.value != "sql":
            trace.error = f"{t.route.value} path not built yet"
            return trace

        try:
            with logfire.span("sql") as sql_span:
                result = sql.run(question, con)
                sql_span.set_attribute("attempts", result.attempts)
                sql_span.set_attribute("sql", result.sql)
                sql_span.set_attribute("row_count", len(result.rows))
        except Exception as e:
            trace.error = f"{type(e).__name__}: {e}"
            return trace

        trace.sql = result.sql
        trace.rows = result.rows
        with logfire.span("synthesise"):
            trace.answer = synth.explain(question, result)
        return trace
