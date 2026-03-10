const API_BASE = window.location.origin + '/api';

const PromptCodeAPI = {
    _refreshPromise: null,

    _getAuthValue(key) {
        const sessionValue = sessionStorage.getItem(key);
        if (sessionValue !== null) return sessionValue;

        const legacyValue = localStorage.getItem(key);
        if (legacyValue === null) return null;

        sessionStorage.setItem(key, legacyValue);
        localStorage.removeItem(key);
        return legacyValue;
    },

    _setAuthValue(key, value) {
        sessionStorage.setItem(key, value);
        localStorage.removeItem(key);
    },

    _removeAuthValue(key) {
        sessionStorage.removeItem(key);
        localStorage.removeItem(key);
    },

    getToken() {
        return this._getAuthValue('pc_token');
    },

    setAuth(token, user, refreshToken) {
        this._setAuthValue('pc_token', token);
        this._setAuthValue('pc_user', JSON.stringify(user));
        if (refreshToken) {
            this._setAuthValue('pc_refresh_token', refreshToken);
        } else {
            this._removeAuthValue('pc_refresh_token');
        }
    },

    getRefreshToken() {
        return this._getAuthValue('pc_refresh_token');
    },

    getUser() {
        const raw = this._getAuthValue('pc_user');
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch (_) {
            this.clearAuth();
            return null;
        }
    },

    clearAuth() {
        this._removeAuthValue('pc_token');
        this._removeAuthValue('pc_refresh_token');
        this._removeAuthValue('pc_user');
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    debugLog(...args) {
        const host = window.location.hostname;
        if (host === 'localhost' || host === '127.0.0.1') {
            console.debug(...args);
        }
    },

    getInitials() {
        const user = this.getUser();
        if (!user) return '??';
        const f = (user.first_name || '')[0] || '';
        const l = (user.last_name || '')[0] || '';
        return (f + l).toLowerCase() || user.username.substring(0, 2);
    },

    async _tryRefresh() {
        if (this._refreshPromise) return this._refreshPromise;
        const rt = this.getRefreshToken();
        if (!rt) return false;
        this._refreshPromise = (async () => {
            try {
                const resp = await fetch(API_BASE + '/auth/refresh', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: rt }),
                });
                if (!resp.ok) return false;
                const data = await resp.json();
                this.setAuth(data.access_token, data.user, data.refresh_token);
                return true;
            } catch (_) {
                return false;
            } finally {
                this._refreshPromise = null;
            }
        })();
        return this._refreshPromise;
    },

    async _fetch(path, options = {}, _isRetry = false) {
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const resp = await fetch(API_BASE + path, { ...options, headers });
        if (resp.status === 401) {
            if (!_isRetry && await this._tryRefresh()) {
                return this._fetch(path, options, true);
            }
            this.clearAuth();
            if (!window.location.pathname.includes('login') && !window.location.pathname.includes('signup')) {
                window.location.href = '/login.html';
            }
            throw new Error('Unauthorized');
        }
        return resp;
    },

    async _readError(resp, fallback = 'Request failed') {
        try {
            const payload = await resp.json();
            const detail = payload?.detail;
            if (typeof detail === 'string' && detail.trim()) return detail;
            if (Array.isArray(detail) && detail.length) {
                return detail.map((d) => d.msg || d.message || JSON.stringify(d)).join('; ');
            }
            if (payload?.message) return String(payload.message);
        } catch (_) {}
        try {
            const text = await resp.text();
            if (text && text.trim()) return text.trim().slice(0, 300);
        } catch (_) {}
        return fallback;
    },

    async signup(data) {
        const resp = await this._fetch('/auth/signup', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            throw new Error(await this._readError(resp, 'Signup failed'));
        }
        const result = await resp.json();
        this.setAuth(result.access_token, result.user, result.refresh_token);
        return result;
    },

    async login(email, password) {
        const resp = await this._fetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
        if (!resp.ok) {
            throw new Error(await this._readError(resp, 'Login failed'));
        }
        const result = await resp.json();
        this.setAuth(result.access_token, result.user, result.refresh_token);
        return result;
    },

    async getMe() {
        const resp = await this._fetch('/auth/me');
        if (!resp.ok) throw new Error('Failed to fetch profile');
        return resp.json();
    },

    async updateMe(data) {
        const resp = await this._fetch('/auth/me', {
            method: 'PUT',
            body: JSON.stringify(data),
        });
        if (!resp.ok) throw new Error('Failed to update profile');
        const user = await resp.json();
        this._setAuthValue('pc_user', JSON.stringify(user));
        return user;
    },

    async getChallenges() {
        const resp = await this._fetch('/challenges/');
        if (!resp.ok) throw new Error('Failed to fetch challenges');
        return resp.json();
    },

    async getChallenge(id) {
        const resp = await this._fetch(`/challenges/${id}`);
        if (!resp.ok) throw new Error('Failed to fetch challenge');
        return resp.json();
    },

    async submitSolution(challengeId, code, entrypoint = 'main.py') {
        const resp = await this._fetch('/submissions/', {
            method: 'POST',
            body: JSON.stringify({ challenge_id: challengeId, code, entrypoint }),
        });
        if (!resp.ok) {
            throw new Error(await this._readError(resp, 'Submission failed'));
        }
        return resp.json();
    },

    async getSubmission(id) {
        const resp = await this._fetch(`/submissions/${id}`);
        if (!resp.ok) throw new Error('Failed to fetch submission');
        return resp.json();
    },

    async getSubmissionReport(id) {
        const resp = await this._fetch(`/submissions/${id}/report`);
        if (!resp.ok) throw new Error('Report not ready');
        return resp.json();
    },

    async getMySubmissions(challengeId) {
        let path = '/submissions/';
        if (challengeId) path += `?challenge_id=${challengeId}`;
        const resp = await this._fetch(path);
        if (!resp.ok) throw new Error('Failed to fetch submissions');
        return resp.json();
    },

    async getLeaderboard(challengeId, limit = 50) {
        const resp = await this._fetch(`/leaderboard/${challengeId}?limit=${limit}`);
        if (!resp.ok) throw new Error('Failed to fetch leaderboard');
        return resp.json();
    },

    async chatWithAssistant(challengeId, messages, code = '') {
        const resp = await this._fetch('/chat/', {
            method: 'POST',
            body: JSON.stringify({ challenge_id: challengeId, messages, code }),
        });
        if (!resp.ok) {
            throw new Error(await this._readError(resp, 'Chat failed'));
        }
        return resp.json();
    },

    async runPlayground(system, messages, options = {}) {
        const resp = await this._fetch('/chat/playground-run', {
            method: 'POST',
            body: JSON.stringify({
                system: system || '',
                messages: messages || [],
                model: options.model,
                temperature: options.temperature ?? 0,
                max_tokens: options.max_tokens ?? 1000,
            }),
        });
        if (!resp.ok) {
            throw new Error(await this._readError(resp, 'Playground run failed'));
        }
        return resp.json();
    },

    async getSubmissionStatus(id) {
        const resp = await this._fetch(`/submissions/${id}/status`);
        if (!resp.ok) throw new Error('Failed to fetch status');
        return resp.json();
    },

    async getUserProfile(username) {
        const resp = await this._fetch(`/users/${username}`);
        if (!resp.ok) throw new Error('Failed to fetch user profile');
        return resp.json();
    },

    async logout() {
        const rt = this.getRefreshToken();
        const token = this.getToken();
        if (rt && token) {
            try {
                await Promise.race([
                    fetch(API_BASE + '/auth/logout', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`,
                        },
                        body: JSON.stringify({ refresh_token: rt }),
                    }),
                    new Promise(resolve => setTimeout(resolve, 3000)),
                ]);
            } catch (_) {
                // best-effort: local logout always proceeds
            }
        }
        this.clearAuth();
        window.location.href = '/index.html';
    },

    updateNavAuth() {
        const loggedIn = this.isLoggedIn();
        const user = this.getUser();

        document.querySelectorAll('[data-auth-show]').forEach(el => {
            if (loggedIn) {
                el.removeAttribute('hidden');
                if (el._pcDisplay) el.style.display = el._pcDisplay;
            } else {
                if (!el._pcDisplay) el._pcDisplay = getComputedStyle(el).display || '';
                el.style.display = 'none';
            }
        });
        document.querySelectorAll('[data-noauth-show]').forEach(el => {
            if (!loggedIn) {
                el.removeAttribute('hidden');
                if (el._pcDisplay) el.style.display = el._pcDisplay;
            } else {
                if (!el._pcDisplay) el._pcDisplay = getComputedStyle(el).display || '';
                el.style.display = 'none';
            }
        });
        document.querySelectorAll('[data-user-initials]').forEach(el => {
            el.textContent = this.getInitials();
        });
        document.querySelectorAll('[data-user-name]').forEach(el => {
            el.textContent = loggedIn ? user.username : '';
        });

        // Logged-in users: logo goes to challenges (the "home" for authenticated users)
        // Logged-out users: logo goes to landing page
        document.querySelectorAll('.nav-logo').forEach(el => {
            el.href = loggedIn ? '/challenges.html' : '/index.html';
        });
    },

    redirectIfLoggedIn(dest = '/challenges.html') {
        if (this.isLoggedIn()) {
            window.location.href = dest;
            return true;
        }
        return false;
    },

    redirectIfLoggedOut(dest = '/login.html') {
        if (!this.isLoggedIn()) {
            window.location.href = dest;
            return true;
        }
        return false;
    },
};

document.addEventListener('DOMContentLoaded', () => {
    PromptCodeAPI.updateNavAuth();

    // Auto-redirect: logged-in users shouldn't see login/signup/landing
    const path = window.location.pathname;
    if (PromptCodeAPI.isLoggedIn()) {
        if (path === '/' || path === '/index.html' || path === '/login.html' || path === '/signup.html') {
            window.location.href = '/challenges.html';
            return;
        }
    }
});
