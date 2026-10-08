const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
function storage() {
  const values = new Map();
  return { get length() { return values.size; }, key: (i) => [...values.keys()][i],
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)), removeItem: (key) => values.delete(key) };
}
function client(sessionStorage = storage()) {
  const context = { sessionStorage, localStorage: storage(), URLSearchParams,
    window: { location: { origin: "https://app.test" } } };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(__dirname + "/interview-api.js", "utf8"), context);
  const api = context.window.InterviewAPI;
  api.setAccessAuth("token", { id: "owner" });
  return { api, context, sessionStorage };
}
test("read cache survives navigation, returns immediately, and refreshes in background", async () => {
  const first = client();
  first.api.request = async () => ({ sessions: ["before"] });
  await first.api.readDashboard();
  const next = client(first.sessionStorage);
  let finish, updated;
  next.api.request = () => new Promise((resolve) => { finish = resolve; });
  const data = await next.api.readDashboard((value) => { updated = value; });
  assert.deepEqual(Array.from(data.sessions), ["before"]);
  finish({ sessions: ["after"] });
  await new Promise(setImmediate);
  assert.deepEqual(updated.sessions, ["after"]);
});
test("simultaneous page reads share one request", async () => {
  const { api } = client();
  let calls = 0, finish;
  api.request = () => { calls++; return new Promise((resolve) => { finish = resolve; }); };
  const a = api.readDashboard(), b = api.readDashboard();
  assert.equal(calls, 1);
  finish({ sessions: [] });
  await Promise.all([a, b]);
});
test("cache cannot cross accounts or survive logout", async () => {
  const { api, sessionStorage } = client();
  api.request = async () => ({ sessions: ["owner"] });
  await api.readDashboard();
  api.setAccessAuth("other-token", { id: "other" });
  api.request = async () => ({ sessions: ["other"] });
  assert.deepEqual((await api.readDashboard()).sessions, ["other"]);
  api.clearAccessAuth();
  assert.equal([...Array(sessionStorage.length)].some((_, i) => sessionStorage.key(i).startsWith("pc_read_v1:")), false);
});

test("logout clears auth immediately and revokes across navigation without waiting", async () => {
  const { api, context } = client();
  api._set("pc_refresh_token", "refresh");
  let sent;
  context.fetch = (url, options) => {
    sent = { url, options };
    return new Promise(() => {});
  };
  await api.logout();
  assert.equal(api.isLoggedIn(), false);
  assert.equal(api.getRefreshToken(), null);
  assert.equal(sent.url, "https://app.test/api/auth/logout");
  assert.equal(sent.options.keepalive, true);
  assert.equal(sent.options.headers.Authorization, "Bearer token");
  assert.equal(JSON.parse(sent.options.body).refresh_token, "refresh");
});

test("logout succeeds locally when server revocation fails", async () => {
  const { api, context } = client();
  api._set("refresh_token", "refresh");
  context.fetch = async () => { throw new Error("offline"); };
  await api.logout();
  assert.equal(api.isLoggedIn(), false);
});

test("legacy logout clears credentials and reaches the landing page without waiting", async () => {
  const context = { sessionStorage: storage(), localStorage: storage(),
    window: { location: { origin: "https://app.test", href: "/profile.html" } },
    document: { addEventListener() {} } };
  let sent;
  context.fetch = (_, options) => { sent = options; return new Promise(() => {}); };
  context.sessionStorage.setItem("pc_token", "token");
  context.sessionStorage.setItem("pc_refresh_token", "refresh");
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(__dirname + "/api.js", "utf8"), context);
  await vm.runInContext("PromptCodeAPI.logout()", context);
  assert.equal(context.window.location.href, "/");
  assert.equal(context.sessionStorage.getItem("pc_token"), null);
  assert.equal(sent.keepalive, true);
  assert.equal(sent.headers.Authorization, "Bearer token");
});
test("mutation invalidation stops an older in-flight response from repopulating cache", async () => {
  const { api, sessionStorage } = client();
  let finish;
  api.request = () => new Promise((resolve) => { finish = resolve; });
  const old = api.readDashboard();
  api.invalidateReads();
  finish({ sessions: ["old"] });
  await old;
  assert.equal(sessionStorage.getItem("pc_read_v1:owner:/dashboard"), null);
});
test("session mutations invalidate reads, but timer and file calls do not", async () => {
  const { api } = client();
  api._request = async () => ({});
  let invalidations = 0;
  api.invalidateReads = () => { invalidations++; };
  await api.request("/sessions/attempt/submit", { method: "POST" });
  assert.equal(invalidations, 2);
  await api.request("/sessions/attempt/timer", { method: "POST" });
  await api.request("/sessions/attempt/files/src/a.py", { method: "PUT" });
  assert.equal(invalidations, 2);
});
test("cached content remains usable on a background network failure", async () => {
  const { api } = client();
  api.request = async () => ({ sessions: ["cached"] });
  await api.readDashboard();
  api.request = async () => { throw new Error("offline"); };
  assert.deepEqual(Array.from((await api.readDashboard()).sessions), ["cached"]);
  await new Promise(setImmediate);
});
test("expired cache waits for fresh data", async () => {
  const { api, sessionStorage } = client();
  sessionStorage.setItem("pc_read_v1:owner:/dashboard", JSON.stringify({ data: { sessions: ["expired"] }, generation: "0", at: 0 }));
  api.request = async () => ({ sessions: ["fresh"] });
  assert.deepEqual((await api.readDashboard()).sessions, ["fresh"]);
});
test("a late cached refresh cannot render data after the account changes", async () => {
  const { api } = client();
  api.request = async () => ({ sessions: ["owner"] });
  await api.readDashboard();
  let finish, rendered = false;
  api.request = () => new Promise((resolve) => { finish = resolve; });
  await api.readDashboard(() => { rendered = true; });
  api.setAccessAuth("other-token", { id: "other" });
  finish({ sessions: ["private-owner-data"] });
  await new Promise(setImmediate);
  assert.equal(rendered, false);
});
test("public challenge text survives mutations and a longer workspace visit", async () => {
  const { api, sessionStorage } = client();
  api.request = async () => ({ readme: "Public task" });
  await api.getChallenge("demo");
  const key = "pc_public_read_v1:/challenges/demo";
  const cached = JSON.parse(sessionStorage.getItem(key));
  cached.at = Date.now() - 30 * 60000;
  sessionStorage.setItem(key, JSON.stringify(cached));
  api.invalidateReads();
  const next = client(sessionStorage);
  let finish;
  next.api.request = (path, options) => {
    assert.equal(path, "/challenges/demo");
    assert.equal(options.skipAuthRedirect, true);
    return new Promise((resolve) => { finish = resolve; });
  };
  assert.equal((await next.api.getChallenge("demo")).readme, "Public task");
  finish({ readme: "Updated public task" });
  await new Promise(setImmediate);
  assert.equal(JSON.parse(sessionStorage.getItem(key)).data.readme, "Updated public task");
});
test("catalog fallback retains public metadata without session IDs, attempts or scores", async () => {
  const { api, sessionStorage } = client();
  api.request = async () => [{ slug: "demo", title: "Task", stack: "Python", type: "bugfix",
    active_session_id: "private-session", best_score: 80, attempt_count: 3, progress: "in_progress" }];
  await api.readChallengesProgress();
  api.clearAccessAuth();
  assert.equal(sessionStorage.getItem("pc_read_v1:owner:/challenges/progress"), null);
  const cards = api.getCachedCatalog();
  assert.equal(cards[0].title, "Task");
  assert.equal(cards[0].active_session_id, undefined);
  assert.equal(cards[0].best_score, undefined);
  assert.equal(cards[0].attempt_count, undefined);
  assert.equal(cards[0].progress, undefined);
});
