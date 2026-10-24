#!/usr/bin/env python3
"""Score a gap report against the known-answer set (eval/golden/gaps.json).
Findings marked "rejected" by the human reviewer are not counted.

Usage: python3 scripts/eval.py outputs/gap_report.json
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ID = re.compile(r"^(DDS|DID|SRS|TC)-\d{3}$")


def key(f):
    return (f.get("type"), tuple(sorted(i for i in f.get("ids", []) if ID.match(str(i)))))


def load_findings(path):
    data = json.loads(pathlib.Path(path).read_text())
    return data.get("findings", []) if isinstance(data, dict) else data


def score(findings):
    golden = {key(g) for g in json.loads((ROOT / "eval/golden/gaps.json").read_text())}
    active = [f for f in findings if f.get("status") != "rejected"]
    found = {key(f) for f in active}
    tp = golden & found
    missed, extra = sorted(golden - found), sorted(found - golden)
    return {
        "known": len(golden), "reported": len(found),
        "recall": len(tp) / len(golden) if golden else 0,
        "precision": len(tp) / len(found) if found else 0,
        "missed": [f"{t} {', '.join(i)}" for t, i in missed],
        "extra": [f"{t} {', '.join(i)}" for t, i in extra],
        "rejected": sum(1 for f in findings if f.get("status") == "rejected"),
        "verdict": "PASS" if not missed and not extra else "REVIEW REQUIRED",
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else ROOT / "outputs/gap_report.json"
    s = score(load_findings(path))
    print(f"Known gaps: {s['known']} | Counted findings: {s['reported']} | Rejected by reviewer: {s['rejected']}")
    print(f"Recall: {s['recall']:.0%} | Precision: {s['precision']:.0%}")
    for m in s["missed"]:
        print(f"MISSED: {m}")
    for e in s["extra"]:
        print(f"NEEDS HUMAN REVIEW (not in known set): {e}")
    print(f"Result: {s['verdict']}")
    sys.exit(0 if s["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
