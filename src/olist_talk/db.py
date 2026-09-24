from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "olist.duckdb"
RAW_DIR = ROOT / "data" / "raw"

TABLES = {
    "orders": "olist_orders_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
}


def build(db_path: Path = DB_PATH, raw_dir: Path = RAW_DIR) -> Path:
    missing = [f for f in TABLES.values() if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"missing CSVs in {raw_dir}: {', '.join(missing)}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for table, filename in TABLES.items():
            con.execute(
                f"create table {table} as "
                f"select * from read_csv('{(raw_dir / filename).as_posix()}')"
            )

        from . import embed  # lazy: fastembed is only needed at build time

        added = embed.update_cache(raw_dir / TABLES["order_reviews"])
        if added:
            print(f"embedded {added:,} new reviews")
        con.execute(
            f"create table review_embeddings as select review_id, "
            f"embedding::float[{embed.DIM}] as embedding "
            f"from read_parquet('{embed.CACHE.as_posix()}') "
            f"where review_id in (select review_id from order_reviews)"
        )
    finally:
        con.close()
    return db_path


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    if not db_path.exists():
        raise FileNotFoundError(f"no database at {db_path}; run: uv run python -m olist_talk.db")
    return duckdb.connect(str(db_path), read_only=True)


def count_rows(con: duckdb.DuckDBPyConnection, table: str) -> int:
    row = con.execute(f"select count(*) from {table}").fetchone()
    if row is None:
        return 0
    return row[0]

def schema_text(con: duckdb.DuckDBPyConnection) -> str:
    parts = []
    for table in TABLES:
        cols = con.execute(
            "select column_name, data_type from information_schema.columns "
            "where table_name = ? order by ordinal_position",
            [table],
        ).fetchall()
        n = count_rows(con, table)
        body = "\n".join(f"  {name}: {dtype.lower()}" for name, dtype in cols)
        parts.append(f"{table} ({n:,} rows)\n{body}")
    return "\n\n".join(parts)


def data_facts(con: duckdb.DuckDBPyConnection) -> str:
    row = con.execute(
        "select min(order_purchase_timestamp), max(order_purchase_timestamp) from orders"
    ).fetchone()
    if row is None:
        raise RuntimeError("orders table is empty")
    lo, hi = row
    statuses = con.execute(
        "select order_status, count(*) n from orders group by 1 order by n desc"
    ).fetchall()
    return (
        f"Orders span {lo:%Y-%m-%d} to {hi:%Y-%m-%d}. There is no data outside that range.\n"
        f"order_status values: {', '.join(f'{s} ({n:,})' for s, n in statuses)}.\n"
        "Reviews are Brazilian Portuguese free text; only ~41% have a comment_message.\n"
        "customer_state is a two-letter Brazilian state code (SP, RJ, BA, ...).\n"
        "\n"
        "Definitions - use these, do not invent alternatives:\n"
        "- An order is late when it was delivered on a later calendar day than estimated:\n"
        "  order_delivered_customer_date::date > order_estimated_delivery_date::date.\n"
        "  Estimated dates have no time of day, so comparing full timestamps would wrongly\n"
        "  count same-day deliveries as late. Only delivered orders can be late or on time.\n"
        "- A late rate is a share of delivered orders, counting each order once - compute it\n"
        "  on orders before joining reviews, which would count some orders twice.\n"
        "- A customer is a person: count customer_unique_id. customer_id is one per order,\n"
        "  so the same person appears under several customer_ids.\n"
        "- Change over time is measured by the order's purchase date\n"
        "  (order_purchase_timestamp), unless the question asks when reviews were written."
    )


if __name__ == "__main__":
    path = build()
    with connect(path) as con:
        actual = [r[0] for r in con.execute("show tables").fetchall()]
        total = sum(count_rows(con, t) for t in actual)
    print(f"built {path.relative_to(ROOT)} - {len(actual)} tables, {total:,} rows")
    print(f"  {', '.join(actual)}")
