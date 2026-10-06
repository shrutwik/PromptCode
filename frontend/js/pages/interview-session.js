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
let pendingEdits = [];
let previewBackup = {};
let undoAi = [];
let viewedOnce = new Set();
let sessionReadOnly = false;

let sessionTerminal = false;
let currentSessionStatus = "active";
let editorOwned = false;
let workspaceFocused = document.hasFocus();
let autosaveBlocked = false;
let sessionReady = false;
let endingSession = false;
let allowNavigation = false;
let runPending = false;
let saveQueue = Promise.resolve();
let timerQueue = Promise.resolve();
const sessionClock = new InterviewSessionState.Clock();
const editorToken = crypto.randomUUID();
InterviewAPI.editorToken = editorToken;
const draftUser = (() => {
  try { return JSON.parse(InterviewAPI._get("pc_user") || "null")?.id || ""; }
  catch (_) { return ""; }
})();
const drafts = draftUser ? new InterviewSessionState.Drafts(localStorage, draftUser, sessionId) : null;
let draftWarningShown = false;

function persistDraft(path) {
  if (!drafts || !models[path] || sessionTerminal) return;
  const item = models[path];
  const value = Object.prototype.hasOwnProperty.call(previewBackup, path) ? previewBackup[path] : item.model.getValue();
  try { drafts.write(path, value, item.saved, item.revision); }
  catch (_) {
    if (!draftWarningShown) PCUI.toast("Local draft storage is unavailable. Save or export your work before leaving.", { tone: "danger" });
    draftWarningShown = true;
  }
}

function setEditable(editable) {
  editable = editable && !endingSession;
  sessionReadOnly = !editable;
  if (editor) editor.updateOptions({ readOnly: !editable });
  ["saveBtn", "testBtn", "relevantBtn", "benchBtn", "submitBtn"].forEach((id) => {
    const button = document.getElementById(id);
    if (button) button.disabled = !editable || endingSession;
  });
  document.getElementById("chatInput").disabled = !editable || endingSession;
}

function syncSession(snapshot) {
  currentSessionStatus = snapshot.status;
  sessionTerminal = !["active", "created"].includes(snapshot.status);
  sessionClock.sync(snapshot);
  setEditable(editorOwned && !sessionTerminal && snapshot.timer_running && workspaceFocused && !document.hidden && navigator.onLine);
  if (document.hidden || !workspaceFocused || !navigator.onLine) sessionClock.pause();
  setSessionStatus(sessionTerminal ? "idle" : snapshot.timer_running ? "active" : "idle",
    sessionTerminal ? snapshot.status : snapshot.timer_running ? "In progress" : "Paused");
  document.getElementById("abandonBtn").hidden = sessionTerminal;
}

function timerAction(action, options = {}) {
  timerQueue = timerQueue.catch(() => {}).then(async () => {
    if (!sessionReady || sessionTerminal) return;
    if (action !== "pause" && (document.hidden || !workspaceFocused || !navigator.onLine || (endingSession && action !== "heartbeat"))) return;
    try {
      const snapshot = await InterviewAPI.timer(sessionId, action, options);
      editorOwned = action !== "pause" && snapshot.timer_running;
      syncSession(snapshot);
      return snapshot;
    } catch (error) {
      editorOwned = false;
      sessionClock.pause();
      setEditable(false);
      setSessionStatus("idle", "Paused");
      if (!options.quiet) PCUI.toast(error.message || "Connection lost. Your timer is paused.", { tone: "danger" });
      if (options.requireSuccess) throw error;
    }
  });
  return timerQueue;
}

function requestPause(unloading = false) {
  editorOwned = false;
  sessionClock.pause();
  setEditable(false);
  Object.keys(models).forEach(persistDraft);
  if (!sessionReady || sessionTerminal) return;
  if (unloading) {
    // Authentication headers rule out sendBeacon; keepalive delivers the pause on navigation.
    fetch(InterviewAPI.base + "/sessions/" + sessionId + "/timer", {
      method: "POST", keepalive: true, credentials: "include",
      headers: InterviewAPI.authHeaders(),
      body: JSON.stringify({ action: "pause", editor_token: editorToken }),
    }).catch(() => {});
  } else {
    timerAction("pause", { quiet: true, skipAuthRedirect: true });
  }
}

function hasPendingWork() { return endingSession || runPending || InterviewAPI.pendingWorkspaceRequests > 0; }
function requireEditing() {
  if (sessionReadOnly || endingSession) throw new Error("The session will resume automatically when it is active and connected.");
}

function enqueueSave(path, { finishing = false } = {}) {
  const operation = saveQueue.catch(() => {}).then(async () => {
    if (finishing) {
      if (!endingSession || !editorOwned || sessionTerminal) throw new Error("The session must be active and connected before saving.");
    } else {
      requireEditing();
    }
    const item = models[path];
    if (!item || item.model.getValue() === item.saved) return;
    const content = item.model.getValue();
    const result = await InterviewAPI.saveFile(sessionId, path, content,
      { source: "candidate", base_revision: item.revision });
    autosaveBlocked = false;
    item.saved = content;
    item.revision = result.revision;
    item.dirty = item.model.getValue() !== content;
    persistDraft(path);
    updateDirtyPill();
    renderTabs();
  });
  saveQueue = operation;
  return operation;
}

window.addEventListener("beforeunload", (event) => {
  Object.keys(models).forEach(persistDraft);
  if (!allowNavigation && !sessionTerminal && (hasPendingWork() || Object.values(models).some((item) => item.model.getValue() !== item.saved))) {
    event.preventDefault(); event.returnValue = "";
  }
});
window.addEventListener("pagehide", () => requestPause(true));
document.addEventListener("visibilitychange", () => {
  if (document.hidden) requestPause();
  else timerAction("resume");
});
window.addEventListener("blur", () => { workspaceFocused = false; requestPause(); });
window.addEventListener("focus", () => { workspaceFocused = true; timerAction("resume"); });
window.addEventListener("offline", () => requestPause());
window.addEventListener("online", () => { autosaveBlocked = false; timerAction("resume"); });
window.addEventListener("pageshow", (event) => { if (event.persisted) timerAction("resume"); });
setInterval(() => {
  document.getElementById("sessionTimer").textContent = formatElapsed(sessionClock.value());
  if (sessionReady && !sessionTerminal && !sessionReadOnly && !sessionClock.running()) {
    sessionClock.pause(); setEditable(false);
    setSessionStatus("idle", "Paused");
  }
}, 1000);
setInterval(() => {
  if (workspaceFocused && !document.hidden && navigator.onLine && (!endingSession || editorOwned)) {
    timerAction(endingSession || !sessionReadOnly ? "heartbeat" : "resume", { quiet: true });
  }
}, 10000);
setInterval(() => {
  if (!autosaveBlocked && !sessionReadOnly && !hasPendingWork() && !pendingEdits.length && workspaceFocused && navigator.onLine && !document.hidden) {
    saveDirtyModels().catch((error) => { autosaveBlocked = true; PCUI.toast(error.message, { tone: "danger" }); });
  }
}, 5000);

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

function renderReadme(el, text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let inCode = false;
  let para = [];
  const flush = () => {
    if (!para.length) return;
    html += `<p>${para.join("<br>")}</p>`;
    para = [];
  };
  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      flush();
      if (!inCode) html += "<pre>";
      else html += "</pre>";
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      html += esc(line) + "\n";
      continue;
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      flush();
      const tag = "h" + heading[1].length;
      html += `<${tag}>${esc(heading[2])}</${tag}>`;
      continue;
    }
    if (!line.trim()) {
      flush();
      continue;
    }
    para.push(esc(line));
  }
  flush();
  if (inCode) html += "</pre>";
  el.classList.add("is-readme");
  el.innerHTML = html || "<p>No task description.</p>";
}
function updateDirtyPill() {
  const dirty = Object.values(models).some((item) => item.dirty);
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
  tabs.replaceChildren();
  for (const path of openTabs) {
    const name = path.split("/").pop();
    const tab = document.createElement("div");
    tab.className = "tab" + (path === currentPath ? " active" : "");
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", path === currentPath ? "true" : "false");
    const label = document.createElement("button");
    label.type = "button";
    label.className = "tab-label";
    label.title = path;
    label.textContent = name + (models[path] && models[path].dirty ? " ●" : "");
    label.onclick = () => openFile(path);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "tab-close";
    close.setAttribute("aria-label", "Close " + name);
    close.textContent = "×";
    close.onclick = (ev) => {
      ev.stopPropagation();
      closeTab(path);
    };
    tab.appendChild(label);
    tab.appendChild(close);
    tabs.appendChild(tab);
  }
}

function closeTab(path) {
  const idx = openTabs.indexOf(path);
  if (idx < 0) return;
  openTabs.splice(idx, 1);
  if (currentPath !== path) {
    renderTabs();
    return;
  }
  const next = openTabs[Math.min(idx, openTabs.length - 1)];
  if (next) {
    openFile(next);
    return;
  }
  currentPath = null;
  if (editor) editor.setModel(null);
  document.getElementById("pathLabel").textContent = "Select a file";
  document.getElementById("langLabel").textContent = "";
  renderTabs();
  renderTree(document.getElementById("fileSearch").value);
  updateDirtyPill();
}

async function openFile(path) {
  if (!editor) return;
  if (currentPath && models[currentPath]) {
    models[currentPath].dirty =
      models[currentPath].model.getValue() !== models[currentPath].saved;
  }
  if (!models[path]) {
    const data = await InterviewAPI.getFile(sessionId, path);
    const uri = monaco.Uri.parse(
      "file:///" + path.split("/").map(encodeURIComponent).join("/")
    );
    const model = monaco.editor.createModel(data.content, langFor(path), uri);
    const detected = (window.InterviewPad || { detectIndent: () => ({ insertSpaces: true, tabSize: 4 }) })
      .detectIndent(data.content);
    model.updateOptions({
      tabSize: detected.tabSize,
      indentSize: detected.tabSize,
      insertSpaces: detected.insertSpaces,
    });
    model.onDidChangeContent(() => {
      if (!models[path]) return;
      models[path].dirty = model.getValue() !== models[path].saved;
      persistDraft(path);
      updateDirtyPill();
      renderTabs();
      renderTree(document.getElementById("fileSearch").value);
    });
    models[path] = { model, saved: data.content, revision: data.revision, dirty: false };
    const draft = drafts?.read(path);
    if (!sessionTerminal && draft && typeof draft.value === "string" && draft.value !== data.content) {
      const sameBase = draft.saved === data.content;
      if (sameBase || window.confirm("This file has a local draft and a newer saved version. Restore the local draft for review? Saving it will replace the saved version.")) {
        model.setValue(draft.value);
        PCUI.toast("Recovered your unsaved draft for " + path, { tone: "info" });
      }
    }
    if (!viewedOnce.has(path)) viewedOnce.add(path);
  }
  if (!openTabs.includes(path)) openTabs.push(path);
  currentPath = path;
  editor.setModel(models[path].model);
  const indent = models[path].model.getOptions();
  editor.updateOptions({
    readOnly: sessionReadOnly,
    tabSize: indent.tabSize,
    indentSize: indent.indentSize || indent.tabSize,
    insertSpaces: indent.insertSpaces,
  });
  document.getElementById("pathLabel").textContent = path;
  document.getElementById("langLabel").textContent = langFor(path);
  renderTabs();
  renderTree(document.getElementById("fileSearch").value);
  updateDirtyPill();
}

function modelEntries() {
  return Object.keys(models).map((path) => ({
    path,
    value: models[path].model.getValue(),
    saved: models[path].saved,
  }));
}

async function saveDirtyModels(options = {}) {
  const pad = window.InterviewPad;
  const paths = pad ? pad.dirtyPaths(modelEntries()) : Object.keys(models).filter((p) => models[p].dirty);
  for (const path of paths) await enqueueSave(path, options);
  updateDirtyPill();
  renderTabs();
  renderTree(document.getElementById("fileSearch").value);
  return paths;
}

function replaceWhole(model, next) {
  if (model.getValue() === next) return;
  const range = model.getFullModelRange();
  model.pushEditOperations([], [{ range, text: next }], () => null);
}

async function save() {
  if (!currentPath || !models[currentPath]) throw new Error("No file selected");
  if (window.InterviewPad && window.InterviewPad.pathUnsafe(currentPath)) {
    throw new Error("This file cannot be changed");
  }
  await enqueueSave(currentPath);
  renderTree(document.getElementById("fileSearch").value);
  logTerm("Saved " + currentPath);

}

function revealTerminal() {
  const term = document.getElementById("termPanel");
  if (term && term.style.display === "none" && window.__pcTogglePanel) {
    window.__pcTogglePanel("term");
  }
}

async function runCmd(commandId) {
  requireEditing();
  if (hasPendingWork()) throw new Error("Wait for the current action to finish.");
  runPending = true;
  try { await runCommand(commandId); }
  finally { runPending = false; }
}

async function runCommand(commandId) {
  revealTerminal();
  setTermMeta("Saving open files…");
  const saved = await saveDirtyModels();
  setTermMeta(`Running <code>${esc(commandId)}</code>…`);
  logTerm(saved.length ? "Saved " + saved.join(", ") : "…");
  const r = await InterviewAPI.runTestsQueued(sessionId, commandId, {
    onWait(attempt, waitMs) {
      const seconds = Math.max(1, Math.round(waitMs / 1000));
      setSessionStatus("busy", "Queued");
      setTermMeta(
        `<span class="queued">QUEUED</span> · execution slots busy · retry ${attempt} in ${seconds}s`
      );
      if (attempt === 1) {
        logTerm("All execution slots are busy. Keeping your run queued — this can take a moment.");
      }
    },
  }).catch((err) => {
    if (err && err.queued) {
      setSessionStatus("fail", "Busy");
      logTerm(
        "Execution capacity stayed busy past the wait window. Your code is saved; run tests again shortly."
      );
      return null;
    }
    throw err;
  });
  if (!r) return;
  setSessionStatus(r.ok ? "ok" : "fail", r.ok ? "Ready" : "Tests failing");
  lastTestOutput = `$ ${r.command}\nexit ${r.exit_code} · ${r.duration_ms || 0}ms · isolation=${r.isolation}\n` +
    `counts ${JSON.stringify(r.counts || {})}\n\n${r.stdout}\n${r.stderr}`;
  setTermMeta(
    `<span class="${r.ok ? "ok" : "fail"}">${r.ok ? "ADVISORY PASS" : "ADVISORY FAIL"}</span> · ` +
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

function bindDialog(modal, primaryId) {
  let prev = null;
  let onKey = null;

  function focusable() {
    return Array.from(modal.querySelectorAll("button, a[href], input, select, textarea")).filter(
      (el) => !el.disabled && !el.hidden && el.getAttribute("tabindex") !== "-1"
    );
  }

  function close() {
    if (modal.classList.contains("hidden") && !onKey) return;
    modal.classList.add("hidden");
    if (onKey) {
      document.removeEventListener("keydown", onKey, true);
      onKey = null;
    }
    const back = prev;
    prev = null;
    if (back && back.isConnected && !modal.contains(back) && !back.closest(".hidden, [hidden]")) {
      back.focus();
    }
  }

  function open(restoreEl) {
    prev = restoreEl || document.activeElement;
    modal.classList.remove("hidden");
    if (onKey) document.removeEventListener("keydown", onKey, true);
    onKey = (e) => {
      if (modal.classList.contains("hidden")) return;
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        return;
      }
      if (e.key === "Tab") {
        const list = focusable();
        if (!list.length) {
          e.preventDefault();
          return;
        }
        const first = list[0];
        const last = list[list.length - 1];
        const active = document.activeElement;
        if (!modal.contains(active)) {
          e.preventDefault();
          (e.shiftKey ? last : first).focus();
          return;
        }
        if (e.shiftKey && active === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && active === last) {
          e.preventDefault();
          first.focus();
        }
        return;
      }
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        const active = document.activeElement;
        if (active && (active.tagName === "TEXTAREA" || active.tagName === "INPUT")) return;
        if (active && active.tagName === "BUTTON" && modal.contains(active)) return;
        const primary = document.getElementById(primaryId);
        if (primary && !primary.disabled) {
          e.preventDefault();
          primary.click();
        }
      }
    };
    document.addEventListener("keydown", onKey, true);
    const primary = document.getElementById(primaryId);
    (primary || focusable()[0])?.focus();
  }

  return { open, close };
}

const submitDialog = bindDialog(document.getElementById("submitModal"), "confirmSubmit");
const abandonDialog = bindDialog(document.getElementById("abandonModal"), "confirmAbandon");

async function submit() {
  requireEditing();
  const dirtyCount = (window.InterviewPad ? window.InterviewPad.dirtyPaths(modelEntries()) : []).length;
  document.getElementById("submitDirtyLine").textContent =
    "Unsaved files: " + dirtyCount + (dirtyCount ? " (will be saved)" : "");
  document.getElementById("submitSummary").textContent =
    "Get advisory practice feedback. You can still open the workspace afterward in read-only mode.";
  const close = () => submitDialog.close();
  document.getElementById("closeSubmit").onclick = close;
  document.getElementById("cancelSubmit").onclick = close;
  document.getElementById("confirmSubmit").onclick = async () => {
    if (hasPendingWork()) { PCUI.toast("Wait for the current action to finish.", { tone: "info" }); return; }
    close();
    try {
      requireEditing();
      endingSession = true;
      setEditable(false);
      await saveDirtyModels({ finishing: true });
      logTerm("Submitting…");
      setSessionStatus("busy", "Submitting");
      await InterviewAPI.submit(sessionId);
      // Successful saves already remove their drafts. Preserve any later local edits.
      sessionTerminal = true;
      sessionClock.pause();
      location.href = "/session/" + sessionId + "/report";
    } catch (error) {
      endingSession = false;
      // A lost response may hide an accepted submission. Ask the server before retrying.
      try {
        const snapshot = await InterviewAPI.getSession(sessionId);
        syncSession(snapshot);
        if (snapshot.status === "submitted") {
          location.href = "/session/" + sessionId + "/report";
          return;
        }
      } catch (_) { requestPause(); }
      PCUI.toast(error.message, { tone: "danger" });
    }
  };
  submitDialog.open(document.getElementById("submitBtn"));
}

function openAbandon() {
  const more = document.getElementById("moreBtn");
  const menu = document.getElementById("moreMenu");
  menu.classList.add("hidden");
  more.setAttribute("aria-expanded", "false");
  const close = () => abandonDialog.close();
  document.getElementById("closeAbandon").onclick = close;
  document.getElementById("cancelAbandon").onclick = close;
  document.getElementById("pauseAndLeave").onclick = async () => {
    if (hasPendingWork()) { PCUI.toast("Wait for the current action to finish.", { tone: "info" }); return; }
    try {
      requireEditing();
      endingSession = true;
      setEditable(false);
      await saveDirtyModels({ finishing: true });
      await timerAction("pause", { requireSuccess: true });
      if (sessionClock.running()) throw new Error("Could not pause the session. Try again.");
      allowNavigation = true;
      location.href = "/dashboard";
    } catch (error) {
      endingSession = false;
      await timerAction("resume");
      PCUI.toast(error.message, { tone: "danger" });
    }
  };
  document.getElementById("confirmAbandon").onclick = async () => {
    if (hasPendingWork()) { PCUI.toast("Wait for the current action to finish.", { tone: "info" }); return; }
    const btn = document.getElementById("confirmAbandon");
    btn.disabled = true;
    try {
      endingSession = true;
      setEditable(false);
      await InterviewAPI.abandon(sessionId, "");
      sessionTerminal = true;
      sessionClock.pause();
      try { drafts?.clear(); } catch (_) {}
      abandonDialog.close();
      location.href = "/dashboard";
    } catch (err) {
      endingSession = false;
      try {
        const snapshot = await InterviewAPI.getSession(sessionId);
        if (snapshot.status === "abandoned") {
          sessionTerminal = true;
          try { drafts?.clear(); } catch (_) {}
          location.href = "/dashboard";
          return;
        }
        if (snapshot.status === "submitted") {
          sessionTerminal = true;
          location.href = "/session/" + sessionId + "/report";
          return;
        }
      } catch (_) { /* Keep the recovery draft when state cannot be confirmed. */ }
      await timerAction("resume");
      btn.disabled = false;
      PCUI.toast(err.message, { tone: "danger" });
    }
  };
  abandonDialog.open(more);
}

function setSessionStatus(state, label) {
  if (sessionReady && sessionReadOnly && !endingSession) {
    state = "idle"; label = sessionTerminal ? currentSessionStatus : "Paused";
  }
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

function setMainView(view) {
  const next = view === "code" ? "code" : "question";
  const panel = document.getElementById("explorerPanel");
  panel.dataset.explorer = next;
  panel.querySelectorAll(".view-toggle button").forEach((btn) => {
    const on = btn.dataset.view === next;
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.classList.toggle("is-active", on);
  });
  try { sessionStorage.setItem("pc_explorer_view", next); } catch (e) { /* ignore */ }
  if (window.__pcApplyPanelSizes) window.__pcApplyPanelSizes();
  if (editor) requestAnimationFrame(() => editor.layout());
}

document.querySelectorAll(".view-toggle button").forEach((btn) => {
  btn.addEventListener("click", () => setMainView(btn.dataset.view));
});
try {
  const savedView = sessionStorage.getItem("pc_explorer_view");
  if (savedView === "code" || savedView === "question") setMainView(savedView);
} catch (e) { /* ignore */ }

function renderLevel(level) {
  const ticketEl = document.getElementById("questionBody");
  ticketEl.classList.add("is-brief");
  ticketEl.classList.remove("is-readme");
  const guide = (level.guide || []).map((line) => `<li>${esc(line)}</li>`).join("");
  ticketEl.innerHTML = `<article class="brief">
    <p class="step-kicker">${esc(level.kind)}</p>
    <h3>${esc(level.title)}</h3>
    <p class="step-problem">${esc(level.problem)}</p>
    <h4 class="brief-label">The work</h4>
    <p>${esc(level.body)}</p>
    <h4 class="brief-label">How to work</h4>
    <ol class="brief-guide">${guide}</ol>
    <p class="step-note">The assistant can be wrong. Check it against the code, then submit when the tests pass.</p>
  </article>`;
}

function configureModuleResolution() {
  const ts = monaco.languages && monaco.languages.typescript;
  if (!ts) return;
  const options = {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.NodeJs,
    allowJs: true,
    allowNonTsExtensions: true,
    esModuleInterop: true,
  };
  ts.typescriptDefaults.setCompilerOptions(options);
  ts.javascriptDefaults.setCompilerOptions(options);
  ts.typescriptDefaults.setEagerModelSync(true);
  ts.javascriptDefaults.setEagerModelSync(true);
}

function bindPadKeys(ed) {
  const pad = window.InterviewPad;
  ed.addCommand(monaco.KeyCode.Tab, () => {
    if (sessionReadOnly || endingSession) return;
    const widget = document.querySelector("#monacoHost .suggest-widget");
    const open = widget && !widget.classList.contains("hidden") && widget.offsetHeight > 0;
    if (open) {
      ed.trigger("pc", "acceptSelectedSuggestion", null);
      return;
    }
    const model = ed.getModel();
    const sel = ed.getSelection();
    if (!model || !sel) return;
    const line = model.getLineContent(sel.startLineNumber);
    const action = pad
      ? pad.tabAction(line, sel.startColumn, sel.isEmpty(), sel.startLineNumber === sel.endLineNumber)
      : "indent";
    if (action === "indent") {
      ed.trigger("pc", "editor.action.indentLines", null);
      return;
    }
    const opts = model.getOptions();
    const unit = pad
      ? pad.indentUnit({ insertSpaces: opts.insertSpaces, tabSize: opts.tabSize })
      : "    ";
    ed.executeEdits("indent", [{ range: sel, text: unit, forceMoveMarkers: true }]);
  });
  ed.addCommand(monaco.KeyMod.Shift | monaco.KeyCode.Tab, () => {
    if (sessionReadOnly || endingSession) return;
    ed.trigger("pc", "editor.action.outdentLines", null);
  });
}

require(["vs/editor/editor.main"], async function () {
  monaco.editor.defineTheme("pc-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#0a0a0a",
      "editorLineNumber.foreground": "#6b675e",
      "editor.selectionBackground": "#3d5a80",
      "editor.selectionForeground": "#ffffff",
      "editor.inactiveSelectionBackground": "#2c415c",
      "editorCursor.foreground": "#f3f1ea",
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
    wrappingIndent: "same",
    padding: { top: 8 },
    tabSize: 4,
    indentSize: 4,
    insertSpaces: true,
    detectIndentation: true,
    autoIndent: "full",
    trimAutoWhitespace: false,
    useTabStops: true,
    stickyTabStops: true,
    tabCompletion: "off",
    fontLigatures: false,
    renderWhitespace: "selection",
    autoClosingBrackets: "languageDefined",
    autoClosingQuotes: "languageDefined",
  });
  configureModuleResolution();
  bindPadKeys(editor);
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
    save().catch((e) => PCUI.toast(e.message, { tone: "danger" }));
  });

  if (!InterviewAPI.isLoggedIn()) {
    InterviewAPI.requireAuth("/session/" + sessionId);
    return;
  }
  const s = await InterviewAPI.getSession(sessionId);
  syncSession(s);
  document.getElementById("slugLabel").textContent = s.challenge_slug;
  files = await InterviewAPI.listFiles(sessionId);
  renderTree();
  const ticketEl = document.getElementById("questionBody");
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
      if (!ticketEl.querySelector(".brief")) {
        renderReadme(ticketEl, text.slice(0, 4000) || "No task description.");
      }
    } catch {
      if (!ticketEl.querySelector(".brief")) {
        ticketEl.textContent = "Open the code view for the full task.";
      }
    }
    await openFile(readme.path);
  }
  // Start only after the workspace is usable; draft recovery precedes autosaving.
  if (!sessionTerminal) {
    for (const path of drafts?.paths() || []) {
      if (files.some((file) => file.path === path)) await openFile(path);
    }
  }
  sessionReady = true;
  if (!sessionTerminal) await timerAction("resume");

});

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
    explorer: [tok("--pc-panel-min-explorer", 200), Math.max(tok("--pc-panel-max-explorer", 280), 480)],
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
  function explorerWidth() {
    if (sizes.explorerHidden) return 0;
    const showingQuestion = document.getElementById("explorerPanel").dataset.explorer !== "code";
    return showingQuestion ? Math.max(sizes.explorer, 360) : sizes.explorer;
  }
  function applySizes() {
    ws.style.setProperty("--pc-explorer-w", explorerWidth() + "px");
    ws.style.setProperty("--pc-ai-w", (sizes.aiHidden ? 0 : sizes.ai) + "px");
    ws.style.setProperty("--pc-term-h", (sizes.termHidden ? 0 : sizes.term) + "px");
    document.getElementById("explorerPanel").style.display = sizes.explorerHidden ? "none" : "";
    document.getElementById("aiPanel").style.display = sizes.aiHidden ? "none" : "";
    document.getElementById("termPanel").style.display = sizes.termHidden ? "none" : "";
  }
  window.__pcApplyPanelSizes = applySizes;
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
  { group: "Navigation", label: "Practice", keywords: "home dashboard", run: () => { location.href = "/dashboard"; } },
  { group: "Navigation", label: "Progress", keywords: "scores skills trends", run: () => { location.href = "/progress"; } },
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
  const items = () => Array.from(menu.querySelectorAll("[role=menuitem]:not([hidden])"));
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
      const submitOpen = !document.getElementById("submitModal").classList.contains("hidden");
      const abandonOpen = !document.getElementById("abandonModal").classList.contains("hidden");
      if (submitOpen || abandonOpen) return;
      menu.classList.add("hidden");
      btn.setAttribute("aria-expanded", "false");
      document.getElementById("diffModal").classList.add("hidden");
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
    if (a === "abandon") openAbandon();
    if (a === "export") exportWork().catch((e) => PCUI.toast(e.message, { tone: "danger" }));
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
  if (sessionReadOnly || hasPendingWork()) return;
  const message = document.getElementById("chatInput").value.trim();
  if (!message) return;
  logChat("user", message);
  document.getElementById("chatInput").value = "";
  const working = document.createElement("div");
  working.className = "chat-msg ai working";
  working.id = "aiWorking";
  working.innerHTML = `<strong>Assistant</strong><pre class="chat-body">Working…</pre>`;
  document.getElementById("chatLog").appendChild(working);
  document.getElementById("chatLog").scrollTop = document.getElementById("chatLog").scrollHeight;
  try {
    const r = await InterviewAPI.chat(sessionId, message, [], {
      test_output: lastTestOutput || null,
    });
    working.remove();
    logChat("ai", r.reply, true);
    pendingEdits = r.proposed_edits || [];
    previewBackup = {};
    renderApplyBar();
  } catch (e) {
    document.getElementById("aiWorking")?.remove();
    logChat("ai", "Error: " + e.message);
  }
};

function renderApplyBar() {
  const bar = document.getElementById("applyBar");
  const plan = window.InterviewPad
    ? window.InterviewPad.proposalPlan(pendingEdits)
    : { usable: [], skipped: [] };
  bar.replaceChildren();
  if (!plan.usable.length) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  const note = document.createElement("span");
  note.textContent = "Nothing is written until you accept. Click a file to preview.";
  bar.appendChild(note);
  for (const edit of plan.usable) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-ghost btn-sm";
    button.textContent = edit.path;
    button.onclick = () => previewProposal(edit.path).catch((e) => PCUI.toast(e.message, { tone: "danger" }));
    bar.appendChild(button);
  }
  const accept = document.createElement("button");
  accept.type = "button";
  accept.className = "btn btn-secondary btn-sm";
  accept.textContent = "Accept";
  accept.onclick = () => applyDisposition("accepted");
  const reject = document.createElement("button");
  reject.type = "button";
  reject.className = "btn btn-quiet btn-sm";
  reject.textContent = "Reject";
  reject.onclick = () => applyDisposition("rejected");
  bar.append(accept, reject);
}

async function previewProposal(path) {
  requireEditing();
  const edit = (window.InterviewPad ? window.InterviewPad.proposalPlan(pendingEdits) : { usable: [] })
    .usable.find((item) => item.path === path);
  if (!edit) return;
  if (!models[path]) await openFile(path);
  else await openFile(path);
  if (!(path in previewBackup)) previewBackup[path] = models[path].model.getValue();
  replaceWhole(models[path].model, edit.content);
  models[path].dirty = models[path].model.getValue() !== models[path].saved;
  updateDirtyPill();
  renderTabs();
  logTerm("Preview only — " + path + " is not saved. Accept to keep it, Reject to restore.");
}

async function applyDisposition(disposition) {
  requireEditing();
  const plan = window.InterviewPad
    ? window.InterviewPad.proposalPlan(pendingEdits)
    : { usable: [] };
  if (!plan.usable.length) return;
  if (disposition === "rejected") {
    for (const edit of plan.usable) {
      if (models[edit.path] && Object.prototype.hasOwnProperty.call(previewBackup, edit.path)) {
        replaceWhole(models[edit.path].model, previewBackup[edit.path]);
        models[edit.path].dirty = models[edit.path].model.getValue() !== models[edit.path].saved;
      }
      try {
        await InterviewAPI.applyAiEdit(sessionId, {
          path: edit.path,
          content: models[edit.path] ? models[edit.path].saved : "",
          disposition: "rejected",
          proposed_content: edit.content,
          base_revision: edit.base_revision,
        });
      } catch (e) {
        PCUI.toast(e.message, { tone: "danger" });
      }
    }
    previewBackup = {};
    pendingEdits = [];
    renderApplyBar();
    updateDirtyPill();
    logTerm("AI edit rejected. Files were not changed.");
    return;
  }
  const applied = [];
  for (const edit of plan.usable) {
    let before = Object.prototype.hasOwnProperty.call(previewBackup, edit.path)
      ? previewBackup[edit.path]
      : null;
    if (before == null && models[edit.path]) before = models[edit.path].saved;
    if (before == null) {
      try {
        const existing = await InterviewAPI.getFile(sessionId, edit.path);
        before = typeof existing === "string" ? existing : (existing.content || "");
      } catch {
        before = "";
      }
    }
    let content = edit.content;
    let disp = "accepted";
    if (models[edit.path] && models[edit.path].model.getValue() !== edit.content) {
      content = models[edit.path].model.getValue();
      disp = "modified";
    }
    let saved;
    try {
      saved = await InterviewAPI.applyAiEdit(sessionId, {
        path: edit.path,
        content,
        disposition: disp,
        proposed_content: edit.content,
        base_revision: edit.base_revision,
      });
    } catch (e) {
      PCUI.toast(e.message, { tone: "danger" });
      pendingEdits = plan.usable.slice(plan.usable.indexOf(edit));
      undoAi = applied;
      renderApplyBar();
      if (applied.length) showUndo(applied.map((item) => item.path));
      return;
    }
    const next = (saved && saved.content) || content;
    if (!models[edit.path]) await openFile(edit.path);
    if (models[edit.path]) {
      replaceWhole(models[edit.path].model, next);
      models[edit.path].revision = saved.revision;
      models[edit.path].saved = next;
      models[edit.path].dirty = false;
    }
    applied.push({ path: edit.path, before });
  }
  undoAi = applied;
  previewBackup = {};
  pendingEdits = [];
  renderApplyBar();
  try {
    files = await InterviewAPI.listFiles(sessionId);
  } catch {
    /* tree refresh is optional */
  }
  renderTree(document.getElementById("fileSearch").value);
  updateDirtyPill();
  renderTabs();
  showUndo(applied.map((item) => item.path));
}

function showUndo(paths) {
  logTerm("Accepted AI edits for " + paths.join(", ") + ". Undo restores the previous text and saves it.");
  const meta = document.getElementById("termMeta");
  meta.textContent = "AI edits applied. ";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-ghost btn-sm";
  button.textContent = "Undo AI edits";
  button.onclick = () => undoAccepted().catch((e) => PCUI.toast(e.message, { tone: "danger" }));
  meta.appendChild(button);
}

async function undoAccepted() {
  requireEditing();
  const items = undoAi.slice();
  undoAi = [];
  for (const item of items) {
    if (window.InterviewPad && window.InterviewPad.pathUnsafe(item.path)) continue;
    const result = await InterviewAPI.saveFile(sessionId, item.path, item.before,
      { source: "candidate", base_revision: models[item.path]?.revision });
    if (!models[item.path]) await openFile(item.path);
    if (models[item.path]) {
      replaceWhole(models[item.path].model, item.before);
      models[item.path].revision = result.revision;
      models[item.path].saved = item.before;
      models[item.path].dirty = false;
    }
  }
  updateDirtyPill();
  renderTabs();
  renderTree(document.getElementById("fileSearch").value);
  logTerm("Restored " + items.map((item) => item.path).join(", "));
  setTermMeta("Undo saved.");
}


async function exportWork() {
  const contents = {};
  for (const file of files) {
    const local = drafts?.read(file.path);
    contents[file.path] = models[file.path]?.model.getValue() ?? local?.value ??
      (await InterviewAPI.getFile(sessionId, file.path)).content;
  }
  const url = URL.createObjectURL(new Blob([JSON.stringify(contents, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = "practice-" + sessionId + ".json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
