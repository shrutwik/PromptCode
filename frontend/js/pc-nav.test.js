const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
function shell() {
  const listeners = {}, requests = [], resolves = {}, loaded = [], fullNavigations = [];
  const location = { origin: "https://app.test", href: "https://app.test/dashboard", pathname: "/dashboard", search: "" };
  location.assign = (href) => fullNavigations.push(href);
  let main = root();
  function root() {
    return { dataset: {}, setAttribute() {}, focus() {}, cloneNode: () => root(),
      replaceWith(next) { main = next; } };
  }
  const document = {
    title: "Practice", addEventListener: (name, fn) => { listeners[name] = fn; },
    getElementById: () => main, querySelectorAll: () => [],
    createElement: () => ({ dataset: {}, remove() {} }),
    body: { appendChild(script) { loaded.push(script.src); script.onload(); } },
  };
  const history = { state: {}, replaceState(state) { this.state = state; },
    pushState(state, _, href) { this.state = state; const u = new URL(href, location.href); Object.assign(location, { href: u.href, pathname: u.pathname, search: u.search }); } };
  const context = { document, location, history, URL, navigator: {}, scrollX: 0, scrollY: 0, scrollTo() {},
    DOMParser: class { parseFromString(name) {
      return { title: name, getElementById: () => root(),
        querySelectorAll: () => [{ src: "/static/js/pages/interview-" + name + ".js", getAttribute() { return this.src; } }] };
    } },
    fetch: (path) => { requests.push(path); return new Promise((resolve) => { resolves[path] = (name, ok = true) => resolve({ ok, text: async () => name }); }); },
    addEventListener: (name, fn) => { listeners[name] = fn; },
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(__dirname + "/pc-nav.js", "utf8"), context);
  return { nav: context.PCNav, document, history, listeners, requests, resolves, loaded, fullNavigations, location,
    get main() { return main; } };
}
test("navigation keeps the document and reuses cached route markup", async () => {
  const p = shell(), doc = p.document;
  const first = p.nav.go("/challenges");
  p.resolves["/challenges"]("challenges");
  await first;
  assert.equal(p.document, doc);
  assert.equal(p.location.pathname, "/challenges");
  assert.equal(p.loaded.length, 1);
  await p.nav.go("/challenges");
  assert.equal(p.requests.length, 1);
});
test("newer navigation wins when HTML responses arrive out of order", async () => {
  const p = shell();
  const old = p.nav.go("/challenges"), fresh = p.nav.go("/progress");
  p.resolves["/progress"]("progress");
  await fresh;
  p.resolves["/challenges"]("challenges");
  await old;
  assert.equal(p.location.pathname, "/progress");
  assert.equal(p.loaded.length, 1);
});
test("unsupported or failed routes retain ordinary full navigation", async () => {
  const p = shell();
  await p.nav.go("/session/owned");
  assert.equal(p.requests.length, 0);
  const failing = p.nav.go("/progress");
  p.resolves["/progress"]("progress", false);
  await failing;
  assert.deepEqual(p.fullNavigations, ["https://app.test/session/owned", "https://app.test/progress"]);
});
test("modified clicks and external links are not intercepted", () => {
  const p = shell();
  let prevented = false;
  const target = { closest: () => ({ href: "https://app.test/challenges", hasAttribute: () => false }) };
  p.listeners.click({ target, button: 0, ctrlKey: true, preventDefault: () => { prevented = true; } });
  target.closest = () => ({ href: "https://external.test/challenges", hasAttribute: () => false });
  p.listeners.click({ target, button: 0, preventDefault: () => { prevented = true; } });
  assert.equal(prevented, false);
  assert.equal(p.requests.length, 0);
});
test("back navigation does not add another history entry", async () => {
  const p = shell();
  p.history.pushState = () => { throw new Error("unexpected history push"); };
  const back = p.nav.go("/progress", true);
  p.resolves["/progress"]("progress");
  await back;
  assert.equal(p.fullNavigations.length, 0);
  assert.equal(p.loaded.length, 1);
});
