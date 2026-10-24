---
name: impact-analysis
description: Analyze which DDS, DID and SRS requirements and tests a change request affects, propose any new requirement in EARS form, and ask the human to decide. Use when asked for the impact of a change request such as CR-014.
---

# Impact analysis

This skill runs in two phases. The prompt says which phase to run.

## Phase 1: analyze and ask

1. Read the change request (`data/change_request_CR-014.md`).
2. Find the affected requirements at each level. Use `python3 scripts/check_trace.py --tree <ID>`
   to see what traces below a requirement, and read `data/*.csv` for the text.
3. List the tests that verify affected SRS requirements, and note affected SRS with no test.
4. If no existing requirement covers the change, propose a new one in EARS form.
5. Write `outputs/impact_CR-014.draft.json`:
   `{"change": "CR-014", "items": [{"ref": "I1", "id": "DID-004", "level": "DID", "rationale": "...", "confidence": "high|medium|low"}], "tests": [{"id": "TC-006", "verifies": "SRS-006", "action": "..."}], "proposed_requirements": [{"ref": "P1", "parent": "DID-004", "level": "SRS", "text": "EARS text"}]}`
6. Write `outputs/questions.json`: one question for every proposed requirement and every item
   with confidence `medium` or `low`. Same format as the gap-discovery skill:
   `[{"id": "Q1", "ref": "P1", "title": "...", "ids": ["DID-004"], "question": "...", "proposal": "optional", "options": [...], "reject_options": [...]}]`
   For a proposed requirement use options `["Accept", "Edit text (add a comment)", "Not needed"]`, rejecting on "Not needed".
   For an uncertain item use `["Include as affected", "Not affected"]`, rejecting on "Not affected".
7. Stop. Do not write the final report and do not change any requirement.

## Phase 2: apply the human's decisions

1. Read `outputs/answers.json` and `outputs/questions.json`.
2. Write `outputs/impact_CR-014.json`: the draft with a `status` on every item and proposed requirement
   (`rejected` if the answer is in that question's `reject_options`, otherwise `accepted`),
   plus `human_decision` and `human_comment` where a question was asked.
3. Run `python3 scripts/eval_impact.py outputs/impact_CR-014.json` and report the result in one or two sentences.
4. Do not ask further questions.
