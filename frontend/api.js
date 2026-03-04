const API_BASE = window.location.origin + '/api';

const PromptCodeAPI = {
    getToken() {
        return localStorage.getItem('pc_token');
    },

    setAuth(token, user) {
        localStorage.setItem('pc_token', token);
        localStorage.setItem('pc_user', JSON.stringify(user));
    },

    getUser() {
        const raw = localStorage.getItem('pc_user');
        return raw ? JSON.parse(raw) : null;
    },

    clearAuth() {
        localStorage.removeItem('pc_token');
        localStorage.removeItem('pc_user');
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    getInitials() {
        const user = this.getUser();
        if (!user) return '??';
        const f = (user.first_name || '')[0] || '';
        const l = (user.last_name || '')[0] || '';
        return (f + l).toLowerCase() || user.username.substring(0, 2);
    },

    async _fetch(path, options = {}) {
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const resp = await fetch(API_BASE + path, { ...options, headers });
        if (resp.status === 401) {
            this.clearAuth();
            if (!window.location.pathname.includes('login') && !window.location.pathname.includes('signup')) {
                window.location.href = '/login.html';
            }
            throw new Error('Unauthorized');
        }
        return resp;
    },

    async signup(data) {
        const resp = await this._fetch('/auth/signup', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Signup failed');
        }
        const result = await resp.json();
        this.setAuth(result.access_token, result.user);
        return result;
    },

    async login(email, password) {
        const resp = await this._fetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Login failed');
        }
        const result = await resp.json();
        this.setAuth(result.access_token, result.user);
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
        localStorage.setItem('pc_user', JSON.stringify(user));
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
            const err = await resp.json();
            const detail = err.detail;
            const msg = typeof detail === 'string' ? detail : (Array.isArray(detail) ? detail.map(d => d.msg || d.message || JSON.stringify(d)).join('; ') : 'Submission failed');
            throw new Error(msg);
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
            const err = await resp.json();
            const detail = err.detail;
            const msg = typeof detail === 'string' ? detail : (Array.isArray(detail) ? detail.map(d => d.msg || d.message || JSON.stringify(d)).join('; ') : 'Chat failed');
            throw new Error(msg);
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
            const err = await resp.json();
            const detail = err.detail;
            const msg = typeof detail === 'string' ? detail : 'Playground run failed';
            throw new Error(msg);
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

    logout() {
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
