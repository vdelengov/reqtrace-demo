# Requirements Agent demo (synthetic)

A small, fully fictional workspace showing reusable AI skills, scripted checks, known-answer
scoring, and a human-in-the-loop review, for requirements work in a regulated setting.

**All data is synthetic.** The product ("LabQC Connect"), its requirements, tests and change
request are invented. No real company data, code, or documents are used.

## Requirement levels

| Level | File | Meaning | Traces to |
| --- | --- | --- | --- |
| DDS | `data/dds.csv` | Marketing-level requirements | (top level) |
| DID | `data/did.csv` | System-level requirements | a DDS |
| SRS | `data/srs.csv` | Software subsystem requirements | a DID |
| Tests | `data/tests.csv` | Verification test cases | an SRS |

Every requirement applies to the whole platform and is written in EARS form
(Ubiquitous, Event-driven, State-driven, Unwanted behavior, Optional feature, Complex).
A few gaps are seeded on purpose so the checks and the agent have something to find.

## Run it

```
python3 app/server.py
```

Then open http://localhost:8765. No installs needed (Python 3 standard library).

- **Live mode** uses your logged-in Claude Code CLI (`claude`). The server finds it on your PATH,
  in `~/.claude/local`, Homebrew, or inside the VS Code extension. To point at a specific binary:
  `CLAUDE_BIN=/path/to/claude python3 app/server.py`
- **Replay mode** plays back a recorded run with no AI calls, but still pauses for your real
  decisions and applies them. Use it as a fallback if live is slow.
- Set your name for the review log: `REVIEWER="Vladimir" python3 app/server.py`

## How the human-in-the-loop works

1. The agent (Claude Code, `claude -p` in this folder) runs phase 1 of a skill. It writes a draft
   report and `outputs/questions.json`, then stops.
2. The UI shows each question with the agent's evidence and any proposed EARS rewrite.
   You choose an option and can add a comment.
3. The app records every decision in `review/review_log.json`, writes `outputs/answers.json`, and
   resumes the **same** Claude Code session for phase 2, which applies your decisions.
4. The final report is scored against the known answers in `eval/golden/`, before and after your review.

The agent can only run `python3 scripts/*` and read or write files. `CLAUDE.md` forbids edits to `data/`.

## Command line, without the UI

```
python3 scripts/check_trace.py                     # scripted checks, no AI
python3 scripts/check_trace.py --tree DID-004      # what traces below a requirement
python3 scripts/eval.py outputs/gap_report.json    # score a gap report
python3 scripts/eval_impact.py outputs/impact_CR-014.json
```

## Layout

- `data/`: DDS, DID, SRS, tests, change request CR-014 (read-only)
- `.claude/skills/`: `gap-discovery` and `impact-analysis` (two phases each)
- `scripts/`: scripted traceability and EARS checks, and the scoring scripts
- `eval/golden/`: known answers
- `app/`: local server, UI, and recorded replays
- `outputs/`: agent results; `review/`: the human decision log
- `docs/DEMO_SCRIPT.md`: the panel run-through
