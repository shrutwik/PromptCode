/**
 * Shared PromptCode UI — toasts, command palette, panel prefs, icons
 * API used by interview-session / report / dashboard.
 */
(function (global) {
  const reduced = () =>
    global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const ICONS = {
    play: '<svg class="pc-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 3.5v9l9-4.5z"/></svg>',
    check: '<svg class="pc-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7"/></svg>',
    x: '<svg class="pc-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4L4 12"/></svg>',
    search: '<svg class="pc-icon" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L13.5 13.5"/></svg>',
  };

  function icon(name) {
    return ICONS[name] || "";
  }

  function ensureToastHost() {
    let host = document.querySelector(".pc-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.className = "pc-toast-host";
      host.setAttribute("aria-live", "polite");
      document.body.appendChild(host);
    }
    return host;
  }

  /** toast(message, { tone, timeout }) or toast(message, toneString) */
  function toast(message, opts = {}) {
    if (typeof opts === "string") opts = { tone: opts };
    const tone = opts.tone || opts.kind || "info";
    const ms = opts.timeout ?? opts.ms ?? 3200;
    const host = ensureToastHost();
    const el = document.createElement("div");
    el.className = "pc-toast";
    el.dataset.tone = tone;
    el.dataset.kind = tone;
    el.setAttribute("role", tone === "danger" ? "alert" : "status");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(() => {
      el.classList.add("is-leaving");
      const done = () => el.remove();
      el.addEventListener("animationend", done, { once: true });
      setTimeout(done, 400);
    }, ms);
  }

  function fuzzy(query, text) {
    const q = (query || "").toLowerCase().trim();
    const t = (text || "").toLowerCase();
    if (!q) return true;
    let i = 0;
    for (const ch of t) {
      if (ch === q[i]) i += 1;
      if (i === q.length) return true;
    }
    return t.includes(q);
  }

  function createCommandPalette(commands) {
    let open = false;
    let backdrop = null;

    function close() {
      if (!backdrop) return;
      backdrop.remove();
      backdrop = null;
      open = false;
      global.removeEventListener("keydown", onDocKey);
    }

    function onDocKey(e) {
      if (e.key === "Escape") close();
    }

    function show() {
      if (open) return;
      open = true;
      const prev = document.activeElement;
      backdrop = document.createElement("div");
      backdrop.className = "pc-palette";
      backdrop.innerHTML =
        '<div class="pc-palette-panel" role="dialog" aria-label="Command palette">' +
        '<input class="pc-palette-input" type="text" placeholder="Type a command…" aria-label="Filter commands" />' +
        '<div class="pc-palette-list" role="listbox"></div></div>';
      document.body.appendChild(backdrop);
      const box = backdrop.querySelector(".pc-palette-panel");
      const input = backdrop.querySelector("input");
      const list = backdrop.querySelector(".pc-palette-list");
      let selected = 0;
      let filtered = commands.slice();

      const render = () => {
        let html = "";
        let lastGroup = null;
        filtered.forEach((c, i) => {
          if (c.group && c.group !== lastGroup) {
            lastGroup = c.group;
            html += `<div class="pc-palette-group">${c.group}</div>`;
          }
          html += `<button type="button" class="pc-palette-item" role="option" aria-selected="${i === selected}" data-i="${i}"><span>${c.label}</span>${c.shortcut ? `<kbd class="pc-kbd">${c.shortcut}</kbd>` : ""}</button>`;
        });
        list.innerHTML = html;
        list.querySelectorAll("[data-i]").forEach((btn) => {
          btn.addEventListener("click", () => run(Number(btn.dataset.i)));
        });
      };

      const run = (i) => {
        const cmd = filtered[i];
        close();
        if (prev && prev.focus) prev.focus();
        cmd?.run?.();
      };

      input.addEventListener("input", () => {
        filtered = commands.filter((c) =>
          fuzzy(input.value, c.label + " " + (c.keywords || "") + " " + (c.group || ""))
        );
        selected = 0;
        render();
      });
      input.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          selected = Math.min(filtered.length - 1, selected + 1);
          render();
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          selected = Math.max(0, selected - 1);
          render();
        } else if (e.key === "Enter") {
          e.preventDefault();
          run(selected);
        }
      });
      backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop) {
          close();
          if (prev && prev.focus) prev.focus();
        }
      });
      global.addEventListener("keydown", onDocKey);
      render();
      input.focus();
    }

    global.addEventListener("keydown", (e) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (open) close();
        else show();
      }
    });

    return { open: show, close };
  }

  function loadPanelSizes(key, defaults) {
    try {
      return { ...defaults, ...JSON.parse(localStorage.getItem(key) || "{}") };
    } catch {
      return { ...defaults };
    }
  }

  function savePanelSizes(key, sizes) {
    localStorage.setItem(key, JSON.stringify(sizes));
  }

  function enhanceCards() {}

  function readStore(key) {
    try {
      return sessionStorage.getItem(key) ?? localStorage.getItem(key);
    } catch (_) {
      return null;
    }
  }

  function isAuthed() {
    return !!(readStore("access_token") || readStore("pc_token"));
  }

  function currentUser() {
    try {
      return JSON.parse(readStore("pc_user") || "null") || {};
    } catch (_) {
      return {};
    }
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function initials(user) {
    const a = (user.first_name || "").trim();
    const b = (user.last_name || "").trim();
    if (a || b) return ((a[0] || "") + (b[0] || "")).toUpperCase() || "?";
    return ((user.username || user.email || "?").trim()[0] || "?").toUpperCase();
  }

  async function logout() {
    try {
      if (global.InterviewAPI && InterviewAPI.logout) await InterviewAPI.logout();
      else if (global.PromptCodeAPI && PromptCodeAPI.logout) await PromptCodeAPI.logout();
    } catch (_) {}
    ["access_token", "pc_token", "pc_user", "refresh_token", "pc_refresh_token", "pc_session_token"].forEach((k) => {
      try { sessionStorage.removeItem(k); localStorage.removeItem(k); } catch (_) {}
    });
    location.href = "/";
  }

  /** Accessible dropdown: toggle, outside click, Esc, arrow keys. */
  function bindMenu(btn, menu) {
    const items = () => Array.from(menu.querySelectorAll("a, button"));
    const setOpen = (open, focusFirst) => {
      menu.classList.toggle("hidden", !open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open && focusFirst) items()[0]?.focus();
    };
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      setOpen(menu.classList.contains("hidden"), e.detail === 0);
    });
    btn.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true, true); }
    });
    menu.addEventListener("keydown", (e) => {
      const list = items();
      const i = list.indexOf(document.activeElement);
      if (e.key === "Escape") { setOpen(false); btn.focus(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); list[(i + 1) % list.length]?.focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); list[(i - 1 + list.length) % list.length]?.focus(); }
    });
    menu.addEventListener("click", (e) => e.stopPropagation());
    document.addEventListener("click", () => setOpen(false));
  }

  function accountMenuHtml(id, extraItems) {
    const user = currentUser();
    const name = user.first_name ? `${user.first_name} ${user.last_name || ""}`.trim() : user.username || "Account";
    return `
      <div class="nav-account">
        <button type="button" class="nav-account-btn" aria-haspopup="menu" aria-expanded="false" aria-controls="${id}Menu" id="${id}Btn" aria-label="Account menu">
          <span class="pc-avatar" aria-hidden="true">${esc(initials(user))}</span><span class="nav-account-name">${esc(name)}</span>
          <svg class="pc-icon pc-icon-sm" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>
        </button>
        <div class="nav-account-menu hidden" id="${id}Menu" role="menu">
          ${user.email ? `<div class="pc-menu-head"><strong>${esc(name)}</strong><span>${esc(user.email)}</span></div>` : ""}
          ${extraItems || ""}
          <a href="/settings" role="menuitem">Settings</a>
          <a href="/settings#feedback" role="menuitem">Feedback</a>
          <div class="pc-menu-sep" role="separator"></div>
          <button type="button" role="menuitem" data-pc-logout>Log out</button>
        </div>
      </div>`;
  }

  function wireAccount(root, id) {
    const btn = root.querySelector("#" + id + "Btn");
    const menu = root.querySelector("#" + id + "Menu");
    if (btn && menu) bindMenu(btn, menu);
    root.querySelectorAll("[data-pc-logout]").forEach((b) => b.addEventListener("click", logout));
  }

  const PUBLIC_LINKS = [
    { href: "/dashboard", label: "Practice", match: (p) => p === "/dashboard" },
    { href: "/challenges", label: "Challenges", match: (p) => p === "/challenges" || p.startsWith("/challenges/") },
    { href: "/progress", label: "Progress", match: (p) => p === "/progress" },
  ];

  /** Public header: <header class="pc-header" data-pc-header></header> */
  function wordmarkHtml() {
    return `<span class="pc-wordmark">` +
      `<svg class="pc-mark" viewBox="0 0 24 24" fill="none" aria-hidden="true">` +
      `<rect x="2" y="2" width="20" height="20" rx="5.5" stroke="currentColor" stroke-width="1.4"/>` +
      `<path d="M8.2 8.1l5.1 3.9-5.1 3.9" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round"/>` +
      `<path d="M13.6 16.2h3.1" stroke="currentColor" stroke-width="1.55" stroke-linecap="round"/>` +
      `</svg>` +
      `<span class="pc-wordmark-text">Prompt<em>Code</em></span>` +
      `</span>`;
  }

  function ensureBrandFont() {
    if (document.getElementById("pc-brand-font")) return;
    const link = document.createElement("link");
    link.id = "pc-brand-font";
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,500;0,600;1,500&display=swap";
    document.head.appendChild(link);
  }

  function enhanceWordmarks(root) {
    ensureBrandFont();
    (root || document).querySelectorAll(".pc-logo, .nav-brand").forEach((el) => {
      if (el.dataset.wordmark === "1") return;
      el.dataset.wordmark = "1";
      el.innerHTML = wordmarkHtml();
    });
  }

  /** Public header: <header class="pc-header" data-pc-header></header> */
  function mountPublicHeader() {
    const host = document.querySelector("[data-pc-header]");
    if (!host || host.dataset.mounted) return;
    host.dataset.mounted = "1";
    host.classList.add("pc-header");
    const path = location.pathname;
    const authed = isAuthed();
    const links = authed
      ? PUBLIC_LINKS.map(
          (l) => `<a href="${l.href}"${l.match && l.match(path) ? ' class="is-active" aria-current="page"' : ""}>${l.label}</a>`
        ).join("")
      : "";
    const onAuthPage = path === "/login.html" || path === "/signup.html";
    let actions;
    if (authed) {
      actions = `<a class="btn btn-primary btn-sm" href="/dashboard">Open app</a>` +
        accountMenuHtml("pcHdrAccount", '<a href="/dashboard" role="menuitem">Practice</a><a href="/profile.html" role="menuitem">Prompt profile</a>');
    } else if (onAuthPage) {
      actions = path === "/login.html"
        ? `<span class="muted pc-hide-sm" style="font-size:var(--pc-text-sm)">New here?</span><a class="btn btn-secondary btn-sm" href="/signup.html">Create account</a>`
        : `<span class="muted pc-hide-sm" style="font-size:var(--pc-text-sm)">Have an account?</span><a class="btn btn-secondary btn-sm" href="/login.html">Sign in</a>`;
    } else {
      actions = `<a class="btn btn-ghost btn-sm" href="/login.html">Sign in</a><a class="btn btn-primary btn-sm" href="/signup.html">Get started</a>`;
    }
    host.innerHTML = `
      <div class="pc-header-inner">
        <a class="pc-logo" href="/" aria-label="PromptCode home">PromptCode</a>
        <nav class="pc-header-links" id="pcHeaderLinks" aria-label="Primary"${links ? "" : " hidden"}>${links}</nav>
        <div class="pc-header-actions">
          ${actions}
          ${links ? `<button type="button" class="btn btn-quiet btn-sm btn-icon pc-header-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="pcHeaderLinks">
            <svg class="pc-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11"/></svg>
          </button>` : ""}
        </div>
      </div>`;
    const toggle = host.querySelector(".pc-header-toggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        const open = host.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      });
      host.querySelectorAll(".pc-header-links a").forEach((a) =>
        a.addEventListener("click", () => {
          host.classList.remove("is-open");
          toggle.setAttribute("aria-expanded", "false");
        })
      );
    }
    if (authed) wireAccount(host, "pcHdrAccount");
    enhanceWordmarks(host);
  }

  /** Public footer: <footer class="pc-footer" data-pc-footer></footer> */
  function mountPublicFooter() {
    const host = document.querySelector("[data-pc-footer]");
    if (!host || host.dataset.mounted) return;
    host.dataset.mounted = "1";
    host.classList.add("pc-footer");
    const product = isAuthed()
      ? `<a href="/dashboard">Practice</a>
          <a href="/challenges">Challenges</a>
          <a href="/challenges.html">Prompt challenges</a>
          <a href="/leaderboard.html">Leaderboard</a>`
      : "";
    host.innerHTML = `
      <div class="pc-footer-inner">
        <a class="pc-logo" href="/">PromptCode</a>
        <nav aria-label="Footer">
          ${product}
          <a href="/privacy">Privacy</a>
        </nav>
        <span>© ${new Date().getFullYear()} PromptCode · Open beta</span>
      </div>`;
    enhanceWordmarks(host);
  }

  /** Sliding underline for .pc-tabs; follows [aria-selected=true] / .is-active. */
  function tabs(container) {
    if (!container || container.dataset.pcTabs) return;
    container.dataset.pcTabs = "1";
    container.classList.add("pc-tabs");
    const ind = document.createElement("span");
    ind.className = "pc-tabs-ind";
    ind.setAttribute("aria-hidden", "true");
    container.appendChild(ind);
    const place = () => {
      const active = container.querySelector('[aria-selected="true"], .is-active');
      if (!active) { ind.style.setProperty("--w", "0px"); return; }
      ind.style.setProperty("--x", active.offsetLeft + "px");
      ind.style.setProperty("--w", active.offsetWidth + "px");
    };
    new MutationObserver(place).observe(container, { subtree: true, attributes: true, attributeFilter: ["class", "aria-selected"] });
    global.addEventListener("resize", place);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(place);
    place();
  }

  /** Markup helpers so pages share loading/empty/bar markup. */
  function skeletonRows(n = 5) {
    return Array.from({ length: n }, () => '<div class="pc-skeleton pc-skeleton-row"></div>').join("");
  }
  function emptyState(title, body, actionHtml) {
    return `<div class="pc-empty"><h3>${esc(title)}</h3>${body ? `<p>${esc(body)}</p>` : ""}${actionHtml || ""}</div>`;
  }
  function bar(pct, tone, delayMs) {
    const v = Math.max(0, Math.min(100, Number(pct) || 0));
    return `<div class="pc-bar"${tone ? ` data-tone="${tone}"` : ""} role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(v)}"><div class="pc-bar-fill" style="--v:${v}%;--d:${delayMs || 0}ms"></div></div>`;
  }

  /**
   * App shell nav: Practice · Challenges · Progress + account menu.
   * Practice starts and resumes sessions. Progress is the scores from finished ones.
   * Markup: <nav class="nav" aria-label="App"><a class="nav-brand" href="/dashboard">PromptCode</a></nav>
   * Skipped on .ide-body (workspace has its own session top bar).
   */
  function mountAppNav(opts = {}) {
    if (document.body.classList.contains("ide-body")) return;
    const nav = document.querySelector("nav.nav");
    if (!nav) return;
    if (nav.dataset.mounted && !opts.active) return;
    nav.dataset.mounted = "1";
    if (!nav.getAttribute("aria-label")) nav.setAttribute("aria-label", "App");

    let links = nav.querySelector(".nav-links");
    if (!links) {
      links = document.createElement("div");
      links.className = "nav-links";
      nav.appendChild(links);
    }
    const primary = [
      { key: "practice", href: "/dashboard", label: "Practice" },
      { key: "challenges", href: "/challenges", label: "Challenges" },
      { key: "progress", href: "/progress", label: "Progress" },
    ];
    links.innerHTML =
      primary.map((i) => `<a href="${i.href}" class="nav-link" data-nav="${i.key}">${i.label}</a>`).join("") +
      accountMenuHtml("pcAccount");

    const path = location.pathname;
    const onDash = path === "/dashboard" || path.endsWith("/dashboard");
    const onReport = /\/session\/[^/]+\/report\/?$/.test(path);
    const onProgress = path === "/progress" || path.endsWith("/progress");
    const key =
      opts.active ||
      (onProgress ? "progress" : onDash || onReport ? "practice" : path.startsWith("/challenges") ? "challenges" : "");
    links.querySelectorAll("[data-nav]").forEach((a) => {
      const on = a.dataset.nav === key;
      a.classList.toggle("is-active", on);
      if (on) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    wireAccount(links, "pcAccount");
    enhanceWordmarks(nav);
  }

  global.PCUI = {
    icon,
    toast,
    createCommandPalette,
    openCommandPalette: (cmds) => createCommandPalette(cmds).open(),
    bindPaletteHotkey: (cmds) => createCommandPalette(typeof cmds === "function" ? cmds() : cmds),
    loadPanelSizes,
    savePanelSizes,
    enhanceCards,
    mountAppNav,
    mountPublicHeader,
    mountPublicFooter,
    tabs,
    skeletonRows,
    emptyState,
    bar,
    esc,
    isAuthed,
    currentUser,
    logout,
    reducedMotion: reduced,
    prefersReducedMotion: reduced,
  };

  function autoMount() {
    mountPublicHeader();
    mountPublicFooter();
    if (document.querySelector("nav.nav") && !document.body.classList.contains("ide-body")) mountAppNav();
    document.querySelectorAll("[data-pc-tabs]").forEach(tabs);
    enhanceWordmarks();
  }
  document.addEventListener("click", (e) => {
    if (e.target instanceof Element && e.target.closest("[data-pc-reload]")) location.reload();
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", autoMount);
  else autoMount();
})(window);

