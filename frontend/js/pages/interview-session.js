const sessionId = location.pathname.split("/").filter(Boolean).pop();
const EXT_LANG = {
  ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript",
  py: "python", json: "json", html: "html", css: "css", sql: "sql",
  md: "markdown", java: "java", cs: "csharp",
};

let files = [];
let editor = null;
let models = {}; // path -> { model, saved, dirty }
let openTabs = [];
let currentPath = null;
let collapsed = new Set();
let lastTestOutput = "";
let lastProposed = null;
let viewedOnce = new Set();
let sessionReadOnly = false;

function langFor(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  return EXT_LANG[ext] || "plaintext";
}

function logTerm(text) {
  document.getElementById("termLog").textContent = text;
}
function setTermMeta(html) {
  document.getElementById("termMeta").innerHTML = html;
}
function logChat(role, text, expandable) {
  const el = document.getElementById("chatLog");
  const block = document.createElement("div");
  block.className = "chat-msg " + role;
  if (expandable && text.length > 280) {
    const short = text.slice(0, 280) + "…";
    block.innerHTML = `<strong>${role === "user" ? "You" : "AI"}</strong><pre class="chat-body">${esc(short)}</pre><button class="linkish" type="button">Expand</button>`;
    block.querySelector("button").onclick = () => {
      block.querySelector("pre").textContent = text;
      block.querySelector("button").remove();
    };
  } else {
    block.innerHTML = `<strong>${role === "user" ? "You" : "AI"}</strong><pre class="chat-body">${esc(text)}</pre>`;
  }
  el.appendChild(block);
  el.scrollTop = el.scrollHeight;
}
function esc(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
function updateDirtyPill() {
  const dirty = openTabs.some((p) => models[p] && models[p].dirty);
  document.getElementById("dirtyPill").classList.toggle("hidden", !dirty);
}

function buildTree(paths) {
  const root = {};
  for (const f of paths) {
    const parts = f.path.split("/");
    let node = root;
    parts.forEach((part, i) => {
      if (!node[part]) node[part] = { __children: {}, __file: null };
      if (i === parts.length - 1) node[part].__file = f;
      else node = node[part].__children;
    });
  }
  return root;
}

function renderTree(filter = "") {
  const treeEl = document.getElementById("tree");
  treeEl.innerHTML = "";
  const q = filter.trim().toLowerCase();
  const filtered = q
    ? files.filter((f) => f.path.toLowerCase().includes(q))
    : files;
  if (q) {
    InterviewAPI.postEvent(sessionId, "file_searched", { query: q, hits: filtered.length }).catch(() => {});
  }
  const root = buildTree(filtered);
  function walk(node, prefix, depth) {
    const names = Object.keys(node).sort((a, b) => {
      const ad = Object.keys(node[a].__children).length > 0;
      const bd = Object.keys(node[b].__children).length > 0;
      if (ad !== bd) return ad ? -1 : 1;
      return a.localeCompare(b);
    });
    for (const name of names) {
      const entry = node[name];
      const path = prefix ? prefix + "/" + name : name;
      const isDir = Object.keys(entry.__children).length > 0 && !entry.__file;
      if (isDir || Object.keys(entry.__children).length) {
        const dirBtn = document.createElement("button");
        dirBtn.className = "file-item dir";
        dirBtn.style.paddingLeft = 10 + depth * 12 + "px";
        const open = !collapsed.has(path);
        dirBtn.textContent = (open ? "▾ " : "▸ ") + name;
        dirBtn.onclick = () => {
          if (collapsed.has(path)) collapsed.delete(path);
          else collapsed.add(path);
          renderTree(document.getElementById("fileSearch").value);
        };
        treeEl.appendChild(dirBtn);
        if (open) walk(entry.__children, path, depth + 1);
      }
      if (entry.__file) {
        const btn = document.createElement("button");
        btn.className = "file-item" + (currentPath === path ? " active" : "");
        btn.style.paddingLeft = 24 + depth * 12 + "px";
        const mod = models[path] && models[path].dirty ? " ●" : "";
        btn.textContent = name + mod;
        btn.onclick = () => openFile(path);
        treeEl.appendChild(btn);
      }
    }
  }
  walk(root, "", 0);
}

function renderTabs() {
  const tabs = document.getElementById("tabs");
  tabs.innerHTML = "";
  for (const path of openTabs) {
    const t = document.createElement("button");
    t.className = "tab" + (path === currentPath ? " active" : "");
    t.type = "button";
    const name = path.split("/").pop();
    t.textContent = name + (models[path] && models[path].dirty ? " ●" : "");
    t.onclick = () => openFile(path);
    tabs.appendChild(t);
  }
}

async function openFile(path) {
  if (!editor) return;
  if (currentPath && models[currentPath]) {
    models[currentPath].dirty =
      models[currentPath].model.getValue() !== models[currentPath].saved;
  }
  if (!models[path]) {
    const data = await InterviewAPI.getFile(sessionId, path);
    const model = monaco.editor.createModel(data.content, langFor(path));
    model.onDidChangeContent(() => {
      if (!models[path]) return;
      models[path].dirty = model.getValue() !== models[path].saved;
      updateDirtyPill();
      renderTabs();
      renderTree(document.getElementById("fileSearch").value);
    });
    models[path] = { model, saved: data.content, dirty: false };
    if (!viewedOnce.has(path)) viewedOnce.add(path);
  }
  if (!openTabs.includes(path)) openTabs.push(path);
  currentPath = path;
  editor.setModel(models[path].model);
  editor.updateOptions({ readOnly: sessionReadOnly });
  document.getElementById("pathLabel").textContent = path;
  document.getElementById("langLabel").textContent = langFor(path);
  renderTabs();
  renderTree(document.getElementById("fileSearch").value);
  updateDirtyPill();
}

async function save() {
  if (!currentPath || !models[currentPath]) throw new Error("No file selected");
  const content = models[currentPath].model.getValue();
  await InterviewAPI.saveFile(sessionId, currentPath, content, { source: "candidate" });
  models[currentPath].saved = content;
  models[currentPath].dirty = false;
  updateDirtyPill();
  renderTabs();
  renderTree(document.getElementById("fileSearch").value);
  logTerm("Saved " + currentPath + " (file_changed on save)");
}

async function runCmd(commandId) {
  setTermMeta(`Running <code>${commandId}</code>…`);
  logTerm("…");
  const r = await InterviewAPI.runTests(sessionId, commandId);
  lastTestOutput = `$ ${r.command}\nexit ${r.exit_code} · ${r.duration_ms || 0}ms · isolation=${r.isolation}\n` +
    `counts ${JSON.stringify(r.counts || {})}\n\n${r.stdout}\n${r.stderr}`;
  setTermMeta(
    `<span class="${r.ok ? "ok" : "fail"}">${r.ok ? "PASS" : "FAIL"}</span> · ` +
    `<code>${esc(r.command)}</code> · ${r.duration_ms || 0}ms · ` +
    `${(r.counts && r.counts.passed) || 0} passed / ${(r.counts && r.counts.failed) || 0} failed`
  );
  logTerm(lastTestOutput);
  try {
    renderLevel(await InterviewAPI.level(sessionId));
  } catch {
    /* step panel is optional for older sessions */
  }
}

async function submit() {
  const dirtyCount = openTabs.filter((p) => models[p] && models[p].dirty).length;
  const modal = document.getElementById("submitModal");
  document.getElementById("submitDirtyLine").textContent =
    "Unsaved files: " + dirtyCount + (dirtyCount ? " (will be saved)" : "");
  document.getElementById("submitSummary").textContent =
    "Score this attempt. You can still open the workspace afterward in read-only mode.";
  modal.classList.remove("hidden");
  const close = () => modal.classList.add("hidden");
  document.getElementById("closeSubmit").onclick = close;
  document.getElementById("cancelSubmit").onclick = close;
  document.getElementById("confirmSubmit").onclick = async () => {
    close();
    for (const p of openTabs) {
      if (models[p] && models[p].dirty) {
        await InterviewAPI.saveFile(sessionId, p, models[p].model.getValue(), { source: "candidate" });
        models[p].saved = models[p].model.getValue();
        models[p].dirty = false;
      }
    }
    logTerm("Submitting…");
    setSessionStatus("busy", "Submitting");
    await InterviewAPI.submit(sessionId);
    location.href = "/session/" + sessionId + "/report";
  };
}

function setSessionStatus(state, label) {
  const el = document.getElementById("sessionStatus");
  if (!el) return;
  el.dataset.state = state || "ok";
  el.textContent = label || "Ready";
}

function parseUtc(v) {
  if (!v) return NaN;
  const s = String(v);
  // API may emit naive UTC ISO (no Z); treat as UTC to avoid local-offset timers.
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(s) ? s : s + "Z";
  return Date.parse(normalized);
}

function formatElapsed(ms) {
  const safe = Number.isFinite(ms) ? Math.max(0, ms) : 0;
  const s = Math.floor(safe / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return String(m).padStart(2, "0") + ":" + String(r).padStart(2, "0");
}

async function openDiff() {
  const summary = await InterviewAPI.diffSummary(sessionId, true);
  const modal = document.getElementById("diffModal");
  modal.classList.remove("hidden");
  const list = document.getElementById("diffFiles");
  list.innerHTML = "";
  document.getElementById("diffView").textContent =
    `${summary.file_count} files · +${summary.additions} / -${summary.deletions}`;
  if (!(summary.files_changed || []).length) {
    list.innerHTML = '<p class="muted" style="padding:10px 12px;font-size:12px">No saved changes yet. Save a file (⌘S) to see it here.</p>';
  }
  for (const f of summary.files_changed || []) {
    const b = document.createElement("button");
    b.className = "file-item";
    b.type = "button";
    b.textContent = `${f.path} (+${f.additions}/-${f.deletions})`;
    b.onclick = async () => {
      const d = await InterviewAPI.diffFile(sessionId, f.path);
      document.getElementById("diffView").textContent = d.unified || "(no textual diff)";
    };
    b.ondblclick = () => {
      modal.classList.add("hidden");
      openFile(f.path);
    };
    list.appendChild(b);
  }
}

function renderLevel(level) {
  const ticketEl = document.getElementById("ticketBody");
  const stepNo = level.index + 1;
  const earlier = (level.earlier || []).map((step) => `<div class="step-card is-earlier">
    <p class="step-kicker">Step ${step.index + 1} of ${level.total} · ${esc(step.kind)}</p>
    <h3>${esc(step.title)}</h3>
    <p>${esc(step.body)}</p>
  </div>`).join("");
  const next = level.is_last
    ? `<p class="step-note">Last step. Submit when the tests pass.</p>`
    : `<button class="btn btn-secondary btn-sm" type="button" id="nextLevel"${level.can_advance ? "" : " disabled"}>Next step</button>
       <p class="step-note">${level.can_advance ? "Tests ran. You can open the next step." : "Run the tests for this step to unlock the next one."}</p>`;
  ticketEl.innerHTML = `<p class="step-problem">${esc(level.problem)}</p>${earlier}<div class="step-card">
    <p class="step-kicker">Step ${stepNo} of ${level.total} · ${esc(level.kind)}</p>
    <h3>${esc(level.title)}</h3>
    <p>${esc(level.body)}</p>
    <p class="step-note">The assistant can be wrong.</p>
    ${next}
  </div>`;
  const btn = document.getElementById("nextLevel");
  if (btn) {
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        renderLevel(await InterviewAPI.nextLevel(sessionId));
      } catch (e) {
        btn.disabled = false;
        PCUI.toast(e.message, { tone: "danger" });
      }
    };
  }
}

require(["vs/editor/editor.main"], async function () {
  monaco.editor.defineTheme("pc-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#0b0d11",
      "editorLineNumber.foreground": "#5c6370",
      "editor.selectionBackground": "#6ea8ff33",
      "editorCursor.foreground": "#11110f",
      "focusBorder": "#11110f66",
    },
  });
  editor = monaco.editor.create(document.getElementById("monacoHost"), {
    value: "",
    language: "plaintext",
    theme: "pc-dark",
    automaticLayout: true,
    minimap: { enabled: false },
    fontFamily: "IBM Plex Mono, ui-monospace, monospace",
    fontSize: 13,
    lineNumbers: "on",
    scrollBeyondLastLine: false,
    wordWrap: "on",
    padding: { top: 8 },
  });
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
    save().catch((e) => PCUI.toast(e.message, { tone: "danger" }));
  });

  const s = await InterviewAPI.getSession(sessionId);
  InterviewAPI.setToken(s.owner_token);
  sessionReadOnly = s.status !== "active";
  document.getElementById("slugLabel").textContent = s.challenge_slug;
  const started = s.started_at ? parseUtc(s.started_at) : Date.now();
  const tick = () => {
    document.getElementById("sessionTimer").textContent = formatElapsed(Date.now() - started);
  };
  tick();
  setInterval(tick, 1000);
  files = await InterviewAPI.listFiles(sessionId);
  renderTree();
  const ticketEl = document.getElementById("ticketBody");
  try {
    renderLevel(await InterviewAPI.level(sessionId));
  } catch {
    ticketEl.textContent = "This task has no steps yet.";
  }
  const readme = files.find((f) => f.path === "README.md");
  if (readme) {
    try {
      const file = await InterviewAPI.getFile(sessionId, readme.path);
      const text = typeof file === "string" ? file : (file.content || file.text || "");
      if (!ticketEl.querySelector(".step-card")) {
        ticketEl.textContent = text.slice(0, 4000) || "No ticket content.";
      }
    } catch {
      if (!ticketEl.querySelector(".step-card")) {
        ticketEl.textContent = "Open README.md in the editor for the full ticket.";
      }
    }
    await openFile(readme.path);
  }

});

document.querySelectorAll(".phase-bar button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".phase-bar button").forEach((b) => {
      b.classList.toggle("is-active", b === btn);
      b.setAttribute("aria-pressed", b === btn ? "true" : "false");
    });
  });
});

function syncCtxChips() {
  document.querySelectorAll("#ctxChips .ctx-chip").forEach((chip) => {
    const input = chip.querySelector("input");
    chip.dataset.on = input && input.checked ? "true" : "false";
  });
}
document.querySelectorAll("#ctxChips input").forEach((input) => {
  input.addEventListener("change", syncCtxChips);
});
syncCtxChips();

document.getElementById("saveBtn").onclick = () =>
  save().then(() => PCUI.toast("Saved", { tone: "success", timeout: 1600 })).catch((e) => PCUI.toast(e.message, { tone: "danger" }));
document.getElementById("testBtn").onclick = () => {
  setSessionStatus("busy", "Running");
  runCmd("run_tests")
    .then(() => setSessionStatus("ok", "Ready"))
    .catch((e) => { setSessionStatus("fail", "Error"); logTerm(String(e.message || e)); });
};
document.getElementById("relevantBtn").onclick = () => runCmd("run_targeted_tests").catch((e) => logTerm(String(e.message || e)));
document.getElementById("benchBtn").onclick = () => runCmd("run_benchmark").catch((e) => logTerm(String(e.message || e)));
document.getElementById("submitBtn").onclick = () => submit().catch((e) => PCUI.toast(e.message, { tone: "danger" }));
document.getElementById("diffBtn").onclick = () => openDiff().catch((e) => PCUI.toast(e.message, { tone: "danger" }));
document.getElementById("closeDiff").onclick = () => document.getElementById("diffModal").classList.add("hidden");
document.getElementById("fileSearch").oninput = (e) => renderTree(e.target.value);

/* Panel resize + persist */
(function initPanels() {
  const ws = document.getElementById("workspace");
  const css = getComputedStyle(document.documentElement);
  const tok = (name, fallback) => parseInt(css.getPropertyValue(name), 10) || fallback;
  const lim = {
    explorer: [tok("--pc-panel-min-explorer", 200), tok("--pc-panel-max-explorer", 280)],
    ai: [tok("--pc-panel-min-ai", 280), tok("--pc-panel-max-ai", 400)],
    term: [tok("--pc-panel-min-term", 160), tok("--pc-panel-max-term", 280)],
  };
  const clamp = (key, v) => Math.min(lim[key][1], Math.max(lim[key][0], v));
  const sizes = PCUI.loadPanelSizes("pc_ws_panels", {
    explorer: tok("--pc-explorer-w", 240), ai: tok("--pc-ai-w", 340), term: tok("--pc-term-h", 200),
    explorerHidden: false, aiHidden: false, termHidden: false,
  });
  sizes.explorer = clamp("explorer", sizes.explorer || 240);
  sizes.ai = clamp("ai", sizes.ai || 340);
  sizes.term = clamp("term", sizes.term || 200);
  function applySizes() {
    ws.style.setProperty("--pc-explorer-w", (sizes.explorerHidden ? 0 : sizes.explorer) + "px");
    ws.style.setProperty("--pc-ai-w", (sizes.aiHidden ? 0 : sizes.ai) + "px");
    ws.style.setProperty("--pc-term-h", (sizes.termHidden ? 0 : sizes.term) + "px");
    document.getElementById("explorerPanel").style.display = sizes.explorerHidden ? "none" : "";
    document.getElementById("aiPanel").style.display = sizes.aiHidden ? "none" : "";
    document.getElementById("termPanel").style.display = sizes.termHidden ? "none" : "";
  }
  applySizes();
  function drag(handle, onMove) {
    handle.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      handle.classList.add("is-dragging");
      const move = (ev) => onMove(ev);
      const up = () => {
        handle.classList.remove("is-dragging");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        PCUI.savePanelSizes("pc_ws_panels", sizes);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    });
  }
  drag(document.getElementById("resizeExplorer"), (ev) => {
    sizes.explorer = clamp("explorer", ev.clientX);
    applySizes();
  });
  drag(document.getElementById("resizeAi"), (ev) => {
    sizes.ai = clamp("ai", window.innerWidth - ev.clientX);
    applySizes();
  });
  drag(document.getElementById("resizeTerm"), (ev) => {
    const rect = ws.getBoundingClientRect();
    sizes.term = clamp("term", rect.bottom - ev.clientY);
    applySizes();
  });
  window.__pcTogglePanel = function (name) {
    if (name === "explorer") sizes.explorerHidden = !sizes.explorerHidden;
    if (name === "ai") sizes.aiHidden = !sizes.aiHidden;
    if (name === "term") sizes.termHidden = !sizes.termHidden;
    applySizes();
    PCUI.savePanelSizes("pc_ws_panels", sizes);
  };
})();

const palette = PCUI.createCommandPalette([
  { group: "Files", label: "Save file", shortcut: "⌘S", keywords: "save write", run: () => save().catch((e) => PCUI.toast(e.message, { tone: "danger" })) },
  { group: "Files", label: "Search files", keywords: "explorer find", run: () => document.getElementById("fileSearch")?.focus() },
  { group: "Testing", label: "Run tests", shortcut: "⌘Enter", keywords: "test", run: () => runCmd("run_tests") },
  { group: "Testing", label: "Relevant tests", keywords: "subset", run: () => document.getElementById("relevantBtn")?.click() },
  { group: "Testing", label: "Benchmark", keywords: "bench", run: () => document.getElementById("benchBtn")?.click() },
  { group: "Panels", label: "Toggle explorer", keywords: "files tree", run: () => window.__pcTogglePanel("explorer") },
  { group: "Panels", label: "Toggle AI panel", keywords: "assistant chat", run: () => window.__pcTogglePanel("ai") },
  { group: "Panels", label: "Toggle terminal", keywords: "output", run: () => window.__pcTogglePanel("term") },
  { group: "Session", label: "Review changes", keywords: "diff", run: () => openDiff() },
  { group: "Session", label: "Submit session", keywords: "finish", run: () => submit() },
  { group: "Navigation", label: "Open dashboard", keywords: "home", run: () => { location.href = "/dashboard"; } },
  { group: "Navigation", label: "Challenge library", keywords: "browse", run: () => { location.href = "/challenges"; } },
]);

(function offlineBanner() {
  let el = document.getElementById("pcOffline");
  if (!el) {
    el = document.createElement("div");
    el.id = "pcOffline";
    el.className = "pc-offline";
    el.hidden = navigator.onLine;
    el.textContent = "Offline — edits stay local until reconnect";
    document.body.appendChild(el);
  }
  const sync = () => {
    el.hidden = navigator.onLine;
    if (navigator.onLine) PCUI.toast("Back online", { tone: "success", timeout: 2000 });
  };
  window.addEventListener("offline", () => { el.hidden = false; });
  window.addEventListener("online", sync);
})();

(function moreMenu() {
  const btn = document.getElementById("moreBtn");
  const menu = document.getElementById("moreMenu");
  const place = () => {
    const r = btn.getBoundingClientRect();
    menu.style.top = r.bottom + 6 + "px";
    menu.style.right = Math.max(8, window.innerWidth - r.right) + "px";
    menu.style.left = "auto";
  };
  const items = () => Array.from(menu.querySelectorAll("[role=menuitem]"));
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = menu.classList.contains("hidden");
    menu.classList.toggle("hidden", !open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      place();
      if (e.detail === 0) items()[0]?.focus();
    }
  });
  menu.addEventListener("keydown", (e) => {
    const list = items();
    const i = list.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { e.preventDefault(); list[(i + 1) % list.length]?.focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); list[(i - 1 + list.length) % list.length]?.focus(); }
    if (e.key === "Escape") btn.focus();
  });
  document.addEventListener("click", () => {
    menu.classList.add("hidden");
    btn.setAttribute("aria-expanded", "false");
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      menu.classList.add("hidden");
      btn.setAttribute("aria-expanded", "false");
      document.getElementById("diffModal").classList.add("hidden");
      document.getElementById("submitModal").classList.add("hidden");
    }
  });
  menu.addEventListener("click", (e) => {
    const item = e.target.closest("[data-action]");
    if (!item) return;
    const a = item.dataset.action;
    if (a === "palette") palette.open();
    if (a === "toggle-explorer") window.__pcTogglePanel("explorer");
    if (a === "toggle-ai") window.__pcTogglePanel("ai");
    if (a === "toggle-term") window.__pcTogglePanel("term");
  });
})();

document.getElementById("chatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    document.getElementById("chatForm").requestSubmit();
  }
});

document.getElementById("chatForm").onsubmit = async (ev) => {
  ev.preventDefault();
  const message = document.getElementById("chatInput").value.trim();
  if (!message) return;
  const attached = [];
  if (document.getElementById("attachCurrent").checked && currentPath) attached.push(currentPath);
  let selected = null;
  if (document.getElementById("attachSelection").checked && editor) {
    const sel = editor.getModel().getValueInRange(editor.getSelection());
    if (sel) selected = sel;
  }
  logChat("user", message);
  document.getElementById("chatInput").value = "";
  const working = document.createElement("div");
  working.className = "chat-msg ai working";
  working.id = "aiWorking";
  working.innerHTML = `<strong>Assistant</strong><pre class="chat-body">Working…</pre>`;
  document.getElementById("chatLog").appendChild(working);
  document.getElementById("chatLog").scrollTop = document.getElementById("chatLog").scrollHeight;
  try {
    const r = await InterviewAPI.chat(sessionId, message, attached, {
      include_test_output: document.getElementById("attachTests").checked,
      selected_text: selected,
    });
    working.remove();
    if (document.getElementById("attachTests").checked && lastTestOutput) {
      // Context flag only — server does not auto-dump; append client-side note in UI.
    }
    logChat("ai", r.reply, true);
    lastProposed = (r.proposed_edits || [])[0] || null;
    const bar = document.getElementById("applyBar");
    if (lastProposed) {
      bar.classList.remove("hidden");
      bar.innerHTML = `Proposed edit <code>${esc(lastProposed.path)}</code>
        <button class="btn btn-secondary btn-sm" type="button" id="acceptAi">Accept</button>
        <button class="btn btn-ghost btn-sm" type="button" id="modifyAi">Apply as mixed</button>
        <button class="btn btn-quiet btn-sm" type="button" id="rejectAi">Reject</button>`;
      document.getElementById("acceptAi").onclick = () => applyDisposition("accepted");
      document.getElementById("modifyAi").onclick = () => applyDisposition("modified");
      document.getElementById("rejectAi").onclick = () => applyDisposition("rejected");
    } else {
      bar.classList.add("hidden");
    }
  } catch (e) {
    document.getElementById("aiWorking")?.remove();
    logChat("ai", "Error: " + e.message);
  }
};

async function applyDisposition(disposition) {
  if (!lastProposed) return;
  const path = lastProposed.path;
  let content = lastProposed.content;
  if (disposition === "modified" && currentPath === path && models[path]) {
    content = models[path].model.getValue();
  }
  if (disposition === "rejected") content = models[path] ? models[path].saved : "";
  let saved;
  try {
    saved = await InterviewAPI.applyAiEdit(sessionId, {
      path,
      content,
      disposition,
      proposed_content: lastProposed.content,
      base_revision: lastProposed.base_revision,
    });
  } catch (e) {
    PCUI.toast(e.message, { tone: "danger" });
    return;
  }
  if (disposition !== "rejected") {
    const next = (saved && saved.content) || content;
    if (!models[path]) await openFile(path);
    else {
      models[path].model.setValue(next);
      models[path].saved = next;
      models[path].dirty = false;
    }
  }
  document.getElementById("applyBar").classList.add("hidden");
  lastProposed = null;
  logTerm("AI edit " + disposition + " for " + path);
}
