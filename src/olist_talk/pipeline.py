from dataclasses import dataclass, field


@dataclass
class Trace:
    """What one run of the app produced. The eval harness asserts against this."""

    question: str
    route: str = ""
    sql: str | None = None
    rows: list | None = None
    answer: str = ""
    quoted_reviews: list[str] = field(default_factory=list)
    error: str | None = None


def answer(question: str) -> Trace:
    raise NotImplementedError("pipeline not built yet")
