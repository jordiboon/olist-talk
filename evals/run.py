import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from olist_talk import db, obs  # noqa: E402
from olist_talk.pipeline import Trace, answer  # noqa: E402

# assertions that need a judgement call, not a string match; reported, never passed silently
SOFT = {"must_report_sample_size", "must_not_fabricate_statistics"}

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    return [float(m) for m in NUMBER.findall(text.replace(",", ""))]


def close_to(target: float, tol: float, trace: Trace) -> bool:
    pool = numbers_in(trace.answer)
    for row in trace.rows or []:
        pool += [float(v) for v in row if isinstance(v, (int, float))]
    return any(abs(v - target) <= tol for v in pool)


def check(case: dict, trace: Trace) -> list[tuple[str, bool | None, str]]:
    exp = case["expect"]
    tol = exp.get("tolerance", 0.01)
    out: list[tuple[str, bool | None, str]] = []

    def add(name, ok, detail=""):
        out.append((name, ok, detail))

    for key, want in exp.items():
        if key == "tolerance":
            continue
        if key in SOFT:
            add(key, None, "needs a judge")
        elif key == "route":
            add(key, trace.route == want, f"got {trace.route or '-'}")
        elif key == "value":
            add(key, close_to(want, tol, trace), f"want {want}+-{tol}")
        elif key == "must_contain_values":
            missing = [v for v in want if not close_to(v, tol, trace)]
            add(key, not missing, f"missing {missing}" if missing else "")
        elif key == "row_count":
            got = len(trace.rows) if trace.rows is not None else None
            add(key, got == want, f"want {want}, got {got}")
        elif key in ("must_mention", "accepted_values", "lowest_month"):
            wants = want if isinstance(want, list) else [want]
            hay = trace.answer.lower()
            hits = [w for w in wants if str(w).lower() in hay]
            ok = bool(hits) if key == "accepted_values" else len(hits) == len(wants)
            add(key, ok, f"found {hits}")
        elif key == "must_quote_reviews":
            add(key, bool(trace.quoted_reviews), f"{len(trace.quoted_reviews)} quoted")
        elif key == "no_query_executed":
            add(key, trace.sql is None, f"ran: {(trace.sql or '')[:30]}")
        elif key == "no_ddl_executed":
            sql = (trace.sql or "").lower()
            bad = [k for k in ("drop", "delete", "update", "insert", "create") if k in sql]
            add(key, not bad, f"found {bad}" if bad else "")
        elif key == "table_still_exists":
            with db.connect() as con:
                names = [r[0] for r in con.execute("show tables").fetchall()]
            add(key, "orders" in names, f"tables: {len(names)}")
        elif key == "must_not_return_empty_as_answer":
            add(key, not (trace.rows == [] and trace.route == "sql"), "")
        else:
            add(key, None, "unknown assertion")
    return out


def main() -> int:
    obs.setup()
    cases = yaml.safe_load((ROOT / "evals" / "questions.yaml").read_text())
    passed = failed = soft = 0

    for case in cases:
        try:
            trace = answer(case["question"])
        except Exception as e:
            trace = Trace(question=case["question"], error=f"{type(e).__name__}: {e}")

        results = check(case, trace)
        hard = [r for r in results if r[1] is not None]
        ok = bool(hard) and all(r[1] for r in hard)
        passed += ok
        failed += not ok
        soft += sum(1 for r in results if r[1] is None)

        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {case['id']}  {case['question'][:52]:<52} [{case['expect']['route']}]")
        if trace.error:
            print(f"        error: {trace.error}")
        for name, res, detail in results:
            if res is False:
                print(f"        x {name} {detail}")
            elif res is None:
                print(f"        ? {name} {detail}")

    print(f"\n{passed} passed, {failed} failed, {soft} unchecked (need a judge)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
