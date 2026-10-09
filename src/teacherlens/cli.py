"""Reproducible command-line training and trusted-model prediction."""

import argparse
import csv
from pathlib import Path
import sys

from .config import load_config
from .data import load_dataset
from .experiment import run_experiment
from .inference import load_model, predict_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="TeacherLens ML research baseline")
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train")
    train.add_argument("--config", required=True)
    research = commands.add_parser("research", help="Three-way grouped model selection and final evaluation")
    research.add_argument("--config", required=True)
    research.add_argument("--output-dir", help="New artifact directory; relative to the current directory")
    verify = commands.add_parser("verify-research", help="Compare two trusted local research runs")
    verify.add_argument("--first", required=True)
    verify.add_argument("--second", required=True)
    predict = commands.add_parser("predict", help="Load only trusted local model files")
    predict.add_argument("--model", required=True)
    predict.add_argument("--data", required=True)
    predict.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "train":
            report = run_experiment(load_config(args.config))
            print(report["interpretation"])
            print(f"Artifacts saved. Data kind: {report['data_kind']}")
        elif args.command == "research":
            from dataclasses import replace
            from .research import load_research_config, run_research
            config = load_research_config(args.config)
            if args.output_dir:
                config = replace(config, output_dir=str(Path(args.output_dir).resolve()))
            report = run_research(config)
            print(f"Research artifacts saved. Data kind: {report['data_kind']}")
        elif args.command == "verify-research":
            from .reproducibility import verify_research_runs
            verify_research_runs(args.first, args.second)
            print("Reproducibility verified: reports, split manifests and fitted model arrays are identical.")
        else:
            output = Path(args.output)
            if output.exists():
                raise ValueError(f"Output already exists: {output}")
            rows = load_dataset(args.data, labeled=False)
            predictions = predict_rows(load_model(args.model), rows)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("row_id", "Category:Misconception", "data_kind"))
                writer.writeheader()
                writer.writerows(predictions)
            print(f"Predictions saved. Model data kind: {predictions[0]['data_kind']}")
    except (ValueError, OSError, EOFError) as exc:
        print(f"TeacherLens error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
