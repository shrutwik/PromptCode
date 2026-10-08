const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
function page() {
  const main = { innerHTML: "", isConnected: true, removeAttribute() {} };
  const calls = [], resolves = {};
  const context = { location: { pathname: "/challenges/demo" },
    document: { getElementById: (id) => id === "main" ? main : null },
    PCUI: { esc: (v) => String(v ?? "") }, window: {},
    InterviewAPI: { requireAuth: () => true,
      getChallenge: () => { calls.push("detail"); return new Promise((resolve) => { resolves.detail = resolve; }); },
      listChallengesProgress: () => { calls.push("progress"); return new Promise((resolve, reject) => { resolves.progress = resolve; resolves.fail = reject; }); } } };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(__dirname + "/interview-challenge.js", "utf8"), context);
  return { main, calls, resolves };
}
test("brief requests start together and description renders before progress", async () => {
  const p = page();
  assert.deepEqual(p.calls, ["progress", "detail"]);
  p.resolves.detail({ title: "Task", readme: "Describe the bug" });
  await new Promise(setImmediate);
  assert.match(p.main.innerHTML, /Describe the bug/);
  assert.match(p.main.innerHTML, /disabled>Checking your sessions/);
  p.resolves.progress([{ slug: "demo", active_session_id: "owned" }]);
  await new Promise(setImmediate);
  assert.match(p.main.innerHTML, /Resume session/);
  assert.doesNotMatch(p.main.innerHTML, /Checking your sessions/);
});
test("failed progress does not enable starting an unknown attempt", async () => {
  const p = page();
  p.resolves.fail(new Error("offline"));
  p.resolves.detail({ title: "Task" });
  await new Promise(setImmediate);
  assert.match(p.main.innerHTML, /disabled>Could not check your sessions/);
  assert.doesNotMatch(p.main.innerHTML, /id="startBtn"/);
});
test("late response cannot render into a different route", async () => {
  const p = page();
  p.main.isConnected = false;
  p.resolves.detail({ title: "Old route" });
  p.resolves.progress([]);
  await new Promise(setImmediate);
  assert.equal(p.main.innerHTML, "");
});

test("candidate sees rubric weights and anchors before starting", async () => {
  const p = page();
  p.resolves.detail({ title: "Task", grading_criteria: {
    notice: "Research-informed pilot; optional discussion is ungraded.",
    dimensions: { A_correctness: { label: "Functional correctness", weight: 30,
      anchors: { 0: "Core behavior fails", 3: "Meets the stated contract" } },
      E_verification: { label: "Verification", weight: 20, anchors: { 4: "Independent counterexample" } } }
  } });
  await new Promise(setImmediate);
  assert.match(p.main.innerHTML, /Functional correctness · 30%/);
  assert.match(p.main.innerHTML, /Verification · 20%/);
  assert.match(p.main.innerHTML, /Meets the stated contract/);
  assert.match(p.main.innerHTML, /optional discussion is ungraded/);
  assert.doesNotMatch(p.main.innerHTML, /What you ask and accept is logged and scored/);
});
