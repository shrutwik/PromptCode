const parts = location.pathname.split("/").filter(Boolean);
const sessionId = parts[1];
let activeTab = "overview";
let ringAnimated = false;
const reducedMotion = () => !!(window.PCUI && PCUI.reducedMotion && PCUI.reducedMotion());

/* Event type names unchanged — calibration depends on these strings */
const GROUPS = {
  Exploration: ["session_started", "file_viewed", "file_searched"],
  AI: ["ai_prompt", "ai_response", "ai_edit_proposed", "ai_edit_accepted", "ai_edit_modified", "ai_edit_rejected"],
  Coding: ["file_changed"],
  Testing: ["test_run", "test_result", "benchmark_run"],
  Recovery: ["change_reverted"],
  Submission: ["final_diff_viewed", "submission", "defend_answer"],
};

const PHASE_COLOR = {
  Exploration: "var(--pc-phase-exploration)",
  AI: "var(--pc-phase-ai)",
  Coding: "var(--pc-phase-coding)",
  Testing: "var(--pc-phase-testing)",
  Recovery: "var(--pc-phase-recovery)",
  Submission: "var(--pc-phase-submission)",
  Other: "var(--pc-faint)",
};

function eventPhase(type) {
  for (const [name, types] of Object.entries(GROUPS)) {
    if (types.includes(type)) return name;
  }
  return "Other";
}

function groupTimeline(events) {
  const used = new Set();
  const out = {};
  for (const [name, types] of Object.entries(GROUPS)) {
    out[name] = events.filter((e) => types.includes(e.event_type));
    out[name].forEach((e) => used.add(e.id));
  }
  out.Other = events.filter((e) => !used.has(e.id));
  return out;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function parseTs(v) {
  if (!v) return 0;
  const s = String(v);
  // Naive ISO timestamps from the API are UTC; append Z so scrubber timing is correct.
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(s) ? s : s + "Z";
  const t = Date.parse(normalized);
  return Number.isFinite(t) ? t : 0;
}

function fmtDuration(ms) {
  if (!ms || ms < 0) return "—";
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return m ? `${m}m ${s}s` : `${s}s`;
}

function compactLabel(e) {
  const p = e.payload || {};
  const t = e.event_type;
  if (t === "file_viewed" || t === "file_changed" || t === "file_searched") return p.path || p.query || t;
  if (t === "test_run" || t === "test_result") return p.ok === false || p.failed ? "tests failed" : (p.ok ? "tests passed" : t);
  if (t.startsWith("ai_")) return t.replace(/^ai_/, "AI ");
  if (t === "change_reverted") return `revert ${p.path || ""}`.trim();
  return t;
}

function detailFor(e) {
  const p = e.payload || {};
  const t = e.event_type;
  let title = t;
  let body = "";
  if (t === "file_viewed" || t === "file_changed" || t === "change_reverted") {
    title = p.path || t;
    body = `<p class="muted">${esc(t)}</p>${p.summary ? `<pre>${esc(p.summary)}</pre>` : ""}`;
  } else if (t.startsWith("ai_")) {
    title = t;
    const text = p.message || p.prompt || JSON.stringify(p, null, 2);
    body = `<p class="muted">Expand only when needed</p><details><summary class="muted">Show AI payload</summary><pre>${esc(text)}</pre></details>`;
  } else if (t === "test_run" || t === "test_result") {
    title = "Test run";
    body = `<p>${p.ok ? "Passed" : "Failed"} · ${esc(p.command || "")}</p>
      <pre>${esc(JSON.stringify(p.counts || p, null, 2))}</pre>`;
  } else {
    body = `<pre>${esc(JSON.stringify(p, null, 2))}</pre>`;
  }
  return { title, body, phase: eventPhase(t) };
}

/** Link AI accepted → fail → revert → pass only when sequence is present */
function findRecoverySequences(events) {
  const sorted = [...events].sort((a, b) => parseTs(a.created_at) - parseTs(b.created_at));
  const seqs = [];
  for (let i = 0; i < sorted.length; i++) {
    const a = sorted[i];
    if (a.event_type !== "ai_edit_accepted" && a.event_type !== "ai_edit_modified") continue;
    let fail = null, revert = null, pass = null;
    for (let j = i + 1; j < Math.min(i + 12, sorted.length); j++) {
      const e = sorted[j];
      if (!fail && (e.event_type === "test_result" || e.event_type === "test_run") && (e.payload?.ok === false || (e.payload?.counts?.failed || 0) > 0)) fail = e;
      else if (fail && !revert && e.event_type === "change_reverted") revert = e;
      else if (revert && !pass && (e.event_type === "test_result" || e.event_type === "test_run") && e.payload?.ok === true) {
        pass = e;
        seqs.push([a, fail, revert, pass]);
        break;
      }
    }
  }
  return seqs;
}

async function load() {
  const [r, sessionMeta] = await Promise.all([
    InterviewAPI.report(sessionId),
    InterviewAPI.getSession(sessionId).catch(() => null),
  ]);
  let defendState = { questions: r.defend_questions || [], answers: {} };
  try {
    defendState = await InterviewAPI.defend(sessionId);
  } catch (_) {}

  const events = r.timeline || [];
  const toneFor = (pct) => (pct >= 70 ? "success" : pct >= 40 ? "warn" : "danger");
  const rubricHtml = Object.entries(r.rubric || {}).map(([k, v], i) => {
    const pct = v.max ? (Number(v.score) / Number(v.max)) * 100 : 0;
    const label = k.replace(/^[A-Z]_/, "").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()).replace(/\bAi\b/, "AI");
    return `<div class="rubric-row"><div><div class="name">${esc(label)}</div>
      <div class="evidence">${esc(v.evidence || "")}</div></div>
      ${PCUI.bar(pct, toneFor(pct), 200 + i * 70)}
      <div class="v">${esc(v.score)}/${esc(v.max)}</div></div>`;
  }).join("") || `<div class="pc-panel-body muted">No rubric scores</div>`;

  const grouped = groupTimeline(events);
  const phases = Object.keys(GROUPS);
  const sequences = findRecoverySequences(events);
  const seqNote = sequences.length
    ? `<div class="timeline-seq">${sequences.length} linked recovery path${sequences.length > 1 ? "s" : ""}: AI accept → fail → revert → pass</div>`
    : "";

  const timelineListHtml = Object.entries(grouped).map(([name, items]) => {
    if (!items.length) return "";
    return `<div class="timeline-group" data-phase="${esc(name)}"><h3>${esc(name)} · ${items.length}</h3>${items.map((e) => {
      const short = compactLabel(e);
      return `<div class="timeline-item" data-id="${esc(e.id)}" data-phase="${esc(name)}" tabindex="0" role="button">
        <div class="t" title="${esc(e.created_at)}">${esc(String(e.created_at || "").slice(11, 19))}</div>
        <div><strong>${esc(e.event_type)}</strong> <span class="muted">${esc(short)}</span></div>
      </div>`;
    }).join("")}</div>`;
  }).join("");

  const q = defendState.questions || [];
  const answers = defendState.answers || {};
  const nextIdx = q.findIndex((_, i) => answers[String(i)] == null && answers[i] == null);
  const answeredCount = q.filter((_, i) => answers[String(i)] != null || answers[i] != null).length;
  const defendHtml = q.map((item, i) => {
    const question = item.question || item;
    const answered = answers[String(i)] ?? answers[i];
    const active = nextIdx === i;
    if (answered != null) {
      return `<div class="pc-panel defend-card"><div class="pc-row"><span class="defend-progress">Question ${i + 1} / ${q.length}</span><span class="tag" data-tone="success">Answered</span></div><h3>Q${i + 1}</h3><p>${esc(question)}</p>
        <div class="defend-answer">${esc(answered)}</div></div>`;
    }
    if (!active) {
      return `<div class="pc-panel defend-card is-locked"><span class="defend-progress">Locked</span><h3>Q${i + 1}</h3><p class="muted">Answer the previous question first.</p></div>`;
    }
    return `<div class="pc-panel defend-card"><div class="pc-row"><span class="defend-progress">Question ${i + 1} / ${q.length} · ${answeredCount} answered</span><span class="tag" data-tone="info">Current</span></div><h3>Q${i + 1} of ${q.length}</h3><p>${esc(question)}</p>
      <form id="defendForm">
        <div class="pc-field"><label for="defendAnswer">Your answer</label><textarea id="defendAnswer" name="answer" required></textarea></div>
        <div class="pc-row">
          <button class="btn btn-primary" id="defendSubmit" type="submit">Submit answer</button>
          <a class="btn btn-ghost" href="/session/${sessionId}">Review code</a>
        </div>
      </form></div>`;
  }).join("") || `<div class="pc-empty"><h3>No defend questions</h3><p>This session has no follow-up questions.</p></div>`;

  const signals = (r.signals || []).map((s) =>
    `<li><strong>${esc(s.type)}</strong> (${esc(s.strength)}/${esc(s.confidence)}) — ${esc(s.explanation)}</li>`
  ).join("") || "<li class='muted'>None</li>";

  const diff = r.diff_summary;
  const fileEvents = new Set();
  events.forEach((e) => {
    const path = e.payload?.path;
    if (path) fileEvents.add(path);
  });
  const diffMeta = diff ? `${esc(diff.file_count)} files · <span class="diff-stat-add">+${esc(diff.additions)}</span> / <span class="diff-stat-del">-${esc(diff.deletions)}</span>` : "";
  const diffHtml = diff && (diff.files_changed || []).length
    ? `<table class="pc-table">
        <thead><tr><th scope="col">File</th><th scope="col" class="num">Added</th><th scope="col" class="num">Removed</th><th scope="col"><span class="sr-only">Timeline</span></th></tr></thead>
        <tbody data-stagger>${(diff.files_changed || []).slice(0, 20).map((f) => {
          const linked = fileEvents.has(f.path);
          return `<tr><td class="mono">${esc(f.path)}</td><td class="num diff-stat-add">+${esc(f.additions)}</td><td class="num diff-stat-del">-${esc(f.deletions)}</td>
            <td class="actions">${linked ? `<button type="button" class="btn btn-ghost btn-sm js-diff-file" data-path="${esc(f.path)}">Timeline</button>` : ""}</td></tr>`;
        }).join("")}</tbody></table>`
    : `<div class="pc-panel-body muted">${diff ? "No files changed." : `<a href="/session/${sessionId}">Open workspace</a> → Review changes`}</div>`;
  const listOr = (items, empty) =>
    `<ul class="pc-list">${(items || []).map((i) => `<li>${esc(i)}</li>`).join("") || `<li class="muted">${empty}</li>`}</ul>`;

  const durationMs = (() => {
    if (!events.length) return 0;
    const times = events.map((e) => parseTs(e.created_at)).filter(Boolean);
    return times.length ? Math.max(...times) - Math.min(...times) : 0;
  })();
  const status = r.status || (r.test_summary?.ok ? "submitted" : "submitted");
  const slug = r.challenge_slug || sessionMeta?.challenge_slug || "";
  const challengeTitle = r.challenge_title || (slug ? slug.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase()) : "Session");

  const target = Math.max(0, Math.min(100, Number(r.total_score) || 0));
  const ringTone = target >= 70 ? "var(--pc-success)" : target >= 40 ? "var(--pc-warn)" : "var(--pc-danger)";
  const testsOk = !!r.test_summary?.ok;
  const steps = r.steps || (r.metrics && r.metrics.steps) || null;
  const prev = r.previous_attempt || null;
  const rubricLabel = (k) => k.replace(/^[A-Z]_/, "").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()).replace(/\bAi\b/, "AI");
  const scoreCell = (field) => (field && field.score != null ? `${field.score}/${field.max}` : "—");
  const compareRows = Object.keys(r.rubric || {}).map((k) => {
    const cur = r.rubric[k] || {};
    const old = (prev && prev.rubric && prev.rubric[k]) || {};
    return `<tr><td>${esc(rubricLabel(k))}</td><td>${esc(scoreCell(cur))}</td><td>${prev ? esc(scoreCell(old)) : "—"}</td></tr>`;
  }).join("");
  const stepCell = (value) => (value && value.opened != null ? `${value.opened} of ${value.total}` : "—");
  const compareHtml = `<section class="pc-panel" aria-labelledby="compareTitle">
    <div class="pc-panel-head"><h2 id="compareTitle">This attempt and the previous one</h2></div>
    <div class="pc-panel-body">
      <p>${prev ? "Same task, same scoring version." : "This attempt is the baseline."}</p>
      <table class="compare-table">
        <thead><tr><th>Field</th><th>This attempt</th><th>Previous</th></tr></thead>
        <tbody>
          <tr><td>Steps</td><td>${esc(stepCell(steps))}</td><td>${prev ? esc(stepCell(prev.steps)) : "—"}</td></tr>
          ${compareRows}
          <tr><td>Total</td><td>${esc(r.total_score)}</td><td>${prev ? esc(prev.total_score) : "—"}</td></tr>
        </tbody>
      </table>
    </div>
  </section>`;
  const TABS = [["overview", "Overview"], ["timeline", "Timeline"], ["code", "Code"], ["defend", "Defend"]];
  const tabBtn = ([key, label]) =>
    `<button type="button" role="tab" id="tab-${key}" aria-controls="panel-${key}" aria-selected="${key === activeTab}" tabindex="${key === activeTab ? 0 : -1}"${key === activeTab ? ' class="is-active"' : ""} data-tab="${key}">${label}</button>`;
  const panelAttrs = (key) =>
    `class="report-panel pc-tabpanel" data-panel="${key}" role="tabpanel" id="panel-${key}" aria-labelledby="tab-${key}" tabindex="0"${key === activeTab ? "" : " hidden"}`;

  const main = document.getElementById("main");
  main.removeAttribute("aria-busy");
  main.innerHTML = `
    <a class="page-back" href="/session/${sessionId}">← Workspace</a>
    <section class="pc-panel report-hero" aria-label="Score summary">
      <div class="pc-score-ring" id="scoreRing" style="--pc-score:${target};--pc-ring-color:${ringTone}" role="img" aria-label="Score ${Math.round(target)} out of 100">${reducedMotion() ? Math.round(target) : 0}</div>
      <div>
        <span class="pc-eyebrow">Session report</span>
        <h1 class="page-title">${esc(challengeTitle)}</h1>
        <div class="report-hero-meta">
          <span class="tag">${Math.round(target)} / 100</span>
          <span class="tag">${esc(fmtDuration(durationMs))}</span>
          <span class="tag" data-tone="${status === "submitted" ? "success" : "idle"}">${esc(status)}</span>
          <span class="tag" data-tone="${testsOk ? "success" : "danger"}">advisory tests ${testsOk ? "passed" : "failed"}</span>
          ${steps ? `<span class="tag">Steps ${esc(steps.opened)} of ${esc(steps.total)}</span>` : ""}
          <span class="tag">hidden tests not leaked</span>
        </div>
        <p class="report-hero-note">Advisory practice feedback only. Execution results do not establish correctness or an authoritative score. ${events.length} logged events across ${phases.filter((p) => (grouped[p] || []).length).length} workflow categories.</p>
      </div>
    </section>

    <div class="report-tabs" role="tablist" aria-label="Report sections">${TABS.map(tabBtn).join("")}</div>

    <div ${panelAttrs("overview")}>
      ${compareHtml}
      <section class="pc-panel" aria-labelledby="rubricTitle">
        <div class="pc-panel-head"><h2 id="rubricTitle">Category scores</h2></div>
        ${rubricHtml}
      </section>
      <div class="report-grid">
        <section class="pc-panel"><div class="pc-panel-head"><h3>Strengths</h3></div><div class="pc-panel-body">${listOr(r.went_well, "None noted")}</div></section>
        <section class="pc-panel"><div class="pc-panel-head"><h3>Improvements</h3></div><div class="pc-panel-body">${listOr(r.improve, "None noted")}</div></section>
        <section class="pc-panel"><div class="pc-panel-head"><h3>Recovery</h3></div><div class="pc-panel-body">${listOr(r.recovery_moments, "None")}${seqNote}</div></section>
        <section class="pc-panel"><div class="pc-panel-head"><h3>Behavioral signals</h3></div><div class="pc-panel-body"><ul class="pc-list">${signals}</ul></div></section>
      </div>
      <section class="pc-panel" id="feedbackBox" aria-labelledby="fbTitle">
        <div class="pc-panel-head"><h3 id="fbTitle">Quick feedback <span class="muted" style="font-weight:400">(optional)</span></h3><span class="section-meta">Does not change your score</span></div>
        <div class="pc-panel-body">
          <div class="fb-grid">
            <div class="pc-field"><label for="fbRealism">Realism (1–5)</label><input id="fbRealism" type="number" min="1" max="5" value="4" /></div>
            <div class="pc-field"><label for="fbDiff">Difficulty (1–5)</label><input id="fbDiff" type="number" min="1" max="5" value="3" /></div>
            <div class="pc-field"><label for="fbAi">AI behaved as expected (1–5)</label><input id="fbAi" type="number" min="1" max="5" value="4" /></div>
          </div>
          <div class="fb-checks">
            <label class="pc-check"><input id="fbBroken" type="checkbox" /> Confusing or broken</label>
            <label class="pc-check"><input id="fbReal" type="checkbox" /> Most like a real interview so far</label>
          </div>
          <div class="pc-field"><label for="fbText">Notes</label><textarea id="fbText" rows="2" placeholder="Anything that felt off or realistic?"></textarea></div>
          <div class="pc-row"><button type="button" class="btn btn-primary" id="fbSend">Send feedback</button><span class="pc-hint" id="fbStatus" aria-live="polite"></span></div>
        </div>
      </section>
    </div>

    <div ${panelAttrs("timeline")}>
      <div class="timeline-minimap" id="phaseMap" aria-hidden="true"></div>
      <div class="timeline-scrub" id="scrubber" role="slider" aria-label="Session timeline" tabindex="0" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
        <div class="timeline-scrub-track"></div>
        <div class="timeline-scrub-playhead" id="playhead"></div>
      </div>
      <div class="timeline-toolbar" id="timelineFilters" role="group" aria-label="Filter by phase">
        <button type="button" class="btn btn-ghost btn-sm" data-phase="all" aria-pressed="true">All</button>
        ${phases.map((p) => `<button type="button" class="btn btn-ghost btn-sm" data-phase="${esc(p)}" aria-pressed="false">${esc(p)}</button>`).join("")}
      </div>
      <div class="timeline-layout">
        <div id="timelineRoot">${timelineListHtml || PCUI.emptyState("No events", "Nothing was logged for this session.")}</div>
        <aside class="pc-panel timeline-detail" id="timelineDetail"><h4>Event detail</h4><p class="muted">Select an event on the scrubber or list.</p></aside>
      </div>
    </div>

    <div ${panelAttrs("code")}>
      <section class="pc-panel" aria-labelledby="diffTitle">
        <div class="pc-panel-head"><h2 id="diffTitle">Code diff</h2><span class="section-meta mono">${diffMeta}</span></div>
        ${diffHtml}
      </section>
      <section class="pc-panel" aria-labelledby="correctTitle">
        <div class="pc-panel-head"><h2 id="correctTitle">Advisory execution feedback</h2><span class="tag" data-tone="${testsOk ? "success" : "danger"}">${testsOk ? "passing" : "failing"}</span></div>
        <pre class="report-pre">${esc(JSON.stringify({
          visible_ok: r.test_summary?.ok,
          command: r.test_summary?.command,
          counts: r.test_summary?.counts,
          hidden_tests_leaked: r.test_summary?.hidden_tests_leaked,
        }, null, 2))}</pre>
      </section>
    </div>

    <div ${panelAttrs("defend")}>
      <div class="section-head">
        <h2 class="section-title">Defend your code</h2>
        <span class="section-meta">Four questions, one at a time. Answer guides are hidden.</span>
      </div>
      <div id="defendRoot">${defendHtml}</div>
    </div>`;

  const tabList = main.querySelector(".report-tabs");
  const tabButtons = () => Array.from(tabList.querySelectorAll("[role=tab]"));
  const selectTab = (btn, focus) => {
    activeTab = btn.dataset.tab;
    tabButtons().forEach((b) => {
      const on = b === btn;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
    document.querySelectorAll(".report-panel").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== activeTab;
    });
    if (focus) btn.focus();
  };
  tabButtons().forEach((btn) => btn.addEventListener("click", () => selectTab(btn)));
  tabList.addEventListener("keydown", (e) => {
    const list = tabButtons();
    const i = list.indexOf(document.activeElement);
    if (i < 0) return;
    const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: list.length - 1 }[e.key];
    if (next == null) return;
    e.preventDefault();
    selectTab(list[(next + list.length) % list.length], true);
  });
  PCUI.tabs(tabList);

  if (window.PCUI) PCUI.mountAppNav({ active: "practice" });

  const ring = document.getElementById("scoreRing");
  const reduced = reducedMotion();
  if (!reduced && !ringAnimated) {
    ringAnimated = true;
    const start = performance.now();
    const dur = 720;
    const tick = (now) => {
      const p = Math.min(1, (now - start) / dur);
      ring.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  } else {
    ring.textContent = String(Math.round(target));
  }

  /* —— Timeline scrubber —— */
  const sorted = [...events].sort((a, b) => parseTs(a.created_at) - parseTs(b.created_at));
  const t0 = sorted.length ? parseTs(sorted[0].created_at) : 0;
  const t1 = sorted.length ? parseTs(sorted[sorted.length - 1].created_at) : 1;
  const span = Math.max(1, t1 - t0);
  const scrubber = document.getElementById("scrubber");
  const playhead = document.getElementById("playhead");
  const detail = document.getElementById("timelineDetail");
  const phaseMap = document.getElementById("phaseMap");
  let focusIdx = 0;

  function pctFor(e) {
    return ((parseTs(e.created_at) - t0) / span) * 100;
  }

  if (phaseMap && sorted.length) {
    const buckets = phases.map((p) => ({ p, n: (grouped[p] || []).length }));
    const total = Math.max(1, buckets.reduce((s, b) => s + b.n, 0));
    phaseMap.innerHTML = buckets.filter((b) => b.n).map((b) =>
      `<span style="flex:${b.n / total};background:${PHASE_COLOR[b.p]}" title="${b.p}"></span>`
    ).join("");
  }

  sorted.forEach((e, i) => {
    const mark = document.createElement("button");
    mark.type = "button";
    mark.className = "timeline-scrub-mark";
    mark.dataset.phase = eventPhase(e.event_type);
    mark.dataset.i = String(i);
    mark.style.left = `calc(12px + (100% - 24px) * ${pctFor(e) / 100})`;
    mark.title = `${e.event_type} · ${e.created_at}`;
    mark.setAttribute("aria-label", `${e.event_type} at ${e.created_at}`);
    mark.addEventListener("click", (ev) => {
      ev.stopPropagation();
      focusEvent(i);
    });
    scrubber.appendChild(mark);
  });

  function focusEvent(i, fromList) {
    if (!sorted.length) return;
    focusIdx = Math.max(0, Math.min(sorted.length - 1, i));
    const e = sorted[focusIdx];
    const pct = pctFor(e);
    playhead.style.left = `calc(12px + (100% - 24px) * ${pct / 100})`;
    scrubber.setAttribute("aria-valuenow", String(Math.round(pct)));
    scrubber.querySelectorAll(".timeline-scrub-mark").forEach((m) => {
      m.classList.toggle("is-focused", Number(m.dataset.i) === focusIdx);
    });
    document.querySelectorAll("#timelineRoot .timeline-item").forEach((el) => {
      const on = String(el.dataset.id) === String(e.id);
      el.classList.toggle("is-active", on);
      if (on && !fromList) el.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
    });
    const d = detailFor(e);
    detail.innerHTML = `<h4>${esc(d.phase)}</h4><strong>${esc(d.title)}</strong>
      <div class="t" style="margin:6px 0;font-family:var(--pc-font-mono);font-size:11px;color:var(--pc-faint)">${esc(e.created_at)}</div>
      ${d.body}`;
  }

  function idxFromClientX(x) {
    const rect = scrubber.getBoundingClientRect();
    const pad = 12;
    const w = Math.max(1, rect.width - pad * 2);
    const pct = Math.max(0, Math.min(1, (x - rect.left - pad) / w));
    const targetT = t0 + pct * span;
    let best = 0, bestD = Infinity;
    sorted.forEach((e, i) => {
      const d = Math.abs(parseTs(e.created_at) - targetT);
      if (d < bestD) { bestD = d; best = i; }
    });
    return best;
  }

  let dragging = false;
  scrubber.addEventListener("pointerdown", (e) => {
    dragging = true;
    scrubber.setPointerCapture?.(e.pointerId);
    focusEvent(idxFromClientX(e.clientX));
  });
  scrubber.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    focusEvent(idxFromClientX(e.clientX));
  });
  scrubber.addEventListener("pointerup", () => { dragging = false; });
  scrubber.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); focusEvent(focusIdx + 1); }
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); focusEvent(focusIdx - 1); }
    if (e.key === "Home") { e.preventDefault(); focusEvent(0); }
    if (e.key === "End") { e.preventDefault(); focusEvent(sorted.length - 1); }
  });

  document.getElementById("timelineRoot")?.addEventListener("click", (e) => {
    const item = e.target.closest(".timeline-item");
    if (!item) return;
    const idx = sorted.findIndex((ev) => String(ev.id) === String(item.dataset.id));
    if (idx >= 0) focusEvent(idx, true);
  });
  document.getElementById("timelineRoot")?.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const item = e.target.closest(".timeline-item");
    if (!item) return;
    e.preventDefault();
    const idx = sorted.findIndex((ev) => String(ev.id) === String(item.dataset.id));
    if (idx >= 0) focusEvent(idx, true);
  });

  document.querySelectorAll(".js-diff-file").forEach((btn) => {
    btn.addEventListener("click", () => {
      const path = btn.dataset.path;
      const tabBtn = document.querySelector('.report-tabs [data-tab="timeline"]');
      if (tabBtn) tabBtn.click();
      const idx = sorted.findIndex((e) => e.payload?.path === path);
      if (idx >= 0) {
        focusEvent(idx);
        scrubber.focus();
      } else PCUI.toast("No timeline events for this file", { tone: "warn" });
    });
  });

  if (sorted.length) focusEvent(0);

  document.getElementById("timelineFilters")?.addEventListener("click", (e) => {
    const b = e.target.closest("[data-phase]");
    if (!b) return;
    const phase = b.dataset.phase;
    document.querySelectorAll("#timelineFilters [data-phase]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    document.querySelectorAll("#timelineRoot .timeline-group").forEach((g) => {
      g.style.display = phase === "all" || g.dataset.phase === phase ? "" : "none";
    });
    scrubber.querySelectorAll(".timeline-scrub-mark").forEach((m) => {
      m.style.display = phase === "all" || m.dataset.phase === phase ? "" : "none";
    });
  });

  const defendForm = document.getElementById("defendForm");
  if (defendForm) {
    defendForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const answer = document.getElementById("defendAnswer").value.trim();
      if (!answer) return PCUI.toast("Write an answer first", { tone: "warn" });
      await InterviewAPI.answerDefend(sessionId, nextIdx, answer);
      load();
    });
    defendForm.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
      if (document.activeElement && document.activeElement.id === "defendSubmit") {
        e.preventDefault();
        defendForm.requestSubmit();
      }
    });
  }
  const fbSend = document.getElementById("fbSend");
  if (fbSend) {
    fbSend.onclick = async () => {
      try {
        await InterviewAPI.feedback(sessionId, {
          realism: Number(document.getElementById("fbRealism").value),
          difficulty: Number(document.getElementById("fbDiff").value),
          ai_as_expected: Number(document.getElementById("fbAi").value),
          confusing_or_broken: document.getElementById("fbBroken").checked,
          most_like_real_interview: document.getElementById("fbReal").checked,
          text: document.getElementById("fbText").value,
        });
        document.getElementById("fbStatus").textContent = "Thanks — feedback saved.";
        fbSend.disabled = true;
        PCUI.toast("Feedback saved", { tone: "success" });
      } catch (e) {
        document.getElementById("fbStatus").textContent = e.message || "Failed";
      }
    };
  }
}
load().catch((e) => {
  document.getElementById("main").innerHTML = `<div class="pc-error"><strong>Could not load report</strong><div class="pc-error-safe">Your session data remains on the server.</div><button class="btn btn-ghost" type="button" data-pc-reload>Retry</button><div class="muted" style="margin-top:8px">${e.message}</div></div>`;
});
