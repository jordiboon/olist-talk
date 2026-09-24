from dataclasses import dataclass

import duckdb
from pydantic import BaseModel

from . import embed, llm

TOP_K = 10


class SearchRequest(BaseModel):
    phrase: str
    state: str | None
    min_score: int | None
    max_score: int | None


@dataclass
class Review:
    review_id: str
    score: int
    state: str
    text: str
    similarity: float


@dataclass
class SearchResult:
    request: SearchRequest
    reviews: list[Review]


SYSTEM = """You turn a question about customer reviews into a search request. You fill in \
the fields; you never write SQL.

phrase     - what the matching reviews should talk about, as a short phrase in Brazilian
             Portuguese, because the reviews are written in Portuguese.
             If the question names a topic ("complaints about packaging"), describe that
             topic: "embalagem danificada, produto quebrado".
             If the question is open ("what do they complain about?", "why are they
             unhappy?"), do NOT guess a topic - that would only find the topic you
             guessed. Describe the sentiment alone: "cliente insatisfeito, reclamação,
             problema com a compra".
state      - two-letter Brazilian state code if the question is about one state
             (e.g. Bahia -> BA, Rio de Janeiro -> RJ, São Paulo -> SP), otherwise null.
min_score,
max_score  - star range 1-5. Unhappy or complaining customers -> 1 to 2. Happy or
             praising -> 4 to 5. Otherwise null."""


def _clean(req: SearchRequest) -> SearchRequest:
    # not a safety measure - the values are bound as parameters - just correctness
    state = req.state.strip().upper() if req.state else None
    if state and (len(state) != 2 or not state.isalpha()):
        state = None
    lo = min(max(req.min_score, 1), 5) if req.min_score else None
    hi = min(max(req.max_score, 1), 5) if req.max_score else None
    return SearchRequest(phrase=req.phrase, state=state, min_score=lo, max_score=hi)


def search(req: SearchRequest, con: duckdb.DuckDBPyConnection, k: int = TOP_K) -> list[Review]:
    where, params = [], [embed.embed_query(req.phrase)]
    if req.state:
        where.append("c.customer_state = ?")
        params.append(req.state)
    if req.min_score:
        where.append("r.review_score >= ?")
        params.append(req.min_score)
    if req.max_score:
        where.append("r.review_score <= ?")
        params.append(req.max_score)
    params.append(k)

    # distinct on: one review can be attached to several orders
    rows = con.execute(
        f"""
        select * from (
            select distinct on (e.review_id)
                e.review_id, r.review_score, c.customer_state, r.review_comment_message,
                array_cosine_similarity(e.embedding, ?::float[{embed.DIM}]) as sim
            from review_embeddings e
            join order_reviews r using (review_id)
            join orders o using (order_id)
            join customers c using (customer_id)
            {"where " + " and ".join(where) if where else ""}
        )
        order by sim desc
        limit ?
        """,
        params,
    ).fetchall()
    return [Review(*row) for row in rows]


def run(question: str, con: duckdb.DuckDBPyConnection) -> SearchResult:
    req = _clean(llm.structured(SYSTEM, question, SearchRequest))
    return SearchResult(req, search(req, con))
