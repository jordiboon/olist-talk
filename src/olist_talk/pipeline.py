from dataclasses import dataclass, field

import logfire

from . import db, search, sql, synth, triage

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


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def quoted(answer: str, reviews: list[search.Review]) -> list[str]:
    """Reviews whose text actually appears in the answer - not merely retrieved."""
    a = _norm(answer)
    return [r.text for r in reviews if _norm(r.text)[:30] in a]


def answer(question: str) -> Trace:
    with logfire.span("answer", question=question) as span, db.connect() as con:
        try:
            with logfire.span("triage"):
                t = triage.triage(question, con)
        except Exception as e:
            return Trace(question=question, error=f"{type(e).__name__}: {e}")
        route = t.route.value
        span.set_attribute("route", route)

        trace = Trace(question=question, route=route, answer=t.reply)
        if route in ANSWERED_BY_TRIAGE:
            return trace

        result = found = None
        try:
            if route in ("sql", "hybrid"):
                with logfire.span("sql") as s:
                    result = sql.run(question, con)
                    s.set_attribute("attempts", result.attempts)
                    s.set_attribute("sql", result.sql)
                    s.set_attribute("row_count", len(result.rows))
                trace.sql, trace.rows = result.sql, result.rows
            if route in ("semantic", "hybrid"):
                with logfire.span("search") as s:
                    found = search.run(question, con)
                    s.set_attribute("request", found.request.model_dump())
                    s.set_attribute("hits", len(found.reviews))
        except Exception as e:
            trace.error = f"{type(e).__name__}: {e}"
            return trace

        with logfire.span("synthesise"):
            trace.answer = synth.explain(
                question, result, found.reviews if found else None, language=t.language
            )
        if found:
            trace.quoted_reviews = quoted(trace.answer, found.reviews)
        return trace
