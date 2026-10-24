#!/usr/bin/env python3
"""Local demo server: requirements explorer + agent runner with a human-in-the-loop pause.

Start:  python3 app/server.py        then open http://localhost:8765

Live mode runs your logged-in Claude Code CLI in this folder (`claude -p ...`), streams
what it does, pauses when the agent writes outputs/questions.json, and resumes the same
Claude Code session after you answer in the UI. Replay mode plays back a recorded run
(no AI calls) but still waits for, and applies, your real decisions.

Python standard library only. Listens on 127.0.0.1 only.
"""
import glob, importlib.util, json, os, shutil, subprocess, threading, time, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
OUT = ROOT / "outputs"
REVIEW_LOG = ROOT / "review" / "review_log.json"
PORT = int(os.environ.get("PORT", "8765"))
REVIEWER = os.environ.get("REVIEWER", "Reviewer")
ALLOWED_TOOLS = "Bash(python3 scripts/*),Read,Write,Edit,Glob,Grep,Skill"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CHECK = load_module("check_trace", ROOT / "scripts" / "check_trace.py")
EVAL_GAPS = load_module("eval_gaps", ROOT / "scripts" / "eval.py")
EVAL_IMPACT = load_module("eval_impact", ROOT / "scripts" / "eval_impact.py")

SKILLS = {
    "gap-discovery": {
        "draft": OUT / "gap_report.draft.json",
        "final": OUT / "gap_report.json",
        "replay": ROOT / "app" / "replay" / "gap_discovery.json",
        "prompt1": "Use the gap-discovery skill (.claude/skills/gap-discovery/SKILL.md). Run phase 1 only, "
                   "then stop after writing outputs/gap_report.draft.json and outputs/questions.json.",
        "prompt2": "The human has answered your questions in the review UI. Run phase 2 of the gap-discovery "
                   "skill now: read outputs/answers.json, write outputs/gap_report.json, run "
                   "python3 scripts/eval.py outputs/gap_report.json, and report the result briefly.",
    },
    "impact-analysis": {
        "draft": OUT / "impact_CR-014.draft.json",
        "final": OUT / "impact_CR-014.json",
        "replay": ROOT / "app" / "replay" / "impact_analysis.json",
        "prompt1": "Use the impact-analysis skill (.claude/skills/impact-analysis/SKILL.md) on CR-014. Run phase 1 "
                   "only, then stop after writing outputs/impact_CR-014.draft.json and outputs/questions.json.",
        "prompt2": "The human has answered your questions in the review UI. Run phase 2 of the impact-analysis "
                   "skill now: read outputs/answers.json, write outputs/impact_CR-014.json, run "
                   "python3 scripts/eval_impact.py outputs/impact_CR-014.json, and report the result briefly.",
    },
}


# ---------------------------------------------------------------- helpers
def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def rel(p):
    s = str(p)
    r = str(ROOT) + os.sep
    return s[len(r):] if s.startswith(r) else s


def find_claude():
    candidates = []
    if os.environ.get("CLAUDE_BIN"):
        candidates.append(os.environ["CLAUDE_BIN"])
    w = shutil.which("claude")
    if w:
        candidates.append(w)
    home = Path.home()
    candidates += [str(home / ".claude/local/claude"), str(home / ".local/bin/claude"),
                   "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]
    for ext in sorted(glob.glob(str(home / ".vscode/extensions/anthropic.claude-code-*")), reverse=True):
        candidates += [p for p in glob.glob(ext + "/**/claude", recursive=True) if os.path.isfile(p)]
    seen = set()
    for p in candidates:
        if not p or p in seen:
            continue
        seen.add(p)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            try:
                v = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=20)
                if v.returncode == 0:
                    return p, (v.stdout.strip() or "unknown version")
            except Exception:
                continue
    return None, None


CLAUDE_BIN, CLAUDE_VERSION = find_claude()


# ---------------------------------------------------------------- runs
class Run:
    def __init__(self, skill, mode):
        self.id = uuid.uuid4().hex[:8]
        self.skill, self.mode = skill, mode
        self.status = "running"            # running | waiting_human | done | error
        self.events, self.questions = [], []
        self.session_id = None
        self.error = None
        self.lock = threading.Lock()
        self.started = now()

    def add(self, kind, text="", **kw):
        with self.lock:
            self.events.append({"i": len(self.events), "kind": kind, "text": text, **kw})

    def view(self, since=0):
        with self.lock:
            return {"id": self.id, "skill": self.skill, "mode": self.mode, "status": self.status,
                    "events": self.events[since:], "next": len(self.events),
                    "questions": self.questions if self.status == "waiting_human" else [],
                    "error": self.error}


RUNS = {}
RUNS_LOCK = threading.Lock()


def active_run():
    with RUNS_LOCK:
        for r in RUNS.values():
            if r.status in ("running", "waiting_human"):
                return r
    return None


def clear_outputs(cfg):
    for p in (cfg["draft"], cfg["final"], OUT / "questions.json", OUT / "answers.json"):
        if Path(p).exists():
            Path(p).unlink()


def tool_summary(name, inp):
    if not isinstance(inp, dict):
        return str(inp)[:200]
    if name == "Bash":
        return inp.get("command", "")
    for k in ("file_path", "path", "pattern", "skill", "url"):
        if k in inp:
            return rel(inp[k])
    return json.dumps(inp)[:200]


def result_text(content):
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict)]
        content = "\n".join(parts)
    s = str(content or "").strip()
    return s if len(s) <= 900 else s[:900] + "\n..."


def run_claude(run, prompt, resume=None):
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--permission-mode", "acceptEdits", "--allowedTools", ALLOWED_TOOLS]
    if resume:
        cmd += ["--resume", resume]
    run.add("status", "Claude Code started" + (" (resuming the same session)" if resume else ""))
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1)
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        if ev.get("session_id"):
            run.session_id = ev["session_id"]
        if t == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "text" and c.get("text", "").strip():
                    run.add("text", c["text"].strip())
                elif c.get("type") == "tool_use":
                    run.add("tool", tool_summary(c.get("name"), c.get("input")), name=c.get("name"))
        elif t == "user":
            for c in ev.get("message", {}).get("content", []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    txt = result_text(c.get("content"))
                    if txt:
                        run.add("tool_result", txt)
        elif t == "result":
            secs = (ev.get("duration_ms") or 0) / 1000
            if ev.get("is_error"):
                raise RuntimeError(str(ev.get("result") or "Claude Code reported an error"))
            run.add("status", f"Claude Code finished this phase in {secs:.0f} s")
    proc.wait()
    err = proc.stderr.read().strip()
    if proc.returncode != 0:
        raise RuntimeError(err[-800:] or f"Claude Code exited with code {proc.returncode}")


def replay(run, phase):
    script = read_json(SKILLS[run.skill]["replay"], {})
    for ev in script.get(phase, []):
        time.sleep(float(ev.get("delay", 0.8)))
        if "write" in ev:
            write_json(ROOT / ev["write"]["path"], ev["write"]["json"])
        if ev.get("merge"):
            build_final_from_answers(run.skill)
        run.add(ev["kind"], ev.get("text", ""), **({"name": ev["name"]} if "name" in ev else {}))
        if ev.get("eval"):
            time.sleep(0.4)
            run.add("tool_result", eval_text(run.skill, SKILLS[run.skill]["final"]))


def build_final_from_answers(skill):
    """Deterministic merge of the draft and the human's answers (used by replay, and as a
    fallback if the live agent does not write its final report)."""
    cfg = SKILLS[skill]
    draft = read_json(cfg["draft"], {}) or {}
    questions = read_json(OUT / "questions.json", []) or []
    answers = {a["id"]: a for a in (read_json(OUT / "answers.json", []) or [])}
    by_ref = {q.get("ref"): q for q in questions}

    def apply(entry):
        e = dict(entry)
        q = by_ref.get(e.get("ref"))
        if q and q["id"] in answers:
            a = answers[q["id"]]
            e["human_decision"] = a.get("choice")
            e["human_comment"] = a.get("comment", "")
            e["status"] = "rejected" if a.get("choice") in q.get("reject_options", []) else "accepted"
        else:
            e["status"] = "accepted"
        return e

    final = dict(draft)
    for key in ("findings", "items", "proposed_requirements"):
        if isinstance(final.get(key), list):
            final[key] = [apply(x) for x in final[key]]
    write_json(cfg["final"], final)
    return final


def score(skill, path):
    data = read_json(path)
    if data is None:
        return None
    if skill == "gap-discovery":
        return EVAL_GAPS.score(data.get("findings", []) if isinstance(data, dict) else data)
    return EVAL_IMPACT.score(data)


def eval_text(skill, path):
    s = score(skill, path)
    if s is None:
        return "No report to score."
    lines = [f"Recall: {s['recall']:.0%} | Precision: {s['precision']:.0%} | Rejected by reviewer: {s['rejected']}"]
    lines += [f"MISSED: {m}" for m in s["missed"]]
    lines += [f"NEEDS HUMAN REVIEW: {e}" for e in s["extra"]]
    lines.append(f"Result: {s['verdict']}")
    return "\n".join(lines)


def phase1(run):
    cfg = SKILLS[run.skill]
    try:
        clear_outputs(cfg)
        if run.mode == "live":
            run_claude(run, cfg["prompt1"])
        else:
            replay(run, "phase1")
        qs = read_json(OUT / "questions.json", []) or []
        if qs:
            run.questions = qs
            run.status = "waiting_human"
            run.add("human", f"The agent is waiting for your decision on {len(qs)} item{'s' if len(qs) != 1 else ''}.")
        else:
            run.status = "done"
            run.add("status", "The agent asked no questions. Run complete.")
    except Exception as e:  # noqa: BLE001
        run.status, run.error = "error", str(e)
        run.add("error", str(e))


def phase2(run):
    cfg = SKILLS[run.skill]
    try:
        if run.mode == "live":
            run_claude(run, cfg["prompt2"], resume=run.session_id)
            if not Path(cfg["final"]).exists():
                build_final_from_answers(run.skill)
                run.add("status", "The agent did not write a final report, so the app assembled it from your decisions.")
        else:
            replay(run, "phase2")
        run.status = "done"
        run.add("status", "Run complete. Your decisions are in the review log.")
    except Exception as e:  # noqa: BLE001
        run.status, run.error = "error", str(e)
        run.add("error", str(e))


def submit_answers(run, answers):
    qmap = {q["id"]: q for q in run.questions}
    clean = [{"id": a["id"], "choice": a.get("choice", ""), "comment": a.get("comment", "").strip()}
             for a in answers if a.get("id") in qmap]
    write_json(OUT / "answers.json", clean)
    log = read_json(REVIEW_LOG, []) or []
    for a in clean:
        q = qmap[a["id"]]
        log.append({"time": now(), "run": run.id, "skill": run.skill, "mode": run.mode, "question": a["id"],
                    "ref": q.get("ref"), "ids": q.get("ids", []), "asked": q.get("question"),
                    "decision": a["choice"], "comment": a["comment"], "reviewer": REVIEWER})
    write_json(REVIEW_LOG, log)
    summary = "; ".join(f"{a['id']}: {a['choice']}" for a in clean)
    run.questions, run.status = [], "running"
    run.add("human", f"Decisions sent to the agent. {summary}")
    threading.Thread(target=phase2, args=(run,), daemon=True).start()


# ---------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            return self.static("index.html")
        if u.path.startswith("/static/"):
            return self.static(u.path[len("/static/"):])
        if u.path == "/api/status":
            return self.send_json({"claude": bool(CLAUDE_BIN), "claude_path": CLAUDE_BIN,
                                   "claude_version": CLAUDE_VERSION, "reviewer": REVIEWER})
        if u.path == "/api/data":
            d = CHECK.load()
            res = CHECK.analyze(d)
            cr = (ROOT / "data" / "change_request_CR-014.md").read_text()
            return self.send_json({**d, "ears": res["ears"], "cr": cr})
        if u.path.startswith("/api/run/"):
            run = RUNS.get(u.path.split("/")[3])
            if not run:
                return self.send_json({"error": "unknown run"}, 404)
            return self.send_json(run.view(int(q.get("since", ["0"])[0])))
        if u.path == "/api/report":
            skill = q.get("skill", ["gap-discovery"])[0]
            cfg = SKILLS.get(skill)
            if not cfg:
                return self.send_json({"error": "unknown skill"}, 400)
            return self.send_json({"draft": read_json(cfg["draft"]), "final": read_json(cfg["final"]),
                                   "draft_score": score(skill, cfg["draft"]), "final_score": score(skill, cfg["final"])})
        if u.path == "/api/review":
            return self.send_json(read_json(REVIEW_LOG, []) or [])
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/check":
            res = CHECK.analyze()
            write_json(OUT / "structural_gaps.json", res["gaps"])
            return self.send_json(res)
        if u.path == "/api/run":
            b = self.body()
            skill, mode = b.get("skill"), b.get("mode", "replay")
            if skill not in SKILLS:
                return self.send_json({"error": "unknown skill"}, 400)
            if mode == "live" and not CLAUDE_BIN:
                return self.send_json({"error": "Claude Code CLI not found. Use Replay, or set CLAUDE_BIN."}, 400)
            if active_run():
                return self.send_json({"error": "Another run is still in progress."}, 409)
            run = Run(skill, mode)
            with RUNS_LOCK:
                RUNS[run.id] = run
            threading.Thread(target=phase1, args=(run,), daemon=True).start()
            return self.send_json({"id": run.id})
        if u.path.startswith("/api/run/") and u.path.endswith("/answers"):
            run = RUNS.get(u.path.split("/")[3])
            if not run or run.status != "waiting_human":
                return self.send_json({"error": "This run is not waiting for answers."}, 409)
            submit_answers(run, self.body().get("answers", []))
            return self.send_json({"ok": True})
        if u.path == "/api/reset":
            if active_run():
                return self.send_json({"error": "A run is in progress."}, 409)
            for cfg in SKILLS.values():
                clear_outputs(cfg)
            for p in (OUT / "structural_gaps.json", REVIEW_LOG):
                if p.exists():
                    p.unlink()
            return self.send_json({"ok": True})
        self.send_json({"error": "not found"}, 404)

    def static(self, name):
        p = (STATIC / name).resolve()
        if not str(p).startswith(str(STATIC.resolve())) or not p.is_file():
            return self.send_json({"error": "not found"}, 404)
        types = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", types.get(p.suffix, "application/octet-stream") + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    OUT.mkdir(exist_ok=True)
    REVIEW_LOG.parent.mkdir(exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Requirements Agent demo running at http://localhost:{PORT}")
    print(f"Claude Code: {CLAUDE_BIN + ' (' + CLAUDE_VERSION + ')' if CLAUDE_BIN else 'not found - Replay mode only'}")
    print("Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
