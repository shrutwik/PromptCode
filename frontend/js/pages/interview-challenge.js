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
  const c = await InterviewAPI.getChallenge(slug);
  let card = null;
  try {
    const cards = await InterviewAPI.listChallengesProgress({});
    card = (cards || []).find((item) => item.slug === slug) || null;
  } catch (_) {
    card = null;
  }
  const activeId = card && card.active_session_id;
  const startLabel = card && card.attempt_count ? "Start another attempt" : "Start session";
  document.title = c.title + " — PromptCode";
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
          </div>
          <p class="brief-summary">${esc(c.summary)}</p>
        </header>
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
            <li>${CHECK}<span>AI assistant allowed. What you ask and accept is logged and scored.</span></li>
            <li>${CHECK}<span>The task opens one step at a time: the bug, then each feature level after you run the tests.</span></li>
            <li>${CHECK}<span>Visible tests run in the workspace; hidden tests run on submit.</span></li>
            <li>${CHECK}<span>After submitting you’ll defend your changes in four short questions.</span></li>
          </ul>
        </div>
        <div class="pc-panel-body">
          ${activeId
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
  const main = document.getElementById("main");
  main.removeAttribute("aria-busy");
  main.innerHTML = `<a class="page-back" href="/challenges">← Challenges</a><div class="pc-error" role="alert"><strong>Could not load this challenge</strong><div class="pc-error-safe">${esc(e.message)}</div><button class="btn btn-ghost btn-sm" type="button" data-pc-reload>Retry</button></div>`;
});
