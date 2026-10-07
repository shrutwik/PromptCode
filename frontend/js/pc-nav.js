/* Keep the app navigation mounted while lightweight practice pages change. */
(function (global) {
  const controllers = {
    dashboard: "interview-dashboard.js", challenges: "interview-challenges.js",
    progress: "interview-progress.js", brief: "interview-challenge.js",
  };
  const pages = new Map();
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
    const promise = fetch(key, { credentials: "same-origin" }).then(async (resp) => {
      if (!resp.ok) throw new Error("Could not load page");
      const parsed = new DOMParser().parseFromString(await resp.text(), "text/html");
      const main = parsed.getElementById("main");
      const expected = "/static/js/pages/" + controllers[route(url)];
      const script = [...parsed.querySelectorAll("script[src]")].find((s) => new URL(s.src, url).pathname === expected);
      if (!main || !script) throw new Error("Unsupported page");
      return { main, script: new URL(script.getAttribute("src"), url).href, title: parsed.title };
    });
    pages.set(key, { at: Date.now(), promise });
    if (pages.size > 20) pages.delete(pages.keys().next().value);
    promise.catch(() => { if (pages.get(key)?.promise === promise) pages.delete(key); });
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
    if (url) page(url).catch(() => {});
  };
  document.addEventListener("pointerover", prefetch);
  document.addEventListener("focusin", prefetch);
  global.addEventListener("popstate", () => go(location.href, true));
  global.PCNav = { go };
})(window);
