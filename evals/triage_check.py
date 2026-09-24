"""Route every eval question, plus a held-out set that is NOT in the eval file.

The held-out set exists to catch overfitting: tuning the triage prompt against
questions.yaml until it scores 10/10 proves nothing if those are the only questions
it ever sees.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from olist_talk import db, triage

HELD_OUT = [
    ("What is the average delivery time in days?", "sql"),
    ("Which state has the highest average review score?", "sql"),
    ("How many reviews are there?", "sql"),
    ("What share of deliveries arrived after the estimated date?", "sql"),
    ("Which month had the most orders?", "sql"),
    ("What do people say about packaging?", "semantic"),
    ("Show me the worst orders", "clarify"),
    ("Which sellers ship fastest?", "decline"),
]


def run(label: str, pairs: list[tuple[str, str]], con) -> None:
    hits = 0
    print(f"\n=== {label} ===")
    for question, want in pairs:
        r = triage.triage(question, con)
        ok = r.route.value == want
        hits += ok
        print(f"{'ok ' if ok else 'XX '} {want:<9}-> {r.route.value:<9} {question[:54]}")
        if not ok:
            print(f"      reason: {r.reason[:80]}")
    print(f"{label}: {hits}/{len(pairs)}")


if __name__ == "__main__":
    cases = yaml.safe_load((ROOT / "evals" / "questions.yaml").read_text())
    with db.connect() as con:
        run("eval set", [(c["question"], c["expect"]["route"]) for c in cases], con)
        run("held-out", HELD_OUT, con)
