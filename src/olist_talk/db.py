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

    # rebuild from scratch - "create or replace" leaves tables that were removed from
    # TABLES still sitting in the file
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        for table, filename in TABLES.items():
            con.execute(
                f"create table {table} as "
                f"select * from read_csv('{(raw_dir / filename).as_posix()}')"
            )
    finally:
        con.close()
    return db_path


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    # read_only is the security boundary: the engine refuses DDL/DML outright.
    if not db_path.exists():
        raise FileNotFoundError(f"no database at {db_path}; run: uv run python -m olist_talk.db")
    return duckdb.connect(str(db_path), read_only=True)


def count_rows(con: duckdb.DuckDBPyConnection, table: str) -> int:
    row = con.execute(f"select count(*) from {table}").fetchone()
    return row[0] if row else 0


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


if __name__ == "__main__":
    path = build()
    with connect(path) as con:
        actual = [r[0] for r in con.execute("show tables").fetchall()]
        total = sum(count_rows(con, t) for t in actual)
    print(f"built {path.relative_to(ROOT)} - {len(actual)} tables, {total:,} rows")
    print(f"  {', '.join(actual)}")
