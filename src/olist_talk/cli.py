import argparse

from . import obs, pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="olist-talk")
    parser.add_argument("--route", action="store_true", help="show which route answered each question")
    args = parser.parse_args()

    obs.setup()
    print("Ask about the Olist data. Empty line or Ctrl-D to quit.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            return

        try:
            trace = pipeline.answer(question)
        except Exception as e:
            print(f"  failed: {type(e).__name__}: {e}\n")
            continue

        if args.route:
            print(f"  [{trace.route}]")
        print(f"\n{trace.answer or f'  ({trace.error})'}\n")


if __name__ == "__main__":
    main()
