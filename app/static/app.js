/* Requirements Agent demo UI. Vanilla JS, no build step. */
const $ = (s) => document.querySelector(s);
const state = {
  data: null, ears: {}, gaps: {}, tab: "trace", mode: "replay", claude: false,
  run: null, since: 0, answers: {}, humanShown: false, busy: false, onlyFlagged: false,
};

const TYPE_LABEL = {
  missing_child: "No child requirement", orphan: "No parent", missing_test: "No test",
  ears_violation: "Not EARS", conflict: "Conflict", ambiguous: "Not verifiable", impacted: "Affected by CR-014",
};
const SKILL_LABEL = { "gap-discovery": "Gap discovery", "impact-analysis": "Impact analysis · CR-014" };
const LEVEL = (id) => (id || "").split("-")[0];

/* ---------- utils ---------- */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const linkIds = (html) => html.replace(/\b(DDS|DID|SRS|TC)-\d{3}\b/g, (m) => `<a class="ref" data-ref="${m}">${m}</a>`);
const rich = (s) => linkIds(esc(s));
const earsHtml = (s) => esc(s).replace(/\b(When|While|If|then|Where|shall)\b/g, '<span class="kw">$1</span>');
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `Request failed (${r.status})`);
  return j;
}
function addGap(ids, type) {
  for (const id of ids || []) (state.gaps[id] ||= new Set()).add(type);
}

/* ---------- explorer ---------- */
function testsFor(srsId) { return state.data.tests.filter((t) => t.verifies === srsId); }

function reqRow(r) {
  const lv = LEVEL(r.id);
  const gaps = [...(state.gaps[r.id] || [])];
  const pattern = state.ears[r.id];
  const tags = [];
  if (lv !== "TC") tags.push(pattern ? `<span class="tag ears">${esc(pattern)}</span>` : `<span class="tag noears">Not EARS</span>`);
  for (const g of gaps) if (!(g === "ears_violation" && !pattern)) tags.push(`<span class="tag g">${esc(TYPE_LABEL[g] || g)}</span>`);
  let tcs = "";
  if (lv === "SRS") {
    const t = testsFor(r.id);
    tcs = `<div class="tcs">${t.length ? t.map((x) => `<span class="tc" title="${esc(x.title)}">${x.id}</span>`).join("") : '<span class="tc none">no test</span>'}</div>`;
  }
  return `<div class="req${gaps.length ? " gap" : ""}" id="row-${r.id}">
    <span class="rid lv-${lv}">${r.id}</span>
    <div class="rtext"><div class="rtitle">${esc(r.title)}</div><div class="rbody">${earsHtml(r.text)}</div>${tcs}</div>
    <div class="tags">${tags.join("")}</div></div>`;
}

function flagged(id) {
  const d = state.data;
  if (state.gaps[id]) return true;
  const kids = [...d.did.filter((x) => x.parent === id), ...d.srs.filter((x) => x.parent === id)];
  return kids.some((k) => flagged(k.id));
}
function renderTrace() {
  const d = state.data;
  const ddsIds = new Set(d.dds.map((x) => x.id));
  const didIds = new Set(d.did.map((x) => x.id));
  const show = (id) => !state.onlyFlagged || flagged(id);
  let h = "";
  for (const a of d.dds.filter((x) => show(x.id))) {
    h += `<div class="node">${reqRow(a)}<div class="kids">`;
    for (const b of d.did.filter((x) => x.parent === a.id && show(x.id))) {
      h += `<div class="node">${reqRow(b)}<div class="kids">`;
      for (const c of d.srs.filter((x) => x.parent === b.id && show(x.id))) h += `<div class="node">${reqRow(c)}</div>`;
      h += `</div></div>`;
    }
    h += `</div></div>`;
  }
  if (state.onlyFlagged && !h) h = `<p class="muted">Nothing flagged yet. Run step 1, 2 or 3.</p>`;
  const orphans = [...d.did.filter((x) => !ddsIds.has(x.parent)), ...d.srs.filter((x) => !didIds.has(x.parent))].filter((x) => show(x.id));
  if (orphans.length) {
    h += `<div class="section-label">Not traced to a parent</div>`;
    for (const o of orphans) h += `<div class="node">${reqRow(o)}</div>`;
  }
  return h;
}

function renderTable(level) {
  const d = state.data;
  if (level === "tests") {
    return `<table class="grid"><tr><th>ID</th><th>Verifies</th><th>Test</th></tr>${d.tests.map((t) =>
      `<tr id="row-${t.id}"><td><span class="rid lv-TC">${t.id}</span></td><td>${rich(t.verifies)}</td><td>${esc(t.title)}</td></tr>`).join("")}</table>`;
  }
  const rows = d[level];
  const childLevel = level === "dds" ? "did" : level === "did" ? "srs" : null;
  const head = `<tr><th style="width:84px">ID</th>${level !== "dds" ? '<th style="width:84px">Parent</th>' : ""}<th>Requirement</th><th style="width:150px">EARS</th><th style="width:150px">${childLevel ? "Children" : "Tests"}</th></tr>`;
  const body = rows.map((r) => {
    const kids = childLevel ? d[childLevel].filter((x) => x.parent === r.id).map((x) => x.id) : testsFor(r.id).map((x) => x.id);
    const gaps = state.gaps[r.id];
    const p = state.ears[r.id];
    return `<tr id="row-${r.id}" class="${gaps ? "gap" : ""}"><td><span class="rid lv-${LEVEL(r.id)}">${r.id}</span></td>
      ${level !== "dds" ? `<td>${r.parent ? rich(r.parent) : '<span class="tag noears">none</span>'}</td>` : ""}
      <td><div class="rtitle">${esc(r.title)}</div><div class="rbody">${earsHtml(r.text)}</div></td>
      <td>${p ? `<span class="tag ears">${esc(p)}</span>` : '<span class="tag noears">Not EARS</span>'}</td>
      <td>${kids.length ? rich(kids.join(", ")) : '<span class="tag g">none</span>'}</td></tr>`;
  }).join("");
  return `<table class="grid">${head}${body}</table>`;
}

function renderExplorer() {
  if (!state.data) return;
  const d = state.data;
  $("#counts").textContent = `${d.dds.length} DDS · ${d.did.length} DID · ${d.srs.length} SRS · ${d.tests.length} tests`;
  $("#explorer").innerHTML = state.tab === "trace" ? renderTrace() : renderTable(state.tab);
}

function jump(id) {
  const lv = LEVEL(id);
  if (lv === "TC" && state.tab !== "tests") { state.tab = "tests"; syncTabs(); renderExplorer(); }
  else if (lv !== "TC" && state.tab === "tests") { state.tab = "trace"; syncTabs(); renderExplorer(); }
  const el = document.getElementById(`row-${id}`);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
}
function syncTabs() { document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === state.tab)); }

/* ---------- agent panel ---------- */
function startBlock(title) {
  $("#empty").style.display = "none";
  $("#feed").innerHTML = `<div class="run-head"><b>${esc(title)}</b><span class="badge running" id="run-badge">running</span></div><div id="events"></div>`;
  $("#human").innerHTML = ""; $("#results").innerHTML = "";
}
function setBadge(status) {
  const b = $("#run-badge"); if (!b) return;
  const label = { running: "running", waiting_human: "waiting for you", done: "done", error: "error" }[status] || status;
  b.className = `badge ${status}`; b.textContent = label;
}
/* One-line summary for a tool call; the full text stays available in an expander. */
function toolSummary(e) {
  const t = String(e.text || "");
  if (e.name !== "Bash") return t;
  const wrote = [...t.matchAll(/>\s*(outputs\/[\w./-]+)/g)].map((m) => m[1]);
  if (wrote.length) return `Wrote ${[...new Set(wrote)].join(", ")}`;
  const first = t.split("\n")[0];
  return first.length > 90 || t.includes("\n") ? first.slice(0, 90) + "…" : t;
}
function addEvent(e) {
  const box = $("#events"); if (!box) return;
  const icon = { text: "AI", tool: "›", tool_result: "", human: "You", error: "!", status: "·" }[e.kind] ?? "·";
  let body;
  if (e.kind === "tool") {
    const sum = toolSummary(e);
    const full = String(e.text || "");
    body = `<span class="toolname">${esc(e.name || "Tool")}</span>` + (sum === full
      ? `<span class="mono">${rich(sum)}</span>`
      : `<details class="fold"><summary class="mono">${esc(sum)}</summary><pre class="out">${rich(full)}</pre></details>`);
  } else if (e.kind === "tool_result") {
    body = e.open ? `<pre class="out">${rich(e.text)}</pre>`
      : `<details class="fold"><summary class="muted">Output (${String(e.text).split("\n").length} lines)</summary><pre class="out">${rich(e.text)}</pre></details>`;
  }
  else if (e.kind === "status") body = `<span class="muted">${rich(e.text)}</span>`;
  else body = rich(e.text);
  const div = document.createElement("div");
  div.className = `ev ${e.kind}`;
  div.innerHTML = `<span class="ic">${icon === "AI" || icon === "You" ? "" : esc(icon)}</span><div class="body">${body}</div>`;
  box.appendChild(div);
  const sc = $("#agent-scroll");
  sc.scrollTop = sc.scrollHeight;
}
function setBusy(b, which) {
  state.busy = b;
  ["#btn-check", "#btn-gap", "#btn-impact", "#btn-reset"].forEach((s) => ($(s).disabled = b));
  document.querySelectorAll(".step").forEach((s) => s.classList.remove("running"));
  if (b && which) $(which).classList.add("running");
}

async function runChecks() {
  startBlock("Scripted checks");
  setBusy(true, "#btn-check");
  addEvent({ kind: "tool", name: "Bash", text: "python3 scripts/check_trace.py" });
  try {
    const res = await api("/api/check", {});
    state.gaps = {};
    for (const g of res.gaps) addGap(g.ids, g.type);
    const ok = Object.values(res.ears).filter(Boolean).length;
    addEvent({ kind: "tool_result", open: true, text: `EARS syntax: ${ok} of ${Object.keys(res.ears).length} requirements match a pattern\n` +
      res.gaps.map((g) => `- ${g.type}: ${g.ids.join(", ")} (${g.detail})`).join("\n") + `\n\nStructural gaps found: ${res.gaps.length}` });
    addEvent({ kind: "status", text: "Deterministic: same input, same output. Gaps are marked in the explorer. Conflicts and vague wording need step 2." });
    setBadge("done");
    renderExplorer();
  } catch (e) { addEvent({ kind: "error", text: e.message }); setBadge("error"); }
  setBusy(false);
}

async function startRun(skill, btn) {
  startBlock(`${SKILL_LABEL[skill]} · ${state.mode === "live" ? "Live (Claude Code)" : "Replay"}`);
  setBusy(true, btn);
  state.answers = {}; state.humanShown = false; state.since = 0;
  try {
    const r = await api("/api/run", { skill, mode: state.mode });
    state.run = { id: r.id, skill };
    poll();
  } catch (e) { addEvent({ kind: "error", text: e.message }); setBadge("error"); setBusy(false); }
}

async function poll() {
  if (!state.run) return;
  let v;
  try { v = await api(`/api/run/${state.run.id}?since=${state.since}`); }
  catch (e) { setTimeout(poll, 1500); return; }
  for (const e of v.events) addEvent(e);
  state.since = v.next;
  setBadge(v.status);
  if (v.status === "waiting_human" && !state.humanShown) { state.humanShown = true; renderHuman(v.questions); }
  if (v.status === "done") { setBusy(false); await renderResults(state.run.skill); return; }
  if (v.status === "error") { setBusy(false); return; }
  setTimeout(poll, v.status === "waiting_human" ? 1500 : 600);
}

/* ---------- human in the loop ---------- */
function renderHuman(questions) {
  const qs = questions.map((q) => `
    <div class="q" id="q-${q.id}">
      <div class="q-top"><span class="q-id">${esc(q.id)}</span><span class="q-title">${esc(q.title || "Decision")}</span><span class="muted">${rich((q.ids || []).join(", "))}</span></div>
      <div class="q-text">${rich(q.question)}</div>
      ${q.proposal ? `<div class="proposal"><span class="lab">Proposed text (EARS)</span>${earsHtml(q.proposal)}</div>` : ""}
      <div class="opts">${q.options.map((o) => `<button class="opt${(q.reject_options || []).includes(o) ? " rej" : ""}" data-q="${esc(q.id)}" data-o="${esc(o)}">${esc(o)}</button>`).join("")}</div>
      <textarea placeholder="Comment, or type your own resolution here if none of the options fit (saved to the review log)" data-c="${esc(q.id)}"></textarea>
    </div>`).join("");
  $("#human").innerHTML = `<div class="hitl">
    <div class="hitl-head"><span class="dot"></span><b>Human input needed</b><span class="muted">The agent has paused. Nothing is final until you decide.</span></div>
    ${qs}
    <div class="hitl-foot"><span class="muted" id="hitl-count">0 of ${questions.length} answered</span><button class="primary" id="btn-send" disabled>Send decisions to the agent</button></div>
  </div>`;
  const OTHER = "Other (own resolution, see comment)";
  const refresh = () => {
    let n = 0;
    for (const q of questions) {
      const box = $(`#q-${CSS.escape(q.id)}`);
      const typed = box.querySelector("textarea").value.trim();
      const answered = !!(state.answers[q.id]?.choice || typed);
      box.classList.toggle("answered", answered);
      if (answered) n++;
    }
    $("#hitl-count").textContent = `${n} of ${questions.length} answered`;
    $("#btn-send").disabled = n < questions.length;
  };
  $("#human").querySelectorAll(".opt").forEach((b) => b.addEventListener("click", () => {
    const q = b.dataset.q;
    state.answers[q] = { ...(state.answers[q] || {}), choice: b.dataset.o };
    $(`#q-${CSS.escape(q)}`).querySelectorAll(".opt").forEach((x) => x.classList.toggle("sel", x === b));
    refresh();
  }));
  $("#human").querySelectorAll("textarea").forEach((t) => t.addEventListener("input", refresh));
  $("#btn-send").addEventListener("click", async () => {
    $("#btn-send").disabled = true;
    const answers = questions.map((q) => ({ id: q.id, choice: state.answers[q.id]?.choice || OTHER, comment: $(`textarea[data-c="${CSS.escape(q.id)}"]`).value }));
    try { await api(`/api/run/${state.run.id}/answers`, { answers }); $("#human").innerHTML = ""; }
    catch (e) { addEvent({ kind: "error", text: e.message }); $("#btn-send").disabled = false; }
  });
  const sc = $("#agent-scroll"); sc.scrollTop = sc.scrollHeight;
}

/* ---------- results ---------- */
function status(e) {
  const s = e.status || "draft";
  const label = { accepted: "accepted", rejected: "rejected", draft: "draft" }[s] || s;
  const dec = e.human_decision ? `<div class="conf">${esc(e.human_decision)}${e.human_comment ? ` · “${esc(e.human_comment)}”` : ""}</div>` : "";
  return `<td class="st"><span class="${s}">${label}</span>${dec}</td>`;
}
function scoreCard(label, s) {
  if (!s) return `<div class="score"><div class="lab">${label}</div><div class="small">No report</div></div>`;
  const pass = s.verdict === "PASS";
  return `<div class="score ${pass ? "pass" : "review"}"><div class="lab">${label}</div>
    <div class="nums"><div><div class="big">${Math.round(s.recall * 100)}%</div><div class="small">recall</div></div>
    <div><div class="big">${Math.round(s.precision * 100)}%</div><div class="small">precision</div></div></div>
    <div class="verdict">${pass ? "PASS" : "Review required"}</div>
    ${s.missed.length || s.extra.length ? `<ul>${s.missed.map((m) => `<li>Missed: ${rich(m)}</li>`).join("")}${s.extra.map((m) => `<li>Not in known set: ${rich(m)}</li>`).join("")}</ul>` : ""}</div>`;
}
async function renderResults(skill) {
  let rep;
  try { rep = await api(`/api/report?skill=${skill}`); } catch (e) { return; }
  const r = rep.final || rep.draft;
  if (!r) return;
  let h = "";
  if (skill === "gap-discovery") {
    for (const f of r.findings || []) if (f.status !== "rejected") addGap(f.ids, f.type);
    h += `<div class="card"><h4>Findings</h4><table class="find"><tr><th>Ref</th><th>Type</th><th>IDs</th><th>Evidence</th><th>Conf.</th><th>Status</th></tr>
      ${(r.findings || []).map((f) => `<tr class="${f.status || ""}"><td>${esc(f.ref)}</td><td>${esc(TYPE_LABEL[f.type] || f.type)}</td><td>${rich((f.ids || []).join(", "))}</td>
      <td>${rich(f.evidence)}${f.proposed_text ? `<div class="proposal"><span class="lab">Proposed EARS text</span>${earsHtml(f.proposed_text)}</div>` : ""}</td>
      <td class="conf ${esc(f.confidence)}">${esc(f.confidence)}</td>${status(f)}</tr>`).join("")}</table></div>`;
  } else {
    for (const i of r.items || []) if (i.status !== "rejected") addGap([i.id], "impacted");
    h += `<div class="card"><h4>Affected requirements</h4><table class="find"><tr><th>Ref</th><th>ID</th><th>Level</th><th>Why</th><th>Conf.</th><th>Status</th></tr>
      ${(r.items || []).map((i) => `<tr class="${i.status || ""}"><td>${esc(i.ref)}</td><td>${rich(i.id)}</td><td>${esc(i.level)}</td><td>${rich(i.rationale)}</td><td class="conf ${esc(i.confidence)}">${esc(i.confidence)}</td>${status(i)}</tr>`).join("")}</table></div>`;
    if ((r.proposed_requirements || []).length) h += `<div class="card"><h4>Proposed new requirements</h4><table class="find"><tr><th>Ref</th><th>Parent</th><th>Text (EARS)</th><th>Status</th></tr>
      ${r.proposed_requirements.map((p) => `<tr class="${p.status || ""}"><td>${esc(p.ref)}</td><td>${rich(p.parent)}</td><td>${earsHtml(p.text)}</td>${status(p)}</tr>`).join("")}</table></div>`;
    if ((r.tests || []).length) h += `<div class="card"><h4>Tests to update</h4><table class="find"><tr><th>Test</th><th>Verifies</th><th>Action</th></tr>
      ${r.tests.map((t) => `<tr><td>${rich(t.id)}</td><td>${rich(t.verifies)}</td><td>${esc(t.action || "")}</td></tr>`).join("")}</table></div>`;
  }
  h += `<div class="card"><h4>Scored against known answers</h4><div class="muted">Rejected items are not counted. The known-answer set is in eval/golden/.</div>
    <div class="scores">${scoreCard("Before human review", rep.draft_score)}${scoreCard("After human review", rep.final_score)}</div></div>`;
  $("#results").innerHTML = h;
  renderExplorer();
  $("#results").scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- review log ---------- */
async function openLog() {
  const log = await api("/api/review").catch(() => []);
  $("#drawer-body").innerHTML = log.length ? `<table class="find"><tr><th>Time (UTC)</th><th>Run</th><th>Q</th><th>IDs</th><th>Decision</th><th>Comment</th><th>Reviewer</th></tr>
    ${log.slice().reverse().map((x) => `<tr><td class="mono">${esc(x.time.replace("T", " ").replace("+00:00", ""))}</td><td>${esc(SKILL_LABEL[x.skill] || x.skill)}<div class="conf">${esc(x.mode)}</div></td>
    <td>${esc(x.question)}</td><td>${rich((x.ids || []).join(", "))}</td><td>${esc(x.decision)}</td><td>${esc(x.comment)}</td><td>${esc(x.reviewer)}</td></tr>`).join("")}</table>`
    : `<p class="muted">No decisions recorded yet.</p>`;
  $("#drawer").classList.remove("hidden");
}

/* ---------- wiring ---------- */
function setMode(m) {
  state.mode = m;
  document.querySelectorAll("#mode button").forEach((b) => b.classList.toggle("on", b.dataset.mode === m));
}
document.addEventListener("click", (e) => {
  const a = e.target.closest("a.ref");
  if (a) { e.preventDefault(); jump(a.dataset.ref); }
});
document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => { state.tab = b.dataset.tab; syncTabs(); renderExplorer(); }));
document.querySelectorAll("#mode button").forEach((b) => b.addEventListener("click", () => { if (!b.disabled) setMode(b.dataset.mode); }));
$("#only-flagged").addEventListener("change", (e) => { state.onlyFlagged = e.target.checked; renderExplorer(); });
$("#btn-check").addEventListener("click", runChecks);
$("#btn-gap").addEventListener("click", () => startRun("gap-discovery", "#btn-gap"));
$("#btn-impact").addEventListener("click", () => startRun("impact-analysis", "#btn-impact"));
$("#btn-log").addEventListener("click", openLog);
$("#drawer-close").addEventListener("click", () => $("#drawer").classList.add("hidden"));
$("#drawer").addEventListener("click", (e) => { if (e.target.id === "drawer") $("#drawer").classList.add("hidden"); });
$("#btn-reset").addEventListener("click", async () => {
  try { await api("/api/reset", {}); } catch (e) { alert(e.message); return; }
  state.gaps = {}; state.run = null;
  $("#feed").innerHTML = ""; $("#human").innerHTML = ""; $("#results").innerHTML = ""; $("#empty").style.display = "";
  renderExplorer();
});

(async function init() {
  try {
    const s = await api("/api/status");
    state.claude = s.claude;
    const pill = $("#claude-status");
    if (s.claude) { pill.className = "pill ok"; pill.textContent = `Claude Code ${s.claude_version}`; pill.title = s.claude_path; setMode("live"); }
    else {
      pill.className = "pill warn"; pill.textContent = "Claude Code CLI not found · Replay only";
      $('#mode button[data-mode="live"]').disabled = true; setMode("replay");
    }
    const d = await api("/api/data");
    state.data = d; state.ears = d.ears;
    renderExplorer();
  } catch (e) {
    $("#explorer").innerHTML = `<p style="color:#b42318">Could not load data: ${esc(e.message)}</p>`;
  }
})();
