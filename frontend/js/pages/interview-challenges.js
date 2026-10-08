(function () {
const pageRoot = document.getElementById("main");
const scriptEpoch = document.currentScript?.dataset.pcNav;
if (!pageRoot || (scriptEpoch && scriptEpoch !== pageRoot.dataset.pcNav)) return;
if (!InterviewAPI.requireAuth("/challenges")) throw new Error("auth");

const esc = PCUI.esc;
const params = new URLSearchParams(location.search);
document.getElementById("tableSkel").innerHTML = PCUI.skeletonRows(6);
if (!InterviewAPI.isLoggedIn()) {
  document.getElementById("authHint").innerHTML = 'Sign in to start or resume a session. <a href="/login.html?next=/challenges">Sign in</a>';
}

let allItems = [];
let filtersReady = false;

const DIFF_TONE = { easy: "success", hard: "danger" };
const PROGRESS = {
  checking: ["Checking…", "idle"],
  not_started: ["Not started", "idle"],
  in_progress: ["In progress", "info"],
  completed: ["Completed", "success"],
};

function applyFilters() {
  const q = (document.getElementById("searchFilter").value || "").trim().toLowerCase();
  const type = document.getElementById("typeFilter").value;
  const stack = document.getElementById("stackFilter").value;
  const status = document.getElementById("statusFilter").value;
  const diff = document.getElementById("diffFilter").value;
  return allItems.filter((c) => {
    if (type && c.type !== type) return false;
    if (stack && c.stack !== stack) return false;
    if (diff && c.difficulty !== diff) return false;
    const progress = c.progress || "not_started";
    if (status && progress !== "checking" && progress !== status) return false;
    if (q) {
      const hay = `${c.title} ${c.summary} ${c.slug || ""} ${c.type} ${c.stack}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function clearFilters() {
  ["searchFilter", "typeFilter", "stackFilter", "statusFilter", "diffFilter"].forEach((id) => {
    document.getElementById(id).value = "";
  });
  renderTable(applyFilters());
}

function renderTable(filtered) {
  const root = document.getElementById("tableWrap");
  document.getElementById("libCount").textContent = `${filtered.length} of ${allItems.length}`;
  if (!filtered.length) {
    root.innerHTML = PCUI.emptyState("No matches", "Try a different search or clear the filters.", '<button class="btn btn-secondary btn-sm" type="button" id="clearFilters">Clear filters</button>');
    document.getElementById("clearFilters").addEventListener("click", clearFilters);
    return;
  }
  root.innerHTML = `<table class="pc-table">
    <thead>
      <tr>
        <th scope="col">Challenge</th>
        <th scope="col">Domain</th>
        <th scope="col">Stack</th>
        <th scope="col">Difficulty</th>
        <th scope="col" class="num">Time</th>
        <th scope="col">Status</th>
        <th scope="col"><span class="sr-only">Action</span></th>
      </tr>
    </thead>
    <tbody data-stagger>
      ${filtered.map((c) => {
        const progress = c.progress || "not_started";
        const [label, tone] = PROGRESS[progress] || [progress, "idle"];
        const brief = `/challenges/${encodeURIComponent(c.slug)}`;
        const href = c.active_session_id ? `/session/${c.active_session_id}` : brief;
        const cta = c.active_session_id ? "Resume" : "Open";
        return `<tr data-href="${esc(brief)}" tabindex="0" aria-label="${esc(c.title)}">
          <td class="title-cell"><a href="${esc(brief)}" tabindex="-1">${esc(c.title)}</a>
            <span class="sub">${c.featured_rank != null ? `Core #${esc(c.featured_rank)}` : "More practice"}</span>
            ${c.best_score != null ? `<span class="sub">best ${esc(c.best_score)}</span>` : ""}
          </td>
          <td>${esc(c.type)}</td>
          <td>${esc(c.stack)}</td>
          <td><span class="tag" data-tone="${DIFF_TONE[String(c.difficulty).toLowerCase()] || ""}">${esc(c.difficulty)}</span></td>
          <td class="num">${esc(c.estimated_minutes)}m</td>
          <td><span class="tag" data-tone="${tone}">${esc(label)}</span></td>
          <td class="actions"><a class="btn ${c.active_session_id ? "btn-primary" : "btn-secondary"} btn-sm" href="${esc(href)}">${cta}</a></td>
        </tr>`;
      }).join("")}
    </tbody>
  </table>`;
  root.querySelectorAll("tr[data-href]").forEach((tr) => {
    tr.addEventListener("click", (e) => {
      if (e.target.closest("a, button")) return;
      window.PCNav ? PCNav.go(tr.dataset.href) : location.assign(tr.dataset.href);
    });
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.target === tr) window.PCNav ? PCNav.go(tr.dataset.href) : location.assign(tr.dataset.href);
    });
  });
}

function fillSelect(el, values, placeholder) {
  if (el.options.length > 1) return;
  [...values].sort().forEach((t) => {
    const o = document.createElement("option");
    o.value = t; o.textContent = t; el.appendChild(o);
  });
  if (placeholder && params.get(placeholder)) {
    el.value = params.get(placeholder);
  }
}

function renderData(data) {
  if (!pageRoot.isConnected) return;
  allItems = data;

  if (!filtersReady) {
    const types = new Set();
    const stacks = new Set();
    const diffs = new Set();
    for (const c of allItems) {
      types.add(c.type);
      stacks.add(c.stack);
      diffs.add(c.difficulty);
    }
    fillSelect(document.getElementById("typeFilter"), types, "type");
    fillSelect(document.getElementById("stackFilter"), stacks, "stack");
    fillSelect(document.getElementById("diffFilter"), diffs, "difficulty");
    filtersReady = true;
  }
  renderTable(applyFilters());
}

async function load() {
  const catalog = InterviewAPI.getCachedCatalog();
  if (catalog) renderData(catalog.map((card) => ({ ...card, progress: "checking" })));
  const data = InterviewAPI.isLoggedIn()
    ? await InterviewAPI.readChallengesProgress(renderData)
    : await InterviewAPI.listChallenges({});
  renderData(data);
}

["typeFilter", "stackFilter", "statusFilter", "diffFilter", "searchFilter"].forEach((id) => {
  const el = document.getElementById(id);
  el.addEventListener(id === "searchFilter" ? "input" : "change", () => renderTable(applyFilters()));
});

load().catch((e) => {
  if (!pageRoot.isConnected) return;
  if (allItems.length) {
    document.getElementById("authHint").innerHTML = `<span class="pc-error" role="alert"><strong>Could not check session status</strong> <span class="pc-error-safe">${esc(e.message)}</span> <button class="btn btn-ghost btn-sm" type="button" data-pc-reload>Retry</button></span>`;
    return;
  }
  document.getElementById("tableWrap").innerHTML = `<div class="pc-error" role="alert" style="border:0;border-radius:0"><strong>Could not load challenges</strong><div class="pc-error-safe">${esc(e.message)}</div><button class="btn btn-ghost btn-sm" type="button" data-pc-reload>Retry</button></div>`;
});

})();
