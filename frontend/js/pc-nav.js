/* Keep the app navigation mounted while lightweight practice pages change. */
(function (global) {
  const controllers = {
    dashboard: "interview-dashboard.js", challenges: "interview-challenges.js",
    progress: "interview-progress.js", brief: "interview-challenge.js",
  };
  const pages = new Map();
  const warmed = new Map();
  const cachePrefix = "pc_nav_v20261008a:";
  let epoch = 0;
  function route(url) {
    if (url.origin !== location.origin) return null;
    const path = url.pathname.replace(/\/$/, "");
    if (path === "/dashboard") return "dashboard";
    if (path === "/challenges") return "challenges";
    if (path === "/progress") return "progress";
    return /^\/challenges\/[^/]+$/.test(path) ? "brief" : null;
  }
  function page(url) {
    const key = url.pathname + url.search;
    const cached = pages.get(key);
    if (cached && Date.now() - cached.at < 300000) return cached.promise;
    let at = Date.now();
    const promise = (async () => {
      let html, stored = false;
      try {
        const saved = JSON.parse(sessionStorage.getItem(cachePrefix + key) || "null");
        if (saved && Date.now() - saved.at >= 0 && Date.now() - saved.at < 300000 && typeof saved.html === "string") {
          html = saved.html;
          at = saved.at;
          stored = true;
        }
      } catch (_) {}
      if (!html) {
        const resp = await fetch(key, { credentials: "same-origin" });
        if (!resp.ok) throw new Error("Could not load page");
        html = await resp.text();
      }
      const parsed = new DOMParser().parseFromString(html, "text/html");
      const main = parsed.getElementById("main");
      const expected = "/static/js/pages/" + controllers[route(url)];
      const script = [...parsed.querySelectorAll("script[src]")].find((s) => new URL(s.src, url).pathname === expected);
      if (!main || !script) throw new Error("Unsupported page");
      // Persist only fetched public templates, never the rendered account view.
      try {
        if (!stored) {
          const cacheKey = cachePrefix + key;
          if (!sessionStorage.getItem(cacheKey)) {
            const keys = [];
            for (let i = 0; i < sessionStorage.length; i++) {
              const item = sessionStorage.key(i);
              if (item?.startsWith(cachePrefix)) keys.push(item);
            }
            if (keys.length >= 20) sessionStorage.removeItem(keys[0]);
          }
          sessionStorage.setItem(cacheKey, JSON.stringify({ html, at: Date.now() }));
        }
      } catch (_) {}
      return { main, script: new URL(script.getAttribute("src"), url).href, title: parsed.title };
    })();
    pages.set(key, { at, promise });
    if (pages.size > 20) pages.delete(pages.keys().next().value);
    promise.catch(() => {
      if (pages.get(key)?.promise === promise) pages.delete(key);
      try { sessionStorage.removeItem(cachePrefix + key); } catch (_) {}
    });
    return promise;
  }
  async function go(href, pop = false) {
    const url = new URL(href, location.href);
    if (!route(url)) { location.assign(url.href); return; }
    const current = ++epoch;
    const previous = document.getElementById("main");
    previous?.setAttribute("aria-busy", "true");
    try {
      const data = await page(url);
      if (current !== epoch) return;
      if (!pop) {
        history.replaceState({ ...history.state, pcScroll: [scrollX, scrollY] }, "");
        history.pushState({}, "", url.pathname + url.search + url.hash);
      }
      const main = data.main.cloneNode(true);
      main.dataset.pcNav = String(current);
      previous.replaceWith(main);
      document.title = data.title;
      const active = route(url) === "brief" ? "challenges" : route(url) === "dashboard" ? "practice" : route(url);
      document.querySelectorAll("[data-nav]").forEach((link) => {
        const on = link.dataset.nav === active;
        link.classList.toggle("is-active", on);
        if (on) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
      const script = document.createElement("script");
      script.src = data.script;
      script.dataset.pcNav = String(current);
      await new Promise((resolve, reject) => {
        script.onload = resolve; script.onerror = reject;
        document.body.appendChild(script);
      });
      script.remove();
      if (current !== epoch) return;
      main.setAttribute("tabindex", "-1");
      main.focus({ preventScroll: true });
      const saved = pop && history.state?.pcScroll;
      if (url.hash) document.getElementById(url.hash.slice(1))?.scrollIntoView();
      else scrollTo(...(saved || [0, 0]));
    } catch (_) {
      if (current === epoch) location.assign(url.href);
    }
  }
  function linkFor(event) {
    const link = event.target.closest?.("a[href]");
    if (!link || link.hasAttribute("download") || (link.target && link.target !== "_self")) return null;
    const url = new URL(link.href, location.href);
    if (!route(url) || (url.pathname === location.pathname && url.search === location.search && url.hash)) return null;
    return url;
  }
  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = linkFor(event);
    if (!url) return;
    event.preventDefault();
    go(url.href);
  });
  const prefetch = (event) => {
    if (navigator.connection?.saveData || /(^|-)2g$/.test(navigator.connection?.effectiveType || "")) return;
    const url = linkFor(event);
    if (!url) return;
    page(url).catch(() => {});
    if (typeof InterviewAPI === "undefined" || !InterviewAPI.isLoggedIn()) return;
    const kind = route(url);
    const paths = kind === "brief"
      ? [url.pathname.replace(/\/$/, ""), "/challenges/progress"]
      : [kind === "challenges" ? "/challenges/progress" : "/dashboard"];
    for (const path of paths) {
      let key;
      try {
        key = (sessionStorage.getItem("pc_user") || "") + ":" +
          (sessionStorage.getItem("pc_read_generation") || "0") + ":" + path;
      } catch (_) { return; }
      if (Date.now() - warmed.get(key) < 300000) continue;
      warmed.set(key, Date.now());
      if (warmed.size > 20) warmed.delete(warmed.keys().next().value);
      InterviewAPI.readCached(path, undefined, {
        skipAuthRedirect: kind === "brief" && path !== "/challenges/progress",
      }).catch(() => warmed.delete(key));
    }
  };
  document.addEventListener("pointerover", prefetch);
  document.addEventListener("focusin", prefetch);
  global.addEventListener("popstate", () => go(location.href, true));
  global.PCNav = { go };
})(window);
