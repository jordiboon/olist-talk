from dataclasses import dataclass, field

from . import db, triage

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
    with db.connect() as con:
        t = triage.triage(question, con)
        trace = Trace(question=question, route=t.route.value, answer=t.reply)
        if t.route.value not in ANSWERED_BY_TRIAGE:
            trace.error = f"{t.route.value} path not built yet"
        return trace
