const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

async function render(report) {
  const elements = new Map();
  const element = () => ({ innerHTML: "", removeAttribute() {}, addEventListener() {},
    querySelectorAll() { return []; }, querySelector() { return element(); } });
  const document = {
    getElementById(id) {
      if (["defendForm", "fbSend", "appealForm"].includes(id)) return null;
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    querySelectorAll() { return []; },
  };
  const PCUI = { reducedMotion: () => true, tabs() {}, mountAppNav() {}, emptyState: () => "" };
  const context = vm.createContext({ location: { pathname: "/report/owned-session" }, document,
    window: { PCUI }, PCUI, console,
    InterviewAPI: { report: async () => report, getSession: async () => ({}),
      defend: async () => ({ questions: [], answers: {} }) } });
  vm.runInContext(fs.readFileSync(__dirname + "/interview-report.js", "utf8"), context);
  await new Promise((resolve) => setImmediate(resolve));
  const html = elements.get("main").innerHTML;
  assert.doesNotMatch(html, /Could not load report/);
  return html;
}

test("pending report does not turn unassessed dimensions into zero grades", async () => {
  const html = await render({ total_score: 0, rubric: {}, timeline: [],
    assessment: { dimensions: {
      A_correctness: { label: "Functional correctness", weight: 35, rating: null, status: "not_assessed" },
      D_ai_leverage: { label: "AI oversight", weight: 10, rating: null, status: "not_applicable" },
    } } });
  assert.match(html, /Functional correctness/);
  assert.match(html, /Not assessed/);
  assert.match(html, /Not applicable/);
  assert.doesNotMatch(html, /0\s*\/\s*100|scoreRing|Category scores|0\/35/);
});

test("historical numerical heuristics remain suppressed and labels are escaped", async () => {
  const html = await render({ total_score: 99, timeline: [], rubric: {
    A_correctness: { score: 25, max: 25, label: "<script>unsafe</script>" },
  }, previous_attempt: { total_score: 95, rubric: { A_correctness: { score: 25, max: 25 } } } });
  assert.doesNotMatch(html, /99\s*\/\s*100|25\/25|<script>unsafe/);
  assert.match(html, /&lt;script&gt;unsafe&lt;\/script&gt;/);
});

test("published human practice ratings are shown while historical heuristics stay suppressed", async () => {
  const html = await render({ total_score: 0, timeline: [], assessment: {
    status: "reviewed_practice", total_score: 75, review_id: "owned-review",
    dimensions: { A_correctness: { label: "Functional correctness", rating: 3,
      status: "reviewed", rationale: "Verified source and independent checks." } },
  } });
  assert.match(html, /75 \/ 100/);
  assert.match(html, /3 \/ 4/);
  assert.match(html, /Human-reviewed practice rating/);
  assert.match(html, /Request an independent review/);
  assert.doesNotMatch(html, /0\s*\/\s*100|scoreRing/);
});

test("adjusted AI mode and unmet requirements remain explicit beside a score", async () => {
  const html = await render({ timeline: [], assessment: {
    status: "reviewed_practice", total_score: 75,
    comparison_notice: "AI judgment was not observed; adjusted total excludes this dimension.",
    review_flags: ["unmet_behavioral_requirements"],
    dimensions: { E_verification: { label: "Verification", weight: 20, rating: 4,
      status: "reviewed", rationale: "Independent counterexample checked." } }
  } });
  assert.match(html, /Verification · 20%/);
  assert.match(html, /adjusted total excludes this dimension/);
  assert.match(html, /Required behavior remains unmet/);
});
