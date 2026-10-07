const test = require("node:test");
const assert = require("node:assert/strict");
const { Clock, Drafts } = require("./interview-session-state.js");
const fs = require("node:fs");
const vm = require("node:vm");

function storage() {
  const values = {};
  return new Proxy({
    getItem: (key) => values[key] ?? null,
    setItem: (key, value) => { values[key] = value; },
    removeItem: (key) => { delete values[key]; },
  }, { ownKeys: () => Object.keys(values), getOwnPropertyDescriptor: () => ({ configurable: true, enumerable: true }) });
}

test("clock pauses, resumes and freezes at the server lease", () => {
  let now = 0;
  const clock = new Clock(() => now);
  clock.sync({ elapsed_ms: 12000, timer_running: true, timer_lease_ms: 30000 });
  now = 5000;
  clock.pause();
  now = 500000;
  assert.equal(clock.value(), 17000);
  clock.sync({ elapsed_ms: 17000, timer_running: true, timer_lease_ms: 30000 });
  now += 90000;
  assert.equal(clock.value(), 47000);
  assert.equal(clock.running(), false);
  clock.sync({ elapsed_ms: 23000, timer_running: false });
  now += 999999;
  assert.equal(clock.value(), 23000);
});

test("draft recovery is isolated by account and attempt, and survives reopening", () => {
  const local = storage();
  const first = new Drafts(local, "owner", "session1");
  first.write("src/a.py", "unsaved", "saved", 3);
  assert.equal(new Drafts(local, "owner", "session1").read("src/a.py").value, "unsaved");
  assert.equal(new Drafts(local, "other", "session1").read("src/a.py"), null);
  assert.equal(new Drafts(local, "owner", "session2").read("src/a.py"), null);
  assert.deepEqual(first.paths(), ["src/a.py"]);
  first.write("src/a.py", "saved", "saved", 4);
  assert.deepEqual(first.paths(), []);
});

function page() {
  let initialise;
  const elements = new Map();
  const events = {};
  const intervals = new Map();
  const listen = (name, callback) => { (events[name] ||= []).push(callback); };
  function element() {
    return {
      classList: { add() {}, remove() {}, toggle() {}, contains: () => true },
      style: { setProperty() {} }, dataset: {},
      setAttribute() {}, getAttribute() {}, addEventListener() {}, removeEventListener() {},
      querySelectorAll: () => [], querySelector: () => null,
      focus() {}, closest: () => null, contains: () => false,
      getBoundingClientRect: () => ({ bottom: 0, right: 0 }), appendChild() {},
    };
  }
  const toasts = [];
  const context = {
    InterviewSessionState: { Clock, Drafts },
    InterviewAPI: {
      _get: () => JSON.stringify({ id: "owner" }), pendingWorkspaceRequests: 0,
      timer: async (_, action) => ({ status: "active", elapsed_ms: 5000, timer_running: action !== "pause", timer_lease_ms: 30000 }),
      postEvent: async () => {},
    },
    PCUI: { toast: (message) => toasts.push(message), loadPanelSizes: (_, defaults) => defaults, createCommandPalette: () => ({}) },
    document: {
      getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
      querySelectorAll: () => [], addEventListener: (name, callback) => listen("document:" + name, callback), removeEventListener() {},
      documentElement: element(), activeElement: null, hidden: false, hasFocus: () => true,
    },
    location: { pathname: "/session/test", href: "/session/test" }, navigator: { onLine: true },
    localStorage: storage(), sessionStorage: storage(),
    crypto: { randomUUID: () => "editor-token-123456" },
    performance: { now: () => 0 }, getComputedStyle: () => ({ getPropertyValue: () => "" }),
    setInterval(callback, delay) { intervals.set(delay, callback); }, setTimeout() {}, requestAnimationFrame() {},
    require(_deps, callback) { initialise = callback; },
    addEventListener: listen, removeEventListener() {}, confirm: () => true,
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(__dirname + "/interview-session.js", "utf8"), context);
  vm.runInContext("sessionReady = true; sessionReadOnly = false; editorOwned = true; renderTabs = () => {}; renderTree = () => {};", context);
  return { context, elements, events, intervals, toasts, initialise: () => initialise(), run: (code) => vm.runInContext(code, context) };
}

function startupPage() {
  const p = page();
  p.context.InterviewAPI.isLoggedIn = () => true;
  p.context.monaco = {
    KeyMod: { Shift: 1, CtrlCmd: 2 }, KeyCode: { Tab: 1, KeyS: 2 },
    Uri: { parse: (value) => value },
    editor: {
      defineTheme() {},
      create: () => ({ addCommand() {}, updateOptions() {}, setModel() {} }),
      createModel(content) {
        let value = content;
        return { getValue: () => value, setValue: (next) => { value = next; },
          updateOptions() {}, onDidChangeContent() {},
          getOptions: () => ({ tabSize: 4, insertSpaces: true }) };
      },
    },
  };
  p.run('sessionReady = false; sessionReadOnly = true; renderLevel = () => {}; renderReadme = (el, text) => { el.textContent = text; };');
  return p;
}

test("page data starts before Monaco and is reused when the editor initializes", async () => {
  const p = startupPage();
  const calls = [];
  p.context.InterviewAPI.getSession = async () => {
    calls.push("session");
    return { status: "active", challenge_slug: "test", timer_running: false };
  };
  p.context.InterviewAPI.listFiles = async () => { calls.push("files"); return []; };
  p.context.InterviewAPI.level = async () => { calls.push("level"); return {}; };
  vm.runInContext(fs.readFileSync(__dirname + "/interview-session-bootstrap.js", "utf8"), p.context);
  assert.deepEqual(calls, ["session", "files", "level"]);
  assert.equal(p.run("sessionReady"), false);
  await p.initialise();
  assert.deepEqual(calls, ["session", "files", "level"]);
  assert.equal(p.run("sessionReady"), true);
  const html = fs.readFileSync(__dirname + "/../../interview-session.html", "utf8");
  assert.ok(html.indexOf("interview-session-bootstrap.js") < html.indexOf("/min/vs/loader.js"));
});

test("early data failure is handled until the editor consumes it", async () => {
  const p = startupPage();
  const failure = new Error("Network unavailable");
  p.context.InterviewAPI.getSession = async () => { throw failure; };
  p.context.InterviewAPI.listFiles = async () => [];
  p.context.InterviewAPI.level = async () => null;
  vm.runInContext(fs.readFileSync(__dirname + "/interview-session-bootstrap.js", "utf8"), p.context);
  assert.equal((await p.context.pcSessionBootstrap).error, failure);
  await assert.rejects(p.initialise(), failure);
  assert.equal(p.run("sessionReady"), false);
});

test("startup requests run concurrently and README is fetched once before timer resume", async () => {
  const p = startupPage();
  const calls = [];
  const resolve = {};
  for (const name of ["getSession", "listFiles", "level"]) {
    p.context.InterviewAPI[name] = () => {
      calls.push(name);
      return new Promise((done) => { resolve[name] = done; });
    };
  }
  p.context.InterviewAPI.getFile = async (_, path) => {
    calls.push(path);
    return { content: "# Task", revision: 7 };
  };
  p.context.InterviewAPI.timer = async (_, action) => {
    calls.push(action);
    assert.equal(p.run('models["README.md"].saved'), "# Task");
    assert.equal(p.run("sessionReady"), true);
    return { status: "active", timer_running: true, timer_lease_ms: 30000 };
  };
  const pending = p.initialise();
  assert.deepEqual(calls, ["getSession", "listFiles", "level"]);
  assert.equal(p.run("sessionReady"), false);
  resolve.getSession({ status: "active", challenge_slug: "test", timer_running: false });
  resolve.listFiles([{ path: "README.md" }]);
  resolve.level({});
  await pending;
  assert.deepEqual(calls, ["getSession", "listFiles", "level", "README.md", "resume"]);
  assert.equal(p.run('models["README.md"].revision'), 7);
});

test("startup tolerates unavailable steps and recovers drafts before resuming", async () => {
  const p = startupPage();
  p.context.InterviewAPI.getSession = async () => ({ status: "active", challenge_slug: "test", timer_running: false });
  p.context.InterviewAPI.listFiles = async () => [{ path: "README.md" }, { path: "src/a.py" }];
  p.context.InterviewAPI.level = async () => { throw new Error("Unavailable"); };
  p.context.InterviewAPI.getFile = async (_, path) => ({ content: path === "README.md" ? "# Task" : "saved", revision: 3 });
  p.run('drafts.write("src/a.py", "unsaved", "saved", 3);');
  p.context.InterviewAPI.timer = async () => {
    assert.equal(p.run('models["src/a.py"].model.getValue()'), "unsaved");
    return { status: "active", timer_running: true, timer_lease_ms: 30000 };
  };
  await p.initialise();
  assert.equal(p.run("sessionReady"), true);
});

test("save failure prevents submission and preserves the draft", async () => {
  const p = page();
  let submissions = 0;
  p.context.InterviewAPI.saveFile = async () => { throw new Error("Save failed"); };
  p.context.InterviewAPI.submit = async () => { submissions++; };
  p.context.InterviewAPI.getSession = async () => ({ status: "active", elapsed_ms: 5000, timer_running: true, timer_lease_ms: 30000 });
  p.run('models["src/a.py"] = { model: { getValue: () => "draft" }, saved: "old", dirty: true, revision: 1 }; persistDraft("src/a.py");');
  await p.run("submit()");
  await p.elements.get("confirmSubmit").onclick();
  assert.equal(submissions, 0);
  assert.equal(p.run('drafts.read("src/a.py").value'), "draft");
  assert.equal(p.context.location.href, "/session/test");
});

test("typing during a save keeps the later edit dirty and recoverable", async () => {
  const p = page();
  let resolve;
  p.context.InterviewAPI.saveFile = () => new Promise((done) => { resolve = done; });
  p.run('let text = "first"; models["src/a.py"] = { model: { getValue: () => text }, saved: "old", dirty: true, revision: 1 };');
  const saving = p.run('enqueueSave("src/a.py")');
  await new Promise(setImmediate);
  p.run('text = "later"');
  resolve({ revision: 2 });
  await saving;
  assert.equal(p.run('models["src/a.py"].dirty'), true);
  assert.equal(p.run('drafts.read("src/a.py").value'), "later");
});

test("lost submit response recovers the accepted report", async () => {
  const p = page();
  p.context.InterviewAPI.submit = async () => { throw new Error("Connection lost"); };
  p.context.InterviewAPI.getSession = async () => ({ status: "submitted", elapsed_ms: 5000, timer_running: false });
  await p.run("submit()");
  await p.elements.get("confirmSubmit").onclick();
  assert.equal(p.context.location.href, "/session/test/report");
  assert.equal(p.run("sessionTerminal"), true);
});

test("save-and-return stays on the page when pause is rejected", async () => {
  const p = page();
  p.context.InterviewAPI.timer = async () => { throw new Error("Pause failed"); };
  p.run("openAbandon()");
  await p.elements.get("pauseAndLeave").onclick();
  assert.equal(p.context.location.href, "/session/test");
  assert.equal(p.run("endingSession"), false);
});

test("discard waits for an in-flight action and sends no abandonment", async () => {
  const p = page();
  let discards = 0;
  p.context.InterviewAPI.abandon = async () => { discards++; };
  p.context.InterviewAPI.pendingWorkspaceRequests = 1;
  p.run("openAbandon()");
  await p.elements.get("confirmAbandon").onclick();
  assert.equal(discards, 0);
  assert.equal(p.context.location.href, "/session/test");
});

test("lost discard response recovers the ended attempt", async () => {
  const p = page();
  p.context.InterviewAPI.abandon = async () => { throw new Error("Connection lost"); };
  p.context.InterviewAPI.getSession = async () => ({ status: "abandoned" });
  p.run("openAbandon()");
  await p.elements.get("confirmAbandon").onclick();
  assert.equal(p.context.location.href, "/dashboard");
  assert.equal(p.run("sessionTerminal"), true);
});

test("an expired session keeps local drafts available for export", () => {
  const p = page();
  p.run('drafts.write("src/a.py", "unsaved", "saved", 1); syncSession({ status: "expired", elapsed_ms: 5000, timer_running: false });');
  assert.equal(p.run('drafts.read("src/a.py").value'), "unsaved");
  assert.equal(p.elements.get("submitBtn").disabled, true);
  assert.equal(p.elements.has("resumeTimerBtn"), false);
});

test("an initial snapshot owned by another tab cannot enable editing", () => {
  const p = page();
  p.run('editorOwned = false; syncSession({ status: "active", elapsed_ms: 5000, timer_running: true, timer_lease_ms: 30000 });');
  assert.equal(p.run("sessionReadOnly"), true);
  assert.equal(p.elements.get("submitBtn").disabled, true);
});


test("leaving the window pauses and returning resumes the same attempt", async () => {
  const p = page();
  const actions = [];
  p.context.InterviewAPI.timer = async (_, action) => {
    actions.push(action);
    return { status: "active", elapsed_ms: 5000, timer_running: action !== "pause", timer_lease_ms: 30000 };
  };
  p.events.blur[0]();
  await p.run("timerQueue");
  assert.equal(p.run("sessionReadOnly"), true);
  p.events.focus[0]();
  await p.run("timerQueue");
  assert.equal(p.run("sessionReadOnly"), false);
  assert.deepEqual(actions, ["pause", "resume"]);
});

test("hidden tabs and offline connections pause, then resume on return", async () => {
  const p = page();
  p.context.document.hidden = true;
  p.events["document:visibilitychange"][0]();
  await p.run("timerQueue");
  assert.equal(p.run("sessionReadOnly"), true);
  p.context.document.hidden = false;
  p.events["document:visibilitychange"][0]();
  await p.run("timerQueue");
  assert.equal(p.run("sessionReadOnly"), false);
  p.context.navigator.onLine = false;
  p.events.offline[0]();
  await p.run("timerQueue");
  assert.equal(p.run("sessionReadOnly"), true);
  p.context.navigator.onLine = true;
  p.events.online[0]();
  await p.run("timerQueue");
  assert.equal(p.run("sessionReadOnly"), false);
});

test("navigation sends a keepalive pause without resetting the attempt", () => {
  const p = page();
  let sent;
  p.context.InterviewAPI.base = "/api/interview";
  p.context.InterviewAPI.authHeaders = () => ({ Authorization: "Bearer test" });
  p.context.fetch = (url, options) => { sent = { url, options }; return Promise.resolve(); };
  p.events.pagehide[0]();
  assert.equal(sent.url, "/api/interview/sessions/test/timer");
  assert.equal(sent.options.keepalive, true);
  assert.equal(JSON.parse(sent.options.body).action, "pause");
  assert.equal(p.run("sessionReadOnly"), true);
});

test("an unsaved draft triggers a navigation warning", () => {
  const p = page();
  let prevented = false;
  p.run('models["src/a.py"] = { model: { getValue: () => "draft" }, saved: "old", dirty: true, revision: 1 };');
  p.events.beforeunload[0]({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(p.run('drafts.read("src/a.py").value'), "draft");
});


test("an earlier heartbeat cannot unlock the editor during submission", () => {
  const p = page();
  p.run('let readonly; editor = { updateOptions: (options) => { readonly = options.readOnly; } }; endingSession = true; setEditable(false);');
  p.run('syncSession({ status: "active", elapsed_ms: 5000, timer_running: true, timer_lease_ms: 30000 });');
  assert.equal(p.run("readonly"), true);
  assert.equal(p.run("sessionReadOnly"), true);
  assert.equal(p.elements.get("submitBtn").disabled, true);
});

test("final saves lock editing and preserve any later local changes", async () => {
  const p = page();
  let resolveSecond;
  let submissions = 0;
  p.context.InterviewAPI.saveFile = async (_, path) => {
    if (path.endsWith("b.py")) return new Promise((done) => { resolveSecond = done; });
    return { revision: 2 };
  };
  p.context.InterviewAPI.submit = async () => { submissions++; return {}; };
  p.run('let a = "first"; let readonly; editor = { updateOptions: (options) => { readonly = options.readOnly; } }; models["src/a.py"] = { model: { getValue: () => a }, saved: "old", dirty: true, revision: 1 }; models["src/b.py"] = { model: { getValue: () => "second" }, saved: "old", dirty: true, revision: 1 };');
  await p.run("submit()");
  const submitting = p.elements.get("confirmSubmit").onclick();
  await new Promise(setImmediate);
  assert.equal(p.run("readonly"), true);
  assert.equal(p.run("endingSession"), true);
  await p.elements.get("confirmSubmit").onclick();
  assert.equal(submissions, 0);
  // Even programmatic edits cannot lose their recovery draft on successful submit.
  p.run('a = "later"; models["src/a.py"].dirty = true; persistDraft("src/a.py");');
  resolveSecond({ revision: 2 });
  await submitting;
  assert.equal(submissions, 1);
  assert.equal(p.run('drafts.read("src/a.py")?.value'), "later");
});

test("failed final saves release the submission lock and restore editing", async () => {
  const p = page();
  p.context.InterviewAPI.saveFile = async () => { throw new Error("Save failed"); };
  p.context.InterviewAPI.getSession = async () => ({ status: "active", elapsed_ms: 5000, timer_running: true, timer_lease_ms: 30000 });
  p.run('models["src/a.py"] = { model: { getValue: () => "draft" }, saved: "old", dirty: true, revision: 1 }; persistDraft("src/a.py");');
  await p.run("submit()");
  await p.elements.get("confirmSubmit").onclick();
  assert.equal(p.run("endingSession"), false);
  assert.equal(p.run("sessionReadOnly"), false);
  assert.equal(p.elements.get("submitBtn").disabled, false);
  assert.equal(p.run('drafts.read("src/a.py").value'), "draft");
});

test("navigation during final saving warns, but successful save-and-return does not", async () => {
  const p = page();
  let warned = false;
  p.run("endingSession = true");
  p.events.beforeunload[0]({ preventDefault() { warned = true; } });
  assert.equal(warned, true);
  p.run("endingSession = false; openAbandon()");
  await p.elements.get("pauseAndLeave").onclick();
  assert.equal(p.context.location.href, "/dashboard");
  warned = false;
  p.events.beforeunload[0]({ preventDefault() { warned = true; } });
  assert.equal(warned, false);
});


test("session offers leave choices without manual timer controls", () => {
  const html = fs.readFileSync(__dirname + "/../../interview-session.html", "utf8");
  assert.doesNotMatch(html, /resumeTimerBtn|pauseSessionBtn/);
  assert.match(html, /id="abandonBtn">Leave session/);
  assert.match(html, /id="pauseAndLeave">Save and come back/);
  assert.match(html, /id="confirmAbandon">Discard and start fresh next time/);
});

test("timer reconnects automatically after a failed heartbeat", async () => {
  const p = page();
  const actions = [];
  p.context.InterviewAPI.timer = async (_, action) => {
    actions.push(action);
    if (actions.length === 1) throw new Error("Connection lost");
    return { status: "active", elapsed_ms: 5000, timer_running: true, timer_lease_ms: 30000 };
  };
  p.intervals.get(10000)();
  await p.run("timerQueue");
  assert.equal(p.run("sessionReadOnly"), true);
  p.intervals.get(10000)();
  await p.run("timerQueue");
  assert.deepEqual(actions, ["heartbeat", "resume"]);
  assert.equal(p.run("sessionReadOnly"), false);
  assert.equal(p.run("sessionClock.running()"), true);
  assert.equal(p.run("sessionClock.elapsed"), 5000);
});

test("automatic retries leave hidden, offline, ending and terminal sessions paused", async () => {
  for (const state of ["document.hidden = true", "navigator.onLine = false", "workspaceFocused = false", "endingSession = true; editorOwned = false", "sessionTerminal = true"]) {
    const p = page();
    let calls = 0;
    p.context.InterviewAPI.timer = async () => { calls++; };
    p.run("sessionReadOnly = true; " + state);
    p.intervals.get(10000)();
    await p.run("timerQueue");
    assert.equal(calls, 0, state);
  }
});

test("save and come back saves changes and pauses at the saved elapsed time", async () => {
  const p = page();
  const actions = [];
  p.context.InterviewAPI.saveFile = async () => { actions.push("save"); return { revision: 2 }; };
  p.context.InterviewAPI.timer = async (_, action) => {
    actions.push(action);
    return { status: "active", elapsed_ms: 12000, timer_running: action !== "pause", timer_lease_ms: 30000 };
  };
  p.run('models["src/a.py"] = { model: { getValue: () => "draft" }, saved: "old", dirty: true, revision: 1 }; openAbandon();');
  await p.elements.get("pauseAndLeave").onclick();
  assert.deepEqual(actions, ["save", "pause"]);
  assert.equal(p.run('models["src/a.py"].saved'), "draft");
  assert.equal(p.run("sessionClock.value()"), 12000);
  assert.equal(p.run("sessionClock.running()"), false);
  assert.equal(p.context.location.href, "/dashboard");
});

test("discard ends the attempt, clears recovery drafts and returns to practice", async () => {
  const p = page();
  let discards = 0;
  p.context.InterviewAPI.abandon = async () => { discards++; };
  p.run('drafts.write("src/a.py", "draft", "old", 1); openAbandon();');
  await p.elements.get("confirmAbandon").onclick();
  assert.equal(discards, 1);
  assert.equal(p.run("sessionTerminal"), true);
  assert.equal(p.run('drafts.read("src/a.py")'), null);
  assert.equal(p.context.location.href, "/dashboard");
});
