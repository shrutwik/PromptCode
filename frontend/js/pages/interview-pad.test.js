const test = require("node:test");
const assert = require("node:assert/strict");
const pad = require("./interview-pad.js");

test("detects 4-space and 2-space indents without treating nested blocks as 8", () => {
  assert.deepEqual(pad.detectIndent("def f():\n    x = 1\n        y = 2\n"), {
    insertSpaces: true,
    tabSize: 4,
  });
  assert.deepEqual(pad.detectIndent("export function f() {\n  return 1;\n}\n"), {
    insertSpaces: true,
    tabSize: 2,
  });
  assert.equal(pad.detectIndent("\tx = 1\n").insertSpaces, false);
});

test("tab indents leading whitespace and inserts a unit inside a line", () => {
  assert.equal(pad.tabAction("    name", 3, true, true), "indent");
  assert.equal(pad.tabAction("    name", 6, true, true), "insert");
  assert.equal(pad.tabAction("name", 1, false, false), "indent");
  assert.equal(pad.indentUnit({ insertSpaces: true, tabSize: 2 }), "  ");
  assert.equal(pad.indentUnit({ insertSpaces: false, tabSize: 4 }), "\t");
});

test("run saves only dirty, writable files", () => {
  assert.deepEqual(
    pad.dirtyPaths([
      { path: "src/a.py", value: "x\n", saved: "y\n" },
      { path: "src/b.py", value: "same\n", saved: "same\n" },
      { path: "pytest.ini", value: "nope\n", saved: "old\n" },
    ]),
    ["src/a.py"]
  );
});

test("AI proposals stay out of blocked and frozen paths", () => {
  const plan = pad.proposalPlan([
    { path: "src/app.py", content: "print(1)\n", base_revision: 2 },
    { path: "SOLUTION.md", content: "secret\n", base_revision: 1 },
    { path: "../etc/passwd", content: "no\n", base_revision: 1 },
    { path: "package.json", content: "{}\n", base_revision: 1 },
    { path: "src/util.py", content: "def f():\n    return 1\n", base_revision: 4 },
  ]);
  assert.deepEqual(
    plan.usable.map((edit) => edit.path),
    ["src/app.py", "src/util.py"]
  );
  assert.equal(plan.skipped.includes("SOLUTION.md"), true);
});
