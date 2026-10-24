#!/usr/bin/env python3
"""Score a change-impact report for CR-014 against the known answer.
Items marked "rejected" by the human reviewer are not counted.

Usage: python3 scripts/eval_impact.py outputs/impact_CR-014.json
"""
import json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def score(report):
    required = set(json.loads((ROOT / "eval/golden/impact_CR-014.json").read_text())["required"])
    got = {i.get("id") for i in report.get("items", []) if i.get("status") != "rejected"}
    missed, extra = sorted(required - got), sorted(got - required)
    return {
        "known": len(required), "reported": len(got),
        "recall": len(required & got) / len(required),
        "precision": len(required & got) / len(got) if got else 0,
        "missed": missed, "extra": extra,
        "rejected": sum(1 for i in report.get("items", []) if i.get("status") == "rejected"),
        "verdict": "PASS" if not missed and not extra else "REVIEW REQUIRED",
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else ROOT / "outputs/impact_CR-014.json"
    s = score(json.loads(pathlib.Path(path).read_text()))
    print(f"Required affected requirements: {s['known']} | Counted: {s['reported']} | Rejected by reviewer: {s['rejected']}")
    print(f"Recall: {s['recall']:.0%} | Precision: {s['precision']:.0%}")
    for m in s["missed"]:
        print(f"MISSED: {m}")
    for e in s["extra"]:
        print(f"NEEDS HUMAN REVIEW (not in known set): {e}")
    print(f"Result: {s['verdict']}")
    sys.exit(0 if s["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
