---
name: gap-discovery
description: Find gaps across DDS, DID and SRS requirements and tests - missing links, untested requirements, EARS violations, conflicts between levels, and untestable wording - then ask the human to decide. Use when asked to find requirement gaps or run gap discovery.
---

# Gap discovery

This skill runs in two phases. The prompt says which phase to run.

## Phase 1: analyze and ask

1. Run `python3 scripts/check_trace.py`. Report every gap it lists, using the same type names.
2. Read `data/dds.csv`, `data/did.csv`, `data/srs.csv`, and `data/tests.csv`.
3. Look for what the script cannot see:
   - `conflict`: a child requirement whose value disagrees with its parent (for example a time limit).
   - `ambiguous`: wording that passes EARS syntax but cannot be verified (for example "promptly", "user-friendly").
4. Write `outputs/gap_report.draft.json`:
   `{"findings": [{"ref": "F1", "type": "...", "ids": ["SRS-010"], "evidence": "...", "confidence": "high|medium|low", "proposed_text": "optional EARS rewrite"}]}`
   Types: `missing_child`, `orphan`, `missing_test`, `ears_violation`, `conflict`, `ambiguous`.
   For `conflict`, list the parent and the child ID. Include only findings you can back with quoted text.
5. Write `outputs/questions.json`: exactly one question for **every** finding in the draft, with the
   finding's `ref`, regardless of type or confidence (including `high` confidence and gaps reported by
   `check_trace.py`). Never skip a finding and never decide for the human that it is a real issue. Before
   you stop, check that every `ref` in `gap_report.draft.json` appears in `questions.json`. Format:
   `[{"id": "Q1", "ref": "F7", "title": "short label", "ids": ["DID-005","SRS-010"], "question": "...", "proposal": "optional EARS text", "options": ["...", "Not a real issue"], "reject_options": ["Not a real issue"]}]`
   Always include "Not a real issue" as the last option and in `reject_options`.
6. Stop. Do not write the final report and do not change any requirement. The human answers in the UI.

## Phase 2: apply the human's decisions

1. Read `outputs/answers.json` (`[{"id": "Q1", "choice": "...", "comment": "..."}]`) and `outputs/questions.json`.
2. Write `outputs/gap_report.json`: every finding from the draft, each with a `status`.
   - A finding whose question was answered with a choice in that question's `reject_options` gets `"status": "rejected"`.
   - Every other finding gets `"status": "accepted"`, using the human's choice.
   - Add `human_decision` and `human_comment` to findings that had a question.
3. Run `python3 scripts/eval.py outputs/gap_report.json` and report the result in one or two sentences.
4. Do not ask further questions.
