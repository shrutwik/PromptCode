if (!InterviewAPI.requireAuth("/dashboard")) throw new Error("auth");

const esc = PCUI.esc;
document.getElementById("listSkel").innerHTML = PCUI.skeletonRows(4);
document.getElementById("stats").innerHTML = Array.from({ length: 6 }, () =>
  '<div class="stat"><span class="pc-skeleton pc-skeleton-text" style="--w:40%;height:20px"></span><span class="pc-skeleton pc-skeleton-text" style="--w:70%"></span></div>'
).join("");
document.getElementById("skills").innerHTML = Array.from({ length: 4 }, () => '<span class="pc-skeleton pc-skeleton-text"></span>').join("");

function parseUtc(v) {
  if (!v) return NaN;
  const s = String(v);
  return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(s) ? s : s + "Z");
}

function when(v) {
  const t = parseUtc(v);
  if (!Number.isFinite(t)) return "—";
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h ago`;
  return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const STATUS_TONE = { submitted: "success", active: "info", abandoned: "idle" };

function scrollToProgress() {
  if (location.hash !== "#progress") return;
  const el = document.getElementById("progress");
  if (!el) return;
  el.scrollIntoView({ block: "start", behavior: PCUI.reducedMotion() ? "auto" : "smooth" });
  el.focus({ preventScroll: true });
}
window.addEventListener("hashchange", scrollToProgress);

function ownedSessionHref(id, report) {
  // Logged-in resume uses the bearer token. The owner token is not required.
  return report ? `/session/${id}/report` : `/session/${id}`;
}

function renderContinue(sessions) {
  const active = sessions.find((s) => s.status === "active");
  const cont = document.getElementById("continue");
  if (active) {
    cont.innerHTML = `<div class="pc-panel dash-continue is-active">
      <div>
        <span class="pc-eyebrow">Continue practice</span>
        <h2>${esc(active.challenge_title || active.challenge_slug)}</h2>
        <p>Your workspace is saved. Pick up where you left off — the timer keeps running.</p>
        <div class="dash-continue-meta">
          <span class="tag" data-tone="info"><span class="pc-dot"></span>In progress</span>
          <span class="tag">Attempt ${esc(active.attempt_number || 1)}</span>
          <span class="tag">Started ${esc(when(active.started_at))}</span>
        </div>
      </div>
      <div class="dash-continue-actions"><a class="btn btn-primary" href="${esc(ownedSessionHref(active.id, false))}">Resume session</a></div>
    </div>`;
  } else {
    cont.innerHTML = `<div class="pc-panel dash-continue">
      <div>
        <span class="pc-eyebrow">Start practice</span>
        <h2>No session in progress</h2>
        <p>Pick a production-style challenge. Sessions are timed, AI is allowed, and how you use it is scored.</p>
      </div>
      <div class="dash-continue-actions"><a class="btn btn-primary" href="/challenges">Find a challenge</a></div>
    </div>`;
  }
}

function renderProgress(data) {
  const stats = document.getElementById("stats");
  /* Category averages are raw rubric points; maxima mirror backend rubric (A 25, B 15, D 15, E 10). */
  const cells = [
    ["Completed", data.completed ?? 0, ""],
    ["Avg score", data.avg_score ?? "—", "/100"],
    ["Correctness", data.avg_correctness ?? "—", "/25"],
    ["Exploration", data.avg_exploration ?? "—", "/15"],
    ["AI judgment", data.avg_ai_judgment ?? "—", "/15"],
    ["Verification", data.avg_verification ?? "—", "/10"],
  ];
  stats.innerHTML = cells.map(([l, v, max]) =>
    `<div class="stat"><div class="n">${esc(v)}${max && v !== "—" ? `<span class="stat-max">${max}</span>` : ""}</div><div class="l">${esc(l)}</div></div>`
  ).join("");

  const skills = [
    ["Correctness", data.avg_correctness, 25],
    ["Exploration", data.avg_exploration, 15],
    ["AI judgment", data.avg_ai_judgment, 15],
    ["Verification", data.avg_verification, 10],
  ].map(([l, v, max]) => [l, v == null || v === "—" ? null : Number(v), max]);
  const skillRoot = document.getElementById("skills");
  if (skills.some(([, v]) => v > 0)) {
    skillRoot.innerHTML = skills.map(([l, v, max], i) => {
      const pct = v == null ? 0 : (v / max) * 100;
      const tone = pct >= 70 ? "success" : pct >= 40 ? "warn" : "danger";
      return `<div class="skill-row"><span>${esc(l)}</span>${PCUI.bar(pct, v == null ? "" : tone, 120 + i * 80)}<span class="v">${v == null ? "—" : `${esc(v)}<span class="stat-max">/${max}</span>`}</span></div>`;
    }).join("");
  } else {
    skillRoot.innerHTML = `<p class="muted" style="font-size:var(--pc-text-sm)">Complete a session to see your skill mix.</p>`;
  }

  const note = document.getElementById("trendsNote");
  const trendsEl = document.getElementById("trends");
  const trends = data.trends || [];
  note.textContent = data.trends_note || "";
  if (trends.length && (data.completed || 0) >= 3) {
    trendsEl.innerHTML = trends.map((t) => `<li>${esc(t)}</li>`).join("");
  } else {
    trendsEl.innerHTML = "";
    if (!data.trends_note) {
      note.textContent = (data.completed || 0) < 3 ? "Trends appear after a few completed sessions — no fake charts." : "";
    }
  }
}

function renderSessions(sessions) {
  const root = document.getElementById("list");
  const meta = document.getElementById("recentMeta");
  if (!sessions.length) {
    meta.textContent = "";
    root.innerHTML = PCUI.emptyState(
      "No sessions yet",
      "Start your first challenge — your work stays private to your account.",
      '<a class="btn btn-primary" href="/challenges">Browse challenges</a>'
    );
    return;
  }
  const recent = sessions.slice(0, 8);
  meta.textContent = `${recent.length} of ${sessions.length}`;
  root.innerHTML = `<div class="pc-table-wrap"><table class="pc-table">
    <thead><tr><th scope="col">Challenge</th><th scope="col">Status</th><th scope="col">Started</th><th scope="col" class="num">Attempt</th><th scope="col" class="num">Score</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
    <tbody data-stagger>${recent.map((s) => {
      const done = s.status === "submitted";
      const href = ownedSessionHref(s.id, done);
      return `<tr data-href="${esc(href)}" tabindex="0">
        <td class="title-cell"><a href="${esc(href)}" tabindex="-1">${esc(s.challenge_title || s.challenge_slug)}</a></td>
        <td><span class="tag" data-tone="${STATUS_TONE[s.status] || "idle"}">${esc(s.status)}</span></td>
        <td>${esc(when(s.started_at))}</td>
        <td class="num">${esc(s.attempt_number || 1)}</td>
        <td class="num">${s.total_score != null ? esc(s.total_score) : "—"}</td>
        <td class="actions">
          <a class="btn btn-ghost btn-sm" href="${esc(ownedSessionHref(s.id, false))}">Workspace</a>
          ${done ? `<a class="btn btn-secondary btn-sm" href="${esc(ownedSessionHref(s.id, true))}">Report</a>` : ""}
        </td>
      </tr>`;
    }).join("")}</tbody></table></div>`;
  root.querySelectorAll("tr[data-href]").forEach((tr) => {
    tr.addEventListener("click", (e) => {
      if (e.target.closest("a, button")) return;
      location.href = tr.dataset.href;
    });
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.target === tr) location.href = tr.dataset.href;
    });
  });
}

async function load() {
  const data = await InterviewAPI.dashboard();
  const sessions = data.sessions || data || [];
  renderContinue(sessions);
  renderSessions(sessions);
  renderProgress(data);
  requestAnimationFrame(scrollToProgress);
}

load().catch((e) => {
  document.getElementById("continue").innerHTML = "";
  document.getElementById("list").innerHTML = `<div class="pc-error" role="alert"><strong>Could not load practice home</strong><div class="pc-error-safe">Your sessions are safe on the server.</div><button class="btn btn-ghost btn-sm" type="button" data-pc-reload>Retry</button><div class="muted" style="margin-top:8px">${esc(e.message)}</div></div>`;
  document.getElementById("stats").innerHTML = "";
  document.getElementById("skills").innerHTML = "";
});
