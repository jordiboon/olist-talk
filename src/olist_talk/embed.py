from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384
CACHE = ROOT / "data" / f"review_embeddings.{MODEL_NAME.split('/')[-1]}.parquet"
BATCH = 2000

_model = None


def _get_model():
    # imported lazily: loading the model takes ~5s and most code paths never need it
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(MODEL_NAME)
    return _model


def embed_query(text: str) -> list[float]:
    return next(iter(_get_model().embed([text]))).tolist()


def update_cache(reviews_csv: Path, cache: Path = CACHE) -> int:
    """Embed reviews that are not in the cache yet. Returns how many were added."""
    con = duckdb.connect()
    # distinct: Olist attaches the same review_id to several orders (same text each time)
    con.execute(
        "create table reviews as select distinct review_id, review_comment_message as text "
        "from read_csv(?) where trim(coalesce(review_comment_message, '')) <> ''",
        [reviews_csv.as_posix()],
    )
    if cache.exists():
        missing = con.execute(
            "select review_id, text from reviews "
            "where review_id not in (select review_id from read_parquet(?))",
            [cache.as_posix()],
        ).fetchall()
    else:
        missing = con.execute("select review_id, text from reviews").fetchall()
    if not missing:
        return 0

    model = _get_model()
    chunks = []
    for i in range(0, len(missing), BATCH):
        texts = [text for _, text in missing[i : i + BATCH]]
        chunks.append(np.array(list(model.embed(texts)), dtype=np.float32))
        print(f"  embedded {min(i + BATCH, len(missing)):,}/{len(missing):,}", flush=True)

    vectors = np.vstack(chunks)
    new = pa.table({
        "review_id": pa.array([r for r, _ in missing]),
        "embedding": pa.FixedSizeListArray.from_arrays(pa.array(vectors.ravel()), DIM),
    })

    old = pq.read_table(cache).cast(new.schema) if cache.exists() else None
    table = pa.concat_tables([old, new]) if old is not None else new
    cache.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, cache)
    return len(missing)
