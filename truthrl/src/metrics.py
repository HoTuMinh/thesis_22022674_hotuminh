"""Compute metrics (hallucination, truthfulness, correct, abstain, F1) from a results JSONL."""

import argparse
import json
import os

from config import ADAPTER_RESULTS, BASELINE_RESULTS


def classify(r):
    if r["judge_abstained"] is True:
        return "abstain"
    if r["is_unanswerable"]:
        return "hallucination"
    return "correct" if r["is_correct"] is True else "hallucination"


def compute(path):
    rows = [json.loads(l) for l in open(path)]
    n = len(rows)
    cls = [classify(r) for r in rows]
    n_corr = cls.count("correct")
    n_abst = cls.count("abstain")
    n_hall = cls.count("hallucination")

    tp = sum(r["judge_abstained"] is True and r["is_unanswerable"] for r in rows)
    fp = sum(r["judge_abstained"] is True and not r["is_unanswerable"] for r in rows)
    fn = sum(r["judge_abstained"] is not True and r["is_unanswerable"] for r in rows)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0

    return {
        "n": n,
        "hallucination": n_hall / n,
        "truthfulness": (n_corr + n_abst) / n,
        "correct": n_corr / n,
        "abstain": n_abst / n,
        "abstention_f1": f1,
    }


def print_row(name, m):
    print(f"{name:<22}{m['hallucination']:>10.3f}{m['truthfulness']:>12.3f}"
          f"{m['correct']:>10.3f}{m['abstain']:>10.3f}{m['abstention_f1']:>10.3f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", nargs="+", default=None,
                        help="Pairs of name:path (e.g. baseline:baseline.jsonl adapter:adapter.jsonl)")
    args = parser.parse_args()

    if args.files:
        runs = [tuple(s.split(":", 1)) for s in args.files]
    else:
        runs = []
        if os.path.exists(BASELINE_RESULTS):
            runs.append(("baseline", BASELINE_RESULTS))
        if os.path.exists(ADAPTER_RESULTS):
            runs.append(("adapter", ADAPTER_RESULTS))

    hdr = f"{'':<22}{'Halluc↓':>10}{'Truthful↑':>12}{'Correct':>10}{'Abstain':>10}{'Abst.F1↑':>10}"
    print(hdr)
    print("-" * len(hdr))
    for name, path in runs:
        print_row(name, compute(path))


if __name__ == "__main__":
    main()
