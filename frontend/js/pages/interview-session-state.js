/* Session timing and draft storage, following the codepad's testable helper pattern. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.InterviewSessionState = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  class Clock {
    constructor(now = () => performance.now()) {
      this.now = now;
      this.elapsed = 0;
      this.lease = 0;
      this.anchor = now();
    }
    sync(session) {
      this.elapsed = Math.max(0, session.elapsed_ms || 0);
      this.lease = session.timer_running ? Math.max(0, session.timer_lease_ms || 0) : 0;
      this.anchor = this.now();
    }
    value() { return this.elapsed + Math.min(this.lease, Math.max(0, this.now() - this.anchor)); }
    pause() { this.elapsed = this.value(); this.lease = 0; }
    running() { return this.lease > Math.max(0, this.now() - this.anchor); }
  }

  class Drafts {
    constructor(storage, userId, sessionId) {
      this.storage = storage;
      this.prefix = "pc_draft:" + userId + ":" + sessionId + ":";
    }
    read(path) {
      try { return JSON.parse(this.storage.getItem(this.prefix + path)); } catch (_) { return null; }
    }
    write(path, value, saved, revision) {
      if (value === saved) return this.remove(path);
      this.storage.setItem(this.prefix + path, JSON.stringify({ value, saved, revision }));
    }
    remove(path) { this.storage.removeItem(this.prefix + path); }
    paths() {
      return Object.keys(this.storage).filter((key) => key.startsWith(this.prefix))
        .map((key) => key.slice(this.prefix.length));
    }
    clear() { this.paths().forEach((path) => this.remove(path)); }
  }
  return { Clock, Drafts };
});
