#!/usr/bin/env python3
"""Deterministic checks across three requirement levels. No AI involved:
the same input always gives the same output.

Levels (top to bottom):
  DDS  marketing-level requirements  (data/dds.csv)
  DID  system-level requirements     (data/did.csv, parent = DDS)
  SRS  software subsystem reqs       (data/srs.csv, parent = DID)
  TC   test cases                    (data/tests.csv, verifies = SRS)

Checks: missing children, orphans, untested SRS, and EARS syntax.
Semantic problems (conflicting values, vague wording) are left to the AI skill
and the human reviewer.

Usage:
  python3 scripts/check_trace.py            human-readable summary
  python3 scripts/check_trace.py --json     also writes outputs/structural_gaps.json
  python3 scripts/check_trace.py --tree DID-004 [ID ...]   show what traces below an ID
"""
import csv, json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# EARS patterns (Mavin et al.). Each requirement must match one and use "shall" once.
EARS = [
    ("Complex", re.compile(r"^While .+, when .+, the .+ shall .+\.$")),
    ("State-driven", re.compile(r"^While .+, the .+ shall .+\.$")),
    ("Event-driven", re.compile(r"^When .+, the .+ shall .+\.$")),
    ("Unwanted behavior", re.compile(r"^If .+, then the .+ shall .+\.$")),
    ("Optional feature", re.compile(r"^Where .+, the .+ shall .+\.$")),
    ("Ubiquitous", re.compile(r"^The .+ shall .+\.$")),
]


def ears_pattern(text):
    t = text.strip()
    if len(re.findall(r"\bshall\b", t)) != 1:
        return None
    for name, rx in EARS:
        if rx.match(t):
            return name
    return None


def rows(name):
    with open(DATA / name, newline="") as f:
        return list(csv.DictReader(f))


def load():
    return {"dds": rows("dds.csv"), "did": rows("did.csv"), "srs": rows("srs.csv"), "tests": rows("tests.csv")}


def analyze(d=None):
    d = d or load()
    dds_ids = {r["id"] for r in d["dds"]}
    did_ids = {r["id"] for r in d["did"]}
    srs_ids = {r["id"] for r in d["srs"]}
    gaps = []
    for r in d["dds"]:
        if not any(x["parent"] == r["id"] for x in d["did"]):
            gaps.append({"type": "missing_child", "ids": [r["id"]], "detail": "No DID traces to this DDS"})
    for r in d["did"]:
        if r["parent"] not in dds_ids:
            gaps.append({"type": "orphan", "ids": [r["id"]], "detail": "No valid parent DDS"})
        if not any(x["parent"] == r["id"] for x in d["srs"]):
            gaps.append({"type": "missing_child", "ids": [r["id"]], "detail": "No SRS traces to this DID"})
    tested = {t["verifies"] for t in d["tests"]}
    for r in d["srs"]:
        if r["parent"] not in did_ids:
            gaps.append({"type": "orphan", "ids": [r["id"]], "detail": "No valid parent DID"})
        elif r["id"] not in tested:
            gaps.append({"type": "missing_test", "ids": [r["id"]], "detail": "No test case verifies this SRS"})
    for t in d["tests"]:
        if t["verifies"] not in srs_ids:
            gaps.append({"type": "orphan", "ids": [t["id"]], "detail": "Test verifies an unknown SRS"})
    ears = {}
    for level in ("dds", "did", "srs"):
        for r in d[level]:
            p = ears_pattern(r["text"])
            ears[r["id"]] = p
            if p is None:
                gaps.append({"type": "ears_violation", "ids": [r["id"]], "detail": "Does not match an EARS pattern"})
    return {"gaps": gaps, "ears": ears}


def tree(d, ident):
    lines = []
    def tests_for(sid):
        return [t["id"] for t in d["tests"] if t["verifies"] == sid]
    def srs_line(s):
        tc = tests_for(s["id"])
        return f"{s['id']} ({', '.join(tc) if tc else 'no test'})"
    if ident.startswith("DDS"):
        for x in d["did"]:
            if x["parent"] == ident:
                kids = [srs_line(s) for s in d["srs"] if s["parent"] == x["id"]]
                lines.append(f"{ident} -> {x['id']} -> " + (", ".join(kids) or "no SRS"))
    elif ident.startswith("DID"):
        kids = [srs_line(s) for s in d["srs"] if s["parent"] == ident]
        lines.append(f"{ident} -> " + (", ".join(kids) or "no SRS"))
    elif ident.startswith("SRS"):
        lines.append(srs_line(next((s for s in d["srs"] if s["id"] == ident), {"id": ident})))
    return lines


def main():
    d = load()
    if "--tree" in sys.argv:
        for ident in sys.argv[sys.argv.index("--tree") + 1:]:
            print("\n".join(tree(d, ident)))
        return
    res = analyze(d)
    print(f"DDS (marketing): {len(d['dds'])} | DID (system): {len(d['did'])} | "
          f"SRS (software): {len(d['srs'])} | Test cases: {len(d['tests'])}")
    ok = sum(1 for p in res["ears"].values() if p)
    print(f"EARS syntax: {ok} of {len(res['ears'])} requirements match a pattern\n")
    for g in res["gaps"]:
        print(f"- {g['type']}: {', '.join(g['ids'])}  ({g['detail']})")
    print(f"\nStructural gaps found: {len(res['gaps'])}")
    if "--json" in sys.argv:
        out = ROOT / "outputs"; out.mkdir(exist_ok=True)
        (out / "structural_gaps.json").write_text(json.dumps(res["gaps"], indent=2))


if __name__ == "__main__":
    main()
