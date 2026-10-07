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
