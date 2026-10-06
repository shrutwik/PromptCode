/* Pure helpers for the interview codepad. No DOM, no shell. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.InterviewPad = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function detectIndent(text) {
    const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
    let tabLines = 0;
    let spaceLines = 0;
    const widths = [];
    for (const line of lines) {
      if (!/^\s+\S/.test(line)) continue;
      if (line[0] === "\t") tabLines += 1;
      else if (line[0] === " ") {
        spaceLines += 1;
        const match = /^( +)/.exec(line);
        if (match) widths.push(match[1].length);
      }
    }
    const insertSpaces = spaceLines >= tabLines;
    let tabSize = 4;
    if (insertSpaces && widths.length) {
      const gcd = widths.reduce((a, b) => {
        let x = a;
        let y = b;
        while (y) {
          const t = y;
          y = x % y;
          x = t;
        }
        return x || a;
      });
      if (gcd === 2 || gcd === 4 || gcd === 8) tabSize = gcd;
      else if (gcd > 0 && gcd < 8) tabSize = gcd;
    }
    return { insertSpaces, tabSize };
  }

  function indentUnit(opts) {
    const tabSize = opts && opts.tabSize > 0 ? opts.tabSize : 4;
    if (opts && opts.insertSpaces === false) return "\t";
    return " ".repeat(tabSize);
  }

  /** Tab indents a selection or leading whitespace; otherwise it inserts one unit. */
  function tabAction(line, column, selectionEmpty, sameLine) {
    const before = String(line || "").slice(0, Math.max(0, (column || 1) - 1));
    const inLeading = /^\s*$/.test(before);
    if (!selectionEmpty || !sameLine || inLeading) return "indent";
    return "insert";
  }

  function dirtyPaths(entries) {
    return (entries || [])
      .filter((entry) => entry && entry.path && entry.value !== entry.saved && !pathUnsafe(entry.path))
      .map((entry) => entry.path);
  }

  const BLOCKED = ["solution.md", "_audit_", "audit.md", "interviewer", ".reference"];
  const FROZEN = new Set([
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    "pyproject.toml",
    "pytest.ini",
    "setup.cfg",
    "setup.py",
    "conftest.py",
    "tox.ini",
    "requirements.txt",
    "dockerfile",
    "makefile",
  ]);

  function pathUnsafe(path) {
    if (!path || typeof path !== "string") return true;
    if (path.includes("\0") || path.includes("..") || path.startsWith("/") || path.startsWith("~")) return true;
    const norm = path.replace(/\\/g, "/").replace(/^\.\//, "").toLowerCase();
    if (!norm || BLOCKED.some((frag) => norm.includes(frag))) return true;
    const base = norm.split("/").pop();
    if (FROZEN.has(base) || base.startsWith(".env") || base.endsWith(".sh")) return true;
    return false;
  }

  function proposalPlan(edits) {
    const usable = [];
    const skipped = [];
    for (const edit of edits || []) {
      const path = edit && String(edit.path || "").trim();
      if (pathUnsafe(path)) {
        skipped.push(path || "(missing)");
        continue;
      }
      usable.push({
        path,
        content: String(edit.content == null ? "" : edit.content),
        base_revision: edit.base_revision,
      });
    }
    return { usable, skipped };
  }

  return { detectIndent, indentUnit, tabAction, dirtyPaths, pathUnsafe, proposalPlan };
});
