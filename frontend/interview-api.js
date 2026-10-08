const InterviewAPI = {
  base: window.location.origin + "/api/interview",
  authBase: window.location.origin + "/api/auth",
  _refreshPromise: null,
  _readPending: new Map(),
  READ_CACHE_MS: 300000,
  editorToken: null,
  pendingWorkspaceRequests: 0,

  // Execution capacity and AI budgets answer with 429/503 plus Retry-After when
  // the system is saturated. Callers should wait that long rather than showing a
  // raw error: the request is queued or throttled, not broken.
  RETRYABLE_STATUSES: [429, 503],
  MAX_CAPACITY_WAIT_MS: 120000,

  _retryAfterMs(resp) {
    const raw = resp.headers.get("Retry-After");
    if (!raw) return null;
    const seconds = Number(raw);
    if (Number.isFinite(seconds) && seconds >= 0) return Math.min(seconds * 1000, this.MAX_CAPACITY_WAIT_MS);
    const when = Date.parse(raw);
    if (!Number.isNaN(when)) {
      return Math.max(0, Math.min(when - Date.now(), this.MAX_CAPACITY_WAIT_MS));
    }
    return null;
  },

  isRetryable(error) {
    return !!error && this.RETRYABLE_STATUSES.includes(error.status);
  },

  _get(key) {
    const s = sessionStorage.getItem(key);
    if (s !== null) return s;
    const l = localStorage.getItem(key);
    if (l !== null) {
      sessionStorage.setItem(key, l);
      localStorage.removeItem(key);
      return l;
    }
    return null;
  },

  _set(key, value) {
    sessionStorage.setItem(key, value);
    localStorage.removeItem(key);
  },

  _remove(key) {
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);
  },

  getToken() {
    return this._get("pc_session_token");
  },

  setToken(token) {
    this._set("pc_session_token", token);
  },

  getAccessToken() {
    return this._get("access_token") || this._get("pc_token");
  },

  setAccessAuth(accessToken, user, refreshToken) {
    this._set("access_token", accessToken);
    this._set("pc_token", accessToken);
    if (user) this._set("pc_user", JSON.stringify(user));
    if (refreshToken) {
      this._set("refresh_token", refreshToken);
      this._set("pc_refresh_token", refreshToken);
    }
  },

  getRefreshToken() {
    return this._get("pc_refresh_token") || this._get("refresh_token");
  },

  clearAccessAuth() {
    this.invalidateReads();
    ["access_token", "pc_token", "pc_user", "refresh_token", "pc_refresh_token", "pc_session_token"].forEach(
      (k) => this._remove(k)
    );
  },

  isLoggedIn() {
    return !!this.getAccessToken();
  },

  requireAuth(redirect) {
    if (this.isLoggedIn()) return true;
    const next = encodeURIComponent(redirect || window.location.pathname);
    window.location.href = "/login.html?next=" + next;
    return false;
  },

  authHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (this.editorToken) headers["X-Editor-Token"] = this.editorToken;
    const access = this.getAccessToken();
    if (access) {
      headers["Authorization"] = "Bearer " + access;
    } else {
      const sessionToken = this.getToken();
      if (sessionToken) headers["X-Session-Token"] = sessionToken;
    }
    return headers;
  },

  async _tryRefresh() {
    if (this._refreshPromise) return this._refreshPromise;
    const rt = this.getRefreshToken();
    if (!rt) return false;
    this._refreshPromise = (async () => {
      try {
        const resp = await fetch(this.authBase + "/refresh", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (!resp.ok) return false;
        const data = await resp.json();
        this.setAccessAuth(data.access_token, data.user, data.refresh_token);
        return true;
      } catch (_) {
        return false;
      } finally {
        this._refreshPromise = null;
      }
    })();
    return this._refreshPromise;
  },

  invalidateReads() {
    try {
      sessionStorage.setItem("pc_read_generation", String(Number(sessionStorage.getItem("pc_read_generation") || 0) + 1));
      for (let i = sessionStorage.length - 1; i >= 0; i--) {
        const key = sessionStorage.key(i);
        if (key?.startsWith("pc_read_v1:")) sessionStorage.removeItem(key);
      }
    } catch (_) {}
    this._readPending.clear();
  },

  async readCached(path, onUpdate, options = {}) {
    const publicRead = options.skipAuthRedirect && path !== "/challenges/progress" &&
      /^\/challenges(?:\/[^/?]+)?$/.test(path);
    let account, generation, key, cached;
    try {
      account = JSON.parse(this._get("pc_user") || "null")?.id;
      if (!publicRead && (!account || !this.isLoggedIn())) return this.request(path, options);
      generation = sessionStorage.getItem("pc_read_generation") || "0";
      key = publicRead ? "pc_public_read_v1:" + path : "pc_read_v1:" + account + ":" + path;
      cached = JSON.parse(sessionStorage.getItem(key) || "null");
    } catch (_) { return this.request(path, options); }
    let pending = this._readPending.get(key);
    if (!pending) {
      pending = this.request(path, options).then((data) => {
        try {
          if (publicRead || (generation === (sessionStorage.getItem("pc_read_generation") || "0") &&
              account === JSON.parse(this._get("pc_user") || "null")?.id && this.isLoggedIn())) {
            sessionStorage.setItem(key, JSON.stringify({ data, at: Date.now(), generation }));
            if (path === "/challenges/progress" && Array.isArray(data)) {
              // Only public metadata survives starting, submitting or leaving a session.
              const cards = data.map(({ slug, title, summary, type, stack, difficulty, estimated_minutes, featured_rank }) =>
                ({ slug, title, summary, type, stack, difficulty, estimated_minutes, featured_rank }));
              sessionStorage.setItem("pc_public_read_v1:/challenges", JSON.stringify({ data: cards, at: Date.now() }));
            }
          }
        } catch (_) {}
        return data;
      }).finally(() => {
        if (this._readPending.get(key) === pending) this._readPending.delete(key);
      });
      this._readPending.set(key, pending);
    }
    if (cached && (publicRead || cached.generation === generation) &&
        Date.now() - cached.at < (publicRead ? 86400000 : this.READ_CACHE_MS)) {
      // Revalidation never erases a usable cached view on a transient failure.
      pending.then((data) => {
        if ((sessionStorage.getItem("pc_read_generation") || "0") === generation &&
            this.isLoggedIn() && account === JSON.parse(this._get("pc_user") || "null")?.id && onUpdate) onUpdate(data);
      }).catch(() => {});
      return cached.data;
    }
    return pending;
  },

  readDashboard(onUpdate) {
    return this.readCached("/dashboard", onUpdate);
  },

  readChallengesProgress(onUpdate) {
    return this.readCached("/challenges/progress", onUpdate);
  },

  getCachedCatalog() {
    try {
      const cached = JSON.parse(sessionStorage.getItem("pc_public_read_v1:/challenges") || "null");
      if (cached && Date.now() - cached.at < 86400000 && Array.isArray(cached.data)) return cached.data;
    } catch (_) {}
    return null;
  },

  async request(path, options = {}, isRetry = false) {
    const writing = options.method && options.method !== "GET" &&
      /\/sessions\//.test(path) && !/\/(timer|events)$/.test(path);
    const changesProgress = options.method && options.method !== "GET" &&
      /^(\/sessions$|\/sessions\/[^/]+\/(submit|abandon|feedback)$|\/grading\/)/.test(path);
    if (changesProgress) this.invalidateReads();
    if (writing) this.pendingWorkspaceRequests += 1;
    try { return await this._request(path, options, isRetry); }
    finally {
      if (writing) this.pendingWorkspaceRequests -= 1;
      if (changesProgress) this.invalidateReads();
    }
  },

  async _request(path, options = {}, isRetry = false) {
    const resp = await fetch(this.base + path, {
      ...options,
      credentials: "include",
      headers: { ...this.authHeaders(), ...(options.headers || {}) },
    });
    if (resp.status === 401 && !options.skipAuthRedirect && !options.authRetried &&
        typeof PromptCodeAPI !== "undefined" && await PromptCodeAPI._tryRefresh()) {
      return this.request(path, { ...options, authRetried: true });
    }
    if (resp.status === 401 && !options.skipAuthRedirect) {
      if (!isRetry && (await this._tryRefresh())) {
        return this.request(path, options, true);
      }
      this.clearAccessAuth();
      this.requireAuth(window.location.pathname);
      throw new Error("Not authenticated");
    }
    if (!resp.ok) {
      let detail = resp.statusText;
      let requestId = resp.headers.get("X-Request-ID");
      try {
        const data = await resp.json();
        detail = data.detail || JSON.stringify(data);
      } catch (_) {}
      const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      err.status = resp.status;
      err.retryAfterMs = this._retryAfterMs(resp);
      err.retryable = this.isRetryable(err);
      if (requestId) err.requestId = requestId;
      throw err;
    }
    if (resp.status === 204) return null;
    return resp.json();
  },

  listChallenges(params = {}) {
    const q = new URLSearchParams();
    if (params.type) q.set("type", params.type);
    if (params.stack) q.set("stack", params.stack);
    const qs = q.toString();
    return this.request("/challenges" + (qs ? "?" + qs : ""), { skipAuthRedirect: true });
  },

  listChallengesProgress(params = {}) {
    const q = new URLSearchParams();
    if (params.type) q.set("type", params.type);
    if (params.stack) q.set("stack", params.stack);
    const qs = q.toString();
    return this.request("/challenges/progress" + (qs ? "?" + qs : ""));
  },

  getChallenge(slug, onUpdate) {
    return this.readCached("/challenges/" + encodeURIComponent(slug), onUpdate, { skipAuthRedirect: true });
  },

  startSession(slug) {
    if (!this.requireAuth("/challenges/" + encodeURIComponent(slug))) {
      return Promise.reject(new Error("Not authenticated"));
    }
    return this.request("/sessions", {
      method: "POST",
      body: JSON.stringify({ challenge_slug: slug }),
    }).then((s) => {
      this.setToken(s.owner_token);
      return s;
    });
  },

  getSession(id) {
    return this.request("/sessions/" + id);
  },

  async bootstrapSession(id) {
    try {
      return await this.request("/sessions/" + id + "/bootstrap");
    } catch (error) {
      // Allow frontend/backend deployments to roll independently.
      if (error.status !== 404) throw error;
      const [session, files, level] = await Promise.all([
        this.getSession(id), this.listFiles(id), this.level(id).catch(() => null),
      ]);
      return { session, files, level };
    }
  },

  timer(id, action, options = {}) {
    return this.request("/sessions/" + id + "/timer", {
      method: "POST", ...options,
      body: JSON.stringify({ action, editor_token: this.editorToken }),
    });
  },

  listFiles(id) {
    return this.request("/sessions/" + id + "/files");
  },

  getFile(id, path) {
    return this.request(
      "/sessions/" + id + "/files/" + path.split("/").map(encodeURIComponent).join("/")
    );
  },

  saveFile(id, path, content, meta = {}) {
    return this.request(
      "/sessions/" + id + "/files/" + path.split("/").map(encodeURIComponent).join("/"),
      {
        method: "PUT",
        body: JSON.stringify({
          content,
          base_revision: meta.base_revision,
          source: meta.source || "candidate",
          additions: meta.additions,
          deletions: meta.deletions,
        }),
      }
    );
  },

  level(id) {
    return this.request("/sessions/" + id + "/level");
  },

  nextLevel(id) {
    return this.request("/sessions/" + id + "/level/next", { method: "POST", body: "{}" });
  },

  runTests(id, commandId = "run_tests", opts = {}) {
    return this.request("/sessions/" + id + "/tests", {
      method: "POST",
      body: JSON.stringify({ command_id: commandId }),
    });
  },

  // Runs an advisory test command, waiting out explicit capacity throttling.
  //
  // The execution host is saturated when every slot is busy; it answers 429/503
  // with Retry-After instead of failing. Retrying here keeps that overload out of
  // the UI as an error and keeps the server's own backpressure signal intact.
  // `opts.onWait(attempt, waitMs)` lets the caller show a queued state.
  async runTestsQueued(id, commandId = "run_tests", opts = {}) {
    const deadline = Date.now() + (opts.maxWaitMs || 90000);
    let attempt = 0;
    for (;;) {
      try {
        return await this.runTests(id, commandId);
      } catch (err) {
        if (!this.isRetryable(err) || opts.signal?.aborted) throw err;
        const suggested = err.retryAfterMs != null ? err.retryAfterMs : 2000;
        const remaining = deadline - Date.now();
        if (remaining <= 0 || attempt >= (opts.maxAttempts || 12)) {
          err.queued = true;
          throw err;
        }
        attempt += 1;
        const waitMs = Math.min(suggested, remaining);
        if (typeof opts.onWait === "function") opts.onWait(attempt, waitMs, err);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
      }
    }
  },

  chat(id, message, attached_paths = [], opts = {}) {
    return this.request("/sessions/" + id + "/ai/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        attached_paths,
        include_test_output: !!opts.include_test_output,
        selected_text: opts.selected_text || null,
        test_output: opts.test_output || null,
      }),
    });
  },

  applyAiEdit(id, { path, content, disposition, proposed_content, base_revision }) {
    return this.request("/sessions/" + id + "/ai/apply", {
      method: "POST",
      body: JSON.stringify({ path, content, disposition, proposed_content, base_revision }),
    });
  },

  diffSummary(id, record = false) {
    return this.request("/sessions/" + id + "/diff?record=" + (record ? "true" : "false"));
  },

  diffFile(id, path) {
    return this.request(
      "/sessions/" + id + "/diff/" + path.split("/").map(encodeURIComponent).join("/")
    );
  },

  submit(id) {
    return this.request("/sessions/" + id + "/submit", { method: "POST", body: "{}" });
  },

  abandon(id, reason) {
    return this.request("/sessions/" + id + "/abandon", {
      method: "POST",
      body: JSON.stringify({ reason: reason || "" }),
    });
  },

  report(id) {
    return this.request("/sessions/" + id + "/report");
  },

  defend(id) {
    return this.request("/sessions/" + id + "/defend");
  },

  answerDefend(id, index, answer) {
    return this.request("/sessions/" + id + "/defend", {
      method: "POST",
      body: JSON.stringify({ index, answer }),
    });
  },

  postEvent(id, event_type, payload = {}) {
    return this.request("/sessions/" + id + "/events", {
      method: "POST",
      body: JSON.stringify({ event_type, payload }),
    });
  },

  dashboard() {
    return this.request("/dashboard");
  },

  feedback(id, payload = {}) {
    const body = {
      realism: payload.realism,
      difficulty: payload.difficulty,
      text: payload.text || "",
    };
    if (payload.ai_as_expected != null) body.ai_as_expected = payload.ai_as_expected;
    if (payload.confusing_or_broken != null) {
      body.confusing_or_broken = !!payload.confusing_or_broken;
    }
    if (payload.most_like_real_interview != null) {
      body.most_like_real_interview = !!payload.most_like_real_interview;
    }
    return this.request("/sessions/" + id + "/feedback", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async me() {
    const resp = await fetch(this.authBase + "/me", {
      credentials: "include",
      headers: this.authHeaders(),
    });
    if (!resp.ok) return null;
    return resp.json();
  },

  async logout() {
    const refresh = this.getRefreshToken();
    const headers = this.authHeaders();
    this.clearAccessAuth();
    if (refresh) {
      try {
        // Deliver revocation across navigation without delaying local sign-out.
        fetch(this.authBase + "/logout", {
          method: "POST",
          keepalive: true,
          credentials: "include",
          headers,
          body: JSON.stringify({ refresh_token: refresh }),
        }).catch(() => {});
      } catch (_) {}
    }
  },
};

window.InterviewAPI = InterviewAPI;
