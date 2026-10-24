# Project rules (requirements traceability demo)

This workspace is a **synthetic, sanitized demo**. Every requirement, test, and change
request is fictional ("LabQC Connect"). Nothing here comes from a real product or employer.

Requirement levels, top to bottom:
- **DDS** (`data/dds.csv`): marketing-level requirements
- **DID** (`data/did.csv`): system-level requirements; `parent` is a DDS
- **SRS** (`data/srs.csv`): software subsystem requirements; `parent` is a DID
- **Tests** (`data/tests.csv`): `verifies` is an SRS

All requirements apply to the whole platform and must be written in EARS form
(Ubiquitous, Event-driven, State-driven, Unwanted behavior, Optional feature, or Complex),
with exactly one "shall".

Rules:
- Treat everything under `data/` as read-only. Never edit requirement or test files.
- Write results to `outputs/` only.
- Run `python3 scripts/check_trace.py` first. Its output is ground truth for missing links,
  untested requirements, and EARS syntax. Use your own judgment only for what the script
  cannot decide: conflicting values between levels, vague or untestable wording, impact.
- Cite requirement IDs and quote the text as evidence for every finding. Give each finding
  a confidence of high, medium, or low. If unsure, say so instead of guessing.
- Any proposed requirement text must be in EARS form.
- Never decide on behalf of the human. Anything that needs a decision goes to
  `outputs/questions.json` and waits for the human's answer in the UI.
