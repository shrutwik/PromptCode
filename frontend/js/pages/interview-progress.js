if (!InterviewAPI.requireAuth("/progress")) throw new Error("auth");

const esc = PCUI.esc;
document.getElementById("finishedSkel").innerHTML = PCUI.skeletonRows(4);
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

function renderScores(data) {
  const cells = [
    ["Completed", data.completed ?? 0, ""],
    ["Avg score", data.avg_score ?? "—", "/100"],
    ["Correctness", data.avg_correctness ?? "—", "/25"],
    ["Exploration", data.avg_exploration ?? "—", "/15"],
    ["AI judgment", data.avg_ai_judgment ?? "—", "/15"],
    ["Verification", data.avg_verification ?? "—", "/10"],
  ];
  document.getElementById("stats").innerHTML = cells.map(([l, v, max]) =>
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
    skillRoot.innerHTML = `<p class="muted" style="font-size:var(--pc-text-sm)">Practice evidence needs review before skill ratings are available.</p>`;
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
      note.textContent = (data.completed || 0) < 3 ? "Trends appear after a few completed sessions." : "";
    }
  }
}

function renderFinished(sessions) {
  const root = document.getElementById("finished");
  const meta = document.getElementById("finishedMeta");
  const done = sessions.filter((s) => s.status === "submitted");
  if (!done.length) {
    meta.textContent = "";
    root.innerHTML = PCUI.emptyState(
      "No finished sessions yet",
      "Scores show up here after you submit a challenge.",
      '<a class="btn btn-primary" href="/challenges">Browse challenges</a>'
    );
    return;
  }
  meta.textContent = String(done.length);
  root.innerHTML = `<div class="pc-table-wrap"><table class="pc-table">
    <thead><tr><th scope="col">Challenge</th><th scope="col">Finished</th><th scope="col" class="num">Attempt</th><th scope="col" class="num">Score</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
    <tbody>${done.map((s) => {
      const href = `/session/${s.id}/report`;
      return `<tr data-href="${esc(href)}" tabindex="0">
        <td class="title-cell"><a href="${esc(href)}" tabindex="-1">${esc(s.challenge_title || s.challenge_slug)}</a></td>
        <td>${esc(when(s.submitted_at || s.started_at))}</td>
        <td class="num">${esc(s.attempt_number || 1)}</td>
        <td class="num">${s.total_score != null ? esc(s.total_score) : "—"}</td>
        <td class="actions"><a class="btn btn-secondary btn-sm" href="${esc(href)}">Report</a></td>
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
  renderScores(data);
  renderFinished(data.sessions || []);
}

load().catch((e) => {
  document.getElementById("stats").innerHTML = "";
  document.getElementById("skills").innerHTML = "";
  document.getElementById("finished").innerHTML = `<div class="pc-error" role="alert"><strong>Could not load progress</strong><div class="pc-error-safe">Your sessions are safe on the server.</div><button class="btn btn-ghost btn-sm" type="button" data-pc-reload>Retry</button><div class="muted" style="margin-top:8px">${esc(e.message)}</div></div>`;
});
