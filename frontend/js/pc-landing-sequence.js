/**
 * PromptCode landing sequence — scroll-scrubbed product story.
 *
 * Architecture (Option B — reliability first):
 *   Native window scroll + GSAP ScrollTrigger pin + scrubbed timeline.
 *   Lenis removed: smooth-wheel overshoot raced through the pin and desynced scrub.
 *
 * Every beat: outgoing line leaves first, then the next line arrives.
 * Scrub lag smooths the wheel without Lenis overshoot.
 */
(function () {
  const reduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const BEATS = [
    { id: "brand", label: "Brand" },
    { id: "value", label: "Value" },
    { id: "library", label: "Library" },
    { id: "workspace", label: "Workspace" },
    { id: "ai", label: "AI" },
    { id: "tests", label: "Tests" },
    { id: "report", label: "Report" },
    { id: "cta", label: "CTA" },
  ];

  /** Brand exits with scroll (no dead hold). Other beats keep HOLD+FADE. */
  const BRAND_EXIT = 0.8;
  const HOLD = 0.24;
  const FADE = 0.9;
  const BEAT = HOLD + FADE;
  /** Viewport-heights of scroll distance per beat while pinned. */
  const VH_PER_BEAT = 0.7;

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function $$(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function setBeat(beat) {
    const sticky = $(".pc-seq-sticky");
    if (sticky) sticky.dataset.beat = beat;
  }

  function showStatic() {
    document.documentElement.classList.add("pc-seq-reduced");
    document.querySelectorAll(".pc-seq-stage").forEach((s) => {
      s.style.opacity = "1";
      s.style.visibility = "visible";
    });
    const hint = $(".pc-seq-scrollhint");
    if (hint) hint.hidden = true;
    const ring = $(".pc-seq-ring");
    if (ring) {
      ring.style.setProperty("--score", "87");
      ring.textContent = "87";
    }
    $$(".pc-seq-dim-bar").forEach((b) => {
      b.style.setProperty("--fill", b.getAttribute("data-fill") || "80");
    });
    $$(".pc-seq-term-fail").forEach((el) => {
      el.style.opacity = "0.35";
    });
    $$(".pc-seq-term-pass").forEach((el) => {
      el.style.opacity = "1";
    });
  }

  function initSequence() {
    const sticky = $(".pc-seq-sticky");
    const stages = Array.from(document.querySelectorAll(".pc-seq-stage"));
    if (!sticky || stages.length < BEATS.length || !window.gsap || !window.ScrollTrigger) {
      showStatic();
      return;
    }

    const gsap = window.gsap;
    const ScrollTrigger = window.ScrollTrigger;
    gsap.registerPlugin(ScrollTrigger);

    gsap.set(stages, {
      autoAlpha: 0,
      scale: 1,
      y: 0,
      filter: "blur(0px)",
      transformOrigin: "50% 46%",
      force3D: true,
    });
    gsap.set(stages[0], { autoAlpha: 1 });
    stages[0].classList.add("is-live");
    setBeat(BEATS[0].id);

    const css = getComputedStyle(document.documentElement);
    const accent = (css.getPropertyValue("--pc-accent") || "#11110f").trim();
    const accentDim = (css.getPropertyValue("--pc-accent-dim") || "rgba(17,17,15,0.08)").trim();
    const muted = (css.getPropertyValue("--pc-muted") || "#6b6b65").trim();

    const ring = $(".pc-seq-ring");
    const focusRow = $(".pc-seq-table tr.is-focus");
    const hint = $(".pc-seq-scrollhint");
    const brandEyebrow = $('[data-beat="brand"] .pc-seq-eyebrow');
    const libNav = $$('[data-beat="library"] .pc-seq-appnav a');
    const libRows = $$(".pc-seq-table tbody tr");
    const libFilters = $$(".pc-seq-filter");
    const wsFiles = $$('[data-beat="workspace"] .pc-seq-ide .file');
    const wsCode = $$('[data-beat="workspace"] .pc-seq-ide .code > div:not(.dim)');
    const wsAi = $('[data-beat="workspace"] .pc-seq-ide .ai-col');
    const wsPhase = $$('[data-beat="workspace"] .pc-seq-phase button');
    const aiLines = $$('[data-beat="ai"] .pc-seq-panel-body > div');
    const applyBtn = $(".pc-seq-apply");
    const termFail = $$(".pc-seq-term-fail");
    const termPass = $$(".pc-seq-term-pass");
    const dimBars = $$(".pc-seq-dim-bar");
    const dimItems = $$(".pc-seq-dim");
    const ctaBtns = $$(".pc-seq-actions .btn");
    const ctaNav = $$('[data-beat="cta"] .pc-seq-appnav a');

    if (libRows.length) gsap.set(libRows, { opacity: 0.35, x: 0 });
    if (libFilters.length) gsap.set(libFilters, { opacity: 0.4, y: 6 });
    if (wsFiles.length) gsap.set(wsFiles, { opacity: 0.35, x: -6 });
    if (wsCode.length) gsap.set(wsCode, { opacity: 0, y: 8 });
    if (wsAi) gsap.set(wsAi, { opacity: 0.25, x: 12 });
    if (aiLines.length) gsap.set(aiLines, { opacity: 0, y: 10 });
    if (applyBtn) gsap.set(applyBtn, { scale: 0.92, boxShadow: "0 0 0 0 rgba(17,17,15,0)" });
    if (termFail.length) gsap.set(termFail, { opacity: 1 });
    if (termPass.length) gsap.set(termPass, { opacity: 0, y: 6 });
    if (dimBars.length) dimBars.forEach((bar) => bar.style.setProperty("--fill", "0"));
    if (dimItems.length) gsap.set(dimItems, { opacity: 0.25, x: 8 });
    if (ctaBtns.length) gsap.set(ctaBtns, { y: 16, opacity: 0.35 });

    const pinDistance = () => Math.round(window.innerHeight * VH_PER_BEAT * BEATS.length);
    const headerOffset = () => {
      const header = $(".pc-header");
      return header ? header.offsetHeight : 0;
    };

    const tl = gsap.timeline({
      defaults: { ease: "none" },
      scrollTrigger: {
        trigger: sticky,
        pin: true,
        scrub: 0.85,
        start: () => "top " + headerOffset() + "px",
        end: () => "+=" + pinDistance(),
        anticipatePin: 1,
        invalidateOnRefresh: true,
        onUpdate: (self) => {
          const time = self.progress * tl.duration();
          let idx = 0;
          for (let i = 0; i < BEATS.length; i++) {
            const at = tl.labels[BEATS[i].id];
            if (at != null && time + 1e-6 >= at) idx = i;
          }
          stages.forEach((s, i) => s.classList.toggle("is-live", i === idx));
          setBeat(BEATS[idx].id);
          if (hint) hint.style.opacity = String(Math.max(0, 1 - self.progress * 8));
        },
      },
    });

    /** Sequential dissolve: outgoing finishes, then incoming arrives sharp. */
    function scaleOut(fromIdx, toIdx, at, dur) {
      const d = dur == null ? FADE : dur;
      tl.to(
        stages[fromIdx],
        {
          autoAlpha: 0,
          y: -48,
          scale: 0.985,
          filter: "blur(5px)",
          duration: d * 0.46,
          ease: "power2.in",
        },
        at
      );
      tl.fromTo(
        stages[toIdx],
        { autoAlpha: 0, y: 48, scale: 1, filter: "blur(0px)" },
        {
          autoAlpha: 1,
          y: 0,
          scale: 1,
          filter: "blur(0px)",
          duration: d * 0.46,
          ease: "power2.out",
          immediateRender: false,
        },
        at + d * 0.54
      );
    }

    let t = 0;

    // —— Brand ——
    tl.addLabel("brand", t);
    if (brandEyebrow) {
      tl.to(brandEyebrow, { opacity: 0, y: -12, duration: BRAND_EXIT * 0.55, ease: "sine.inOut" }, t);
    }
    scaleOut(0, 1, t, BRAND_EXIT);
    t += BRAND_EXIT;

    // —— Value ——
    tl.addLabel("value", t);
    t += HOLD;
    scaleOut(1, 2, t);
    t += FADE;

    // —— Library ——
    tl.addLabel("library", t);
    if (libNav.length) {
      tl.to(libNav, { color: muted, duration: HOLD * 0.25 }, t);
      tl.to(libNav[1] || libNav[0], { color: accent, duration: HOLD * 0.3 }, t + HOLD * 0.15);
    }
    if (libFilters.length) {
      tl.to(libFilters, { opacity: 1, y: 0, duration: HOLD * 0.4, stagger: 0.05 }, t + HOLD * 0.05);
    }
    if (libRows.length) {
      tl.to(libRows, { opacity: 1, duration: HOLD * 0.4, stagger: 0.04 }, t + HOLD * 0.1);
    }
    if (focusRow) {
      tl.fromTo(
        focusRow,
        { backgroundColor: "rgba(17,17,15,0)", boxShadow: "inset 3px 0 0 transparent" },
        {
          backgroundColor: accentDim,
          boxShadow: "inset 3px 0 0 " + accent,
          duration: HOLD * 0.45,
        },
        t + HOLD * 0.25
      );
    }
    t += HOLD;
    scaleOut(2, 3, t);
    t += FADE;

    // —— Workspace ——
    tl.addLabel("workspace", t);
    if (wsPhase.length) {
      tl.to(wsPhase, { opacity: 0.45, duration: HOLD * 0.2 }, t);
      tl.to(wsPhase[1] || wsPhase[0], { opacity: 1, color: accent, duration: HOLD * 0.3 }, t + HOLD * 0.1);
    }
    if (wsFiles.length) {
      tl.to(wsFiles, { opacity: 1, x: 0, duration: HOLD * 0.35, stagger: 0.05 }, t + HOLD * 0.05);
    }
    if (wsCode.length) {
      tl.to(wsCode, { opacity: 1, y: 0, duration: HOLD * 0.4, stagger: 0.07 }, t + HOLD * 0.2);
    }
    if (wsAi) {
      tl.to(wsAi, { opacity: 1, x: 0, duration: HOLD * 0.4 }, t + HOLD * 0.35);
    }
    t += HOLD;
    scaleOut(3, 4, t);
    t += FADE;

    // —— AI ——
    tl.addLabel("ai", t);
    if (aiLines.length) {
      tl.to(aiLines, { opacity: 1, y: 0, duration: HOLD * 0.35, stagger: 0.06 }, t + HOLD * 0.05);
    }
    if (applyBtn) {
      tl.to(
        applyBtn,
        {
          scale: 1,
          boxShadow: "0 8px 24px rgba(17,17,15,0.12)",
          duration: HOLD * 0.4,
        },
        t + HOLD * 0.35
      );
    }
    t += HOLD;
    scaleOut(4, 5, t);
    t += FADE;

    // —— Tests ——
    tl.addLabel("tests", t);
    if (termFail.length) {
      tl.to(termFail, { opacity: 0.25, duration: HOLD * 0.35 }, t + HOLD * 0.15);
    }
    if (termPass.length) {
      tl.to(termPass, { opacity: 1, y: 0, duration: HOLD * 0.4, stagger: 0.07 }, t + HOLD * 0.35);
    }
    t += HOLD;
    scaleOut(5, 6, t);
    t += FADE;

    // —— Report ——
    tl.addLabel("report", t);
    if (ring) {
      const scoreProxy = { v: 0 };
      tl.to(
        scoreProxy,
        {
          v: 87,
          duration: HOLD * 0.75,
          onUpdate: () => {
            const n = Math.round(scoreProxy.v);
            ring.style.setProperty("--score", String(n));
            ring.textContent = String(n);
          },
        },
        t + HOLD * 0.1
      );
    }
    if (dimItems.length) {
      tl.to(dimItems, { opacity: 1, x: 0, duration: HOLD * 0.4, stagger: 0.05 }, t + HOLD * 0.15);
    }
    if (dimBars.length) {
      dimBars.forEach((bar, i) => {
        const fill = Number(bar.getAttribute("data-fill") || 80);
        const proxy = { v: 0 };
        tl.to(
          proxy,
          {
            v: fill,
            duration: HOLD * 0.5,
            onUpdate: () => bar.style.setProperty("--fill", String(Math.round(proxy.v))),
          },
          t + HOLD * 0.2 + i * 0.04
        );
      });
    }
    t += HOLD;
    scaleOut(6, 7, t);
    t += FADE;

    // —— CTA ——
    tl.addLabel("cta", t);
    if (ctaNav.length) {
      tl.to(ctaNav[0], { color: accent, duration: HOLD * 0.3 }, t);
    }
    if (ctaBtns.length) {
      tl.to(ctaBtns, { y: 0, opacity: 1, duration: HOLD * 0.45, stagger: 0.08 }, t + HOLD * 0.1);
    }
    t += HOLD;

    // Brand is a short beat; remaining beats keep HOLD+FADE; last beat hold only.
    const expected = BRAND_EXIT + (BEATS.length - 2) * BEAT + HOLD;
    if (Math.abs(tl.duration() - expected) > 0.05) {
      tl.to({}, { duration: Math.max(0, expected - tl.duration()) }, t);
    }

    const glow = $(".pc-seq-glow");
    if (glow) {
      gsap.to(glow, {
        opacity: 0.55,
        duration: 3,
        yoyo: true,
        repeat: -1,
        ease: "sine.inOut",
      });
    }

    // Refresh after layout; setTimeout works even when rAF is paused.
    setTimeout(() => ScrollTrigger.refresh(), 0);
    window.addEventListener(
      "resize",
      () => {
        ScrollTrigger.refresh();
      },
      { passive: true }
    );

    window.addEventListener("pagehide", () => {
      ScrollTrigger.getAll().forEach((st) => st.kill());
    });
  }

  function boot() {
    if (reduced) {
      showStatic();
      return;
    }
    // Do not gate on rAF — background/headless tabs may never paint, so rAF never runs.
    const start = () => {
      try {
        if (window.gsap && window.ScrollTrigger) initSequence();
        else showStatic();
      } catch (_err) {
        showStatic();
      }
    };
    if (window.gsap && window.ScrollTrigger) start();
    else setTimeout(start, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
