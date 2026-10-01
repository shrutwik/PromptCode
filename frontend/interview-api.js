const InterviewAPI = {
  base: window.location.origin + "/api/interview",
  authBase: window.location.origin + "/api/auth",

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
    if (refreshToken) this._set("refresh_token", refreshToken);
  },

  clearAccessAuth() {
    ["access_token", "pc_token", "pc_user", "refresh_token", "pc_session_token"].forEach(
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
    const sessionToken = this.getToken();
    if (sessionToken) headers["X-Session-Token"] = sessionToken;
    const access = this.getAccessToken();
    if (access) headers["Authorization"] = "Bearer " + access;
    return headers;
  },

  async request(path, options = {}) {
    const resp = await fetch(this.base + path, {
      ...options,
      credentials: "include",
      headers: { ...this.authHeaders(), ...(options.headers || {}) },
    });
    if (resp.status === 401 && !options.skipAuthRedirect) {
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

  getChallenge(slug) {
    return this.request("/challenges/" + encodeURIComponent(slug), { skipAuthRedirect: true });
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

  runTests(id, commandId = "run_tests") {
    return this.request("/sessions/" + id + "/tests", {
      method: "POST",
      body: JSON.stringify({ command_id: commandId }),
    });
  },

  chat(id, message, attached_paths = [], opts = {}) {
    return this.request("/sessions/" + id + "/ai/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        attached_paths,
        include_test_output: !!opts.include_test_output,
        selected_text: opts.selected_text || null,
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
    const refresh = this._get("refresh_token");
    try {
      if (refresh) {
        await fetch(this.authBase + "/logout", {
          method: "POST",
          credentials: "include",
          headers: this.authHeaders(),
          body: JSON.stringify({ refresh_token: refresh }),
        });
      }
    } finally {
      this.clearAccessAuth();
    }
  },
};

window.InterviewAPI = InterviewAPI;
