(function () {
const pageRoot = document.getElementById("main");
const scriptEpoch = document.currentScript?.dataset.pcNav;
if (!pageRoot || (scriptEpoch && scriptEpoch !== pageRoot.dataset.pcNav)) return;
if (!InterviewAPI.requireAuth(location.pathname)) throw new Error("auth");
const slug = location.pathname.split("/").filter(Boolean).pop();
const esc = PCUI.esc;
const DIFF_TONE = { easy: "success", hard: "danger" };
const CHECK = '<svg class="pc-icon pc-icon-sm" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7"/></svg>';

async function start() {
  const session = await InterviewAPI.startSession(slug);
  location.href = "/session/" + session.id;
}

async function load() {
  let challenge, card = null, pending = "Checking your sessions…";
  const show = () => {
    if (challenge && pageRoot.isConnected) render(challenge, card, pending);
  };
  const updateProgress = (cards) => {
    card = cards.find((item) => item.slug === slug) || null;
    pending = "";
    show();
  };
  const progress = InterviewAPI.readChallengesProgress(updateProgress).then(updateProgress, () => {
    pending = "Could not check your sessions. Reload to retry.";
    show();
  });
  challenge = await InterviewAPI.getChallenge(slug, (data) => { challenge = data; show(); });
  show();
  await progress;
}

function render(c, card, pending) {
  const activeId = card && card.active_session_id;
  const startLabel = card && card.attempt_count ? "Start another attempt" : "Start session";
  const main = document.getElementById("main");
  main.removeAttribute("aria-busy");
  main.innerHTML = `
    <a class="page-back" href="/challenges">← Challenges</a>
    <div class="brief-layout">
      <div>
        <header class="brief-head">
          <h1 class="page-title">${esc(c.title)}</h1>
          <div class="pc-row">
            <span class="tag" data-tone="${DIFF_TONE[String(c.difficulty).toLowerCase()] || ""}">${esc(c.difficulty)}</span>
            <span class="tag">${esc(c.type)}</span>
            <span class="tag">${esc(c.stack)}</span>
            <span class="tag">${esc(c.estimated_minutes)} min</span>
            ${c.featured_rank != null ? `<span class="tag">Core #${esc(c.featured_rank)}</span>` : ""}
          </div>
          <p class="brief-summary">${esc(c.summary)}</p>
        </header>
        <section class="pc-panel" aria-labelledby="criteriaTitle">
          <div class="pc-panel-head"><h2 id="criteriaTitle">How your work is assessed</h2></div>
          <div class="pc-panel-body">
            <p>${esc(c.grading_criteria?.notice || "Test results and human review are separate. Optional discussion is ungraded.")}</p>
            ${Object.values(c.grading_criteria?.dimensions || {}).map((criterion) => `<details>
              <summary>${esc(criterion.label)} · ${esc(criterion.weight)}%</summary>
              <dl>${Object.entries(criterion.anchors || {}).map(([rating, anchor]) => `<dt>${esc(rating)} / 4</dt><dd>${esc(anchor)}</dd>`).join("")}</dl>
            </details>`).join("")}
            <p>Missing evidence is not a zero. AI use is optional; when AI judgment is not observed, the report identifies its exclusion. Model brand, prompt count and verbosity do not earn points.</p>
          </div>
        </section>
        <section class="pc-panel" aria-labelledby="ticketTitle">
          <div class="pc-panel-head"><h2 id="ticketTitle">Task</h2><span class="section-meta mono">README.md</span></div>
          <pre class="brief-readme">${esc(c.readme)}</pre>
        </section>
      </div>
      <aside class="pc-panel brief-aside" aria-label="Session details">
        <div class="pc-panel-body">
          <div class="brief-label">Assessment</div>
          <dl class="pc-dl">
            <dt>Difficulty</dt><dd>${esc(c.difficulty)}</dd>
            <dt>Stack</dt><dd>${esc(c.stack)}</dd>
            <dt>Domain</dt><dd>${esc(c.type)}</dd>
            <dt>Time box</dt><dd>${esc(c.estimated_minutes)} min</dd>
          </dl>
        </div>
        <div class="pc-panel-body">
          <div class="brief-label">Rules</div>
          <ul class="brief-rules">
            <li>${CHECK}<span>Timed interview simulation — the clock starts when the workspace is ready and pauses while you’re away.</span></li>
            <li>${CHECK}<span>AI assistant allowed. The rubric considers how you inspect and verify its output.</span></li>
            <li>${CHECK}<span>Follow the stated task parts. Optional changed-requirement discussion is ungraded.</span></li>
            <li>${CHECK}<span>Visible tests run in the workspace; hidden tests run on submit.</span></li>
            <li>${CHECK}<span>After submitting you’ll defend your changes in four short questions.</span></li>
          </ul>
        </div>
        <div class="pc-panel-body">
          ${pending ? `<button class="btn btn-primary btn-lg btn-block" disabled>${esc(pending)}</button>` : activeId
            ? `<a class="btn btn-primary btn-lg btn-block" href="/session/${esc(activeId)}">Resume session</a><button class="btn btn-ghost btn-block" id="restartBtn" type="button">Discard and restart</button>`
            : `<button class="btn btn-primary btn-lg btn-block" id="startBtn" type="button">${startLabel}</button>`}
          <p class="brief-note">${activeId ? "An open session is already saved for this challenge." : "Desktop recommended."}</p>
        </div>
      </aside>
    </div>`;
  const restart = document.getElementById("restartBtn");
  if (restart) restart.onclick = async () => {
    if (!window.confirm("Discard this unfinished attempt? Restarting opens fresh code with the timer at 00:00.")) return;
    restart.disabled = true;
    try {
      try { await InterviewAPI.abandon(activeId, "restart"); }
      catch (error) {
        const snapshot = await InterviewAPI.getSession(activeId);
        if (snapshot.status !== "abandoned") throw error;
      }
      await start();
    } catch (error) {
      restart.disabled = false;
      PCUI.toast(error.message, { tone: "danger" });
    }
  };
  const btn = document.getElementById("startBtn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    btn.disabled = true;
    btn.classList.add("is-loading");
    btn.innerHTML = '<span class="pc-spinner" aria-hidden="true"></span> Starting…';
    start().catch((e) => {
      btn.disabled = false;
      btn.classList.remove("is-loading");
      btn.textContent = startLabel;
      PCUI.toast(e.message || String(e), { tone: "danger" });
    });
  });
}

load().catch((e) => {
  if (!pageRoot.isConnected) return;
  const main = document.getElementById("main");
  main.removeAttribute("aria-busy");
  main.innerHTML = `<a class="page-back" href="/challenges">← Challenges</a><div class="pc-error" role="alert"><strong>Could not load this challenge</strong><div class="pc-error-safe">${esc(e.message)}</div><button class="btn btn-ghost btn-sm" type="button" data-pc-reload>Retry</button></div>`;
});

})();
