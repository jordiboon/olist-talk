import os
import re
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from olist_talk import db, llm, obs
from olist_talk.pipeline import Trace, answer

# assertions that need a judgement call, not a string match. Unchecked by default;
# `--judge` asks an LLM. Never passed silently.
SOFT = {
    "must_report_sample_size": "If the answer names a group (such as a state) as best or "
    "worst, it also says how many reviews or orders that result rests on.",
    "must_not_fabricate_statistics": "The answer does not generalise from the retrieved "
    "reviews to all customers: no percentages, proportions or 'most customers' claims about "
    "the whole population unless that number appears in the query rows. Saying how many "
    "reviews were retrieved, and describing recurring themes among them, is fine.",
}
JUDGE = "--judge" in sys.argv
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "anthropic:claude-sonnet-5")


class Verdict(BaseModel):
    reason: str
    passed: bool


def judge(criterion: str, trace: Trace) -> tuple[bool, str]:
    v = llm.structured(
        "You check one criterion against an answer. Judge only that criterion.",
        f"Criterion: {criterion}\n\nQuestion: {trace.question}\n\n"
        f"Query rows: {trace.rows or 'none'}\n\nAnswer:\n{trace.answer}",
        Verdict,
        model=JUDGE_MODEL,
    )
    return v.passed, v.reason

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
            if JUDGE and trace.error:
                add(key, None, "not judged - the pipeline errored, nothing to judge")
            elif JUDGE:
                try:
                    ok, reason = judge(SOFT[key], trace)
                    add(key, ok, f"judge: {reason}")
                except Exception as e:
                    add(key, None, f"judge unavailable - {type(e).__name__}")
            else:
                add(key, None, "unchecked - run with --judge")
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


def run_once(cases: list[dict], verbose: bool) -> dict[str, bool]:
    outcome = {}
    for case in cases:
        try:
            trace = answer(case["question"])
        except Exception as e:
            trace = Trace(question=case["question"], error=f"{type(e).__name__}: {e}")

        results = check(case, trace)
        hard = [r for r in results if r[1] is not None]
        ok = bool(hard) and all(r[1] for r in hard)
        outcome[case["id"]] = ok
        if not verbose:
            continue

        print(f"{'PASS' if ok else 'FAIL'}  {case['id']}  {case['question'][:52]:<52} [{case['expect']['route']}]")
        if trace.error:
            print(f"        error: {trace.error}")
        for name, res, detail in results:
            if res is False:
                print(f"        x {name} {detail}")
            elif res is None:
                print(f"        ? {name} {detail}")
            elif detail.startswith("judge:"):
                print(f"        v {name} {detail}")
    return outcome


def main() -> int:
    # --repeat N: one green run proves little when the model can write different SQL each
    # time, so report how often each case passes instead
    repeat = int(sys.argv[sys.argv.index("--repeat") + 1]) if "--repeat" in sys.argv else 1
    obs.setup()
    cases = yaml.safe_load((ROOT / "evals" / "questions.yaml").read_text())

    runs = []
    for i in range(repeat):
        if repeat > 1:
            print(f"run {i + 1}/{repeat}...", flush=True)
        runs.append(run_once(cases, verbose=repeat == 1))

    if repeat == 1:
        passed = sum(runs[0].values())
        print(f"\n{passed} passed, {len(cases) - passed} failed")
        return 0 if passed == len(cases) else 1

    print()
    for case in cases:
        n = sum(run[case["id"]] for run in runs)
        print(f"{case['id']}  {n}/{repeat}  {'#' * n}{'.' * (repeat - n)}  {case['question'][:55]}")
    total = sum(sum(run.values()) for run in runs)
    print(f"\noverall: {total}/{len(cases) * repeat} ({100 * total / (len(cases) * repeat):.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
