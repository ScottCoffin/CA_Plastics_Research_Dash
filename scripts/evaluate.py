"""Evaluate predictions against canonical adjudicated gold JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.nlp.eval import evaluate, render_markdown, write_calibration_plot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "dev", "test"), required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--data-snapshot", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plot", type=Path)
    parser.add_argument("--final-test", action="store_true")
    args = parser.parse_args()
    report = evaluate(
        json.loads(args.gold.read_text(encoding="utf-8")),
        json.loads(args.predictions.read_text(encoding="utf-8")),
        split=args.split,
        model_version=args.model_version,
        data_snapshot=args.data_snapshot,
        allow_test=args.final_test,
    )
    if args.plot:
        write_calibration_plot(report, args.plot)
        plot = args.plot.name
    else:
        plot = None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(report, plot), encoding="utf-8")
    print(f"Wrote evaluation report for {report['n']} {args.split} works")


if __name__ == "__main__":
    main()
