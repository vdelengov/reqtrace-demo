# Live demo script (about 10 minutes)

Before the panel: run `python3 app/server.py`, open http://localhost:8765, click **Reset**,
and do one full rehearsal in **Live** mode. Keep **Replay** as the fallback.

## 1. The data (1.5 min)
- **Trace** tab: DDS (marketing) → DID (system) → SRS (software) → tests, for the whole platform.
- Point at the EARS keywords (When, While, If/then, shall) and the pattern tag on each row.
- Say: all data is fictional.

## 2. Scripted checks (1.5 min)
- Click **1 Scripted checks**. Six structural gaps: a DDS with no DID, a DID with no SRS,
  an orphan SRS, two untested SRS, and one SRS that is not in EARS form.
- Say: no AI here. Same input, same output. Tick **Only flagged** to show just the gaps.

## 3. Gap discovery agent (4 min)
- Click **2 Gap discovery** (Live). Narrate the feed: it runs the script first, then reads the text.
- It finds what the script can't: DID-005 says 3 seconds, its child SRS-010 says 5 seconds;
  SRS-016 says "promptly", which can't be verified.
- **Human input needed**: answer the four questions.
  - Q1 conflict: "Align SRS-010 to 3 seconds", comment "system requirement wins".
  - Q2 and Q3: accept the EARS rewrites.
  - Q4 low-confidence finding: "Not a real issue". This is the AI being wrong, caught by a person.
- Send. The agent resumes the same session and applies your decisions.
- Show the scores: before review, precision is under 100% because of the false finding;
  after review, PASS.

## 4. Impact analysis, CR-014 (2.5 min)
- Click **3 Impact · CR-014** (add lot expiry to outbound HL7 results).
- It traces DID-004 and DID-006 down to SRS and tests, and proposes a new SRS in EARS form.
- Approve the new requirement; mark SRS-013 "Not affected".
- Open **Review log**: every decision, with time and reviewer, recorded by the app, not the AI.

## Fallbacks
- Live is slow or fails: switch to **Replay** at the top and rerun the step. It still waits for
  your decisions.
- Live writes no final report: the app assembles it from your decisions and says so in the feed.
- Never edit files under `data/` during the demo.
