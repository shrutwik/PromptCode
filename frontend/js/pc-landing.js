/** PromptCode landing — motion layer.
 *
 * Three jobs, in order of importance:
 *   1. Progressive enhancement. We add `.re-js` ourselves, so if this file
 *      never runs the page is already the finished, readable version.
 *   2. The signature moment: the hero headline falls into place. Words are
 *      plain inline text; a small fixed-step integrator gives them gravity,
 *      inter-word collisions, bounce, and cursor repulsion. It owns a word
 *      only while that word is still moving, then hands the final state back
 *      to CSS by zeroing the transform.
 *   3. Scroll entrances + light parallax. Section level only, one-shot, and
 *      entirely inside a reduced-motion guard.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var fine = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  function each(list, fn) { Array.prototype.forEach.call(list, fn); }
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  /* ── 1 · Mark that JS is alive ──────────────────────────────────── */
  root.classList.add("re-js");
  var header = $(".pc-header");
  if (header) header.classList.add("re-header");

  /* Pre-declare stagger indices so CSS delays have something to read. */
  $$("[data-re-stagger]").forEach(function (group) {
    Array.prototype.forEach.call(group.children, function (child, i) {
      child.style.setProperty("--i", i);
    });
  });  $$("[data-re-row]").forEach(function (row, i) {
    row.style.setProperty("--i", i);
  });
  $$("[data-re-bar]").forEach(function (bar) {
    var len = parseFloat(bar.getAttribute("data-w") || "60");
    bar.style.setProperty("--re-bar-w", len + "%");
  });

  /* Hero copy enters in reading order on load. */
  var heroCopy = $(".re-hero-copy");
  if (heroCopy) {
    var order = 0;
    Array.prototype.forEach.call(heroCopy.children, function (child) {
      if (child.hasAttribute("data-re-drop")) return;
      child.setAttribute("data-re-enter", "");
      child.style.setProperty("--i", order++);
    });
  }

  /* Ring geometry: 2πr for r = 42, read from the markup's target length.
     Both the empty and drawn states live in CSS; this only supplies the
     target length and a safety net if the observer never fires. */
  var ring = $("[data-re-ring]");
  if (ring) {
    var path = 2 * Math.PI * 42;
    var target = parseFloat(ring.getAttribute("data-re-ring")) || path * 0.72;
    ring.parentNode.style.setProperty("--re-ring-len", target.toFixed(1));
    window.setTimeout(function () {
      var report = $(".re-report");
      if (report) report.classList.add("is-in");
    }, 2500);
  }

  /* ── 2 · Signature moment: the headline settles into place ──────────
   * One restrained gesture: each word eases down from just above its own
   * resting position and lands. Timed and eased rather than sprung, so the
   * travel is monotonic and stops exactly on the baseline — no bounce, no
   * overshoot, no lateral drift, no cursor shoving. All of those extras were
   * running at once, and together they read as fidgety.
   */
  var DROP = 24;           // px each word starts above its resting position
  var TRAVEL = 520;        // ms for one word to cover that distance
  var STAGGER = 70;        // ms between words, so the line lands as one gesture
  var LEAD = 90;           // ms before the first word moves

  function initDrop() {
    var h1 = $("[data-re-drop]");
    if (!h1) return;

    /* Wrap each visual word in a span so it can move on its own, keeping inline
       emphasis inside the word it belongs to. Whitespace stays as bare text
       nodes, so the line still wraps exactly as it would unstyled. */
    var nodes = Array.prototype.slice.call(h1.childNodes);
    h1.textContent = "";
    var spans = [];
    function pushWord(el) { h1.appendChild(el); spans.push(el); }

    nodes.forEach(function (node) {
      if (node.nodeType === 3) {
        node.textContent.split(/(\s+)/).forEach(function (piece) {
          if (!piece) return;
          if (/^\s+$/.test(piece)) { h1.appendChild(document.createTextNode(piece)); return; }
          var s = document.createElement("span");
          s.className = "re-word";
          s.textContent = piece;
          pushWord(s);
        });
      } else if (node.nodeType === 1) {
        var tag = node.tagName.toLowerCase();
        node.textContent.split(/(\s+)/).forEach(function (piece) {
          if (!piece) return;
          if (/^\s+$/.test(piece)) { h1.appendChild(document.createTextNode(piece)); return; }
          var wrap = document.createElement("span");
          wrap.className = "re-word";
          var inner = document.createElement(tag);
          inner.textContent = piece;
          wrap.appendChild(inner);
          pushWord(wrap);
        });
      }
    });
    if (!spans.length) return;

    var words = spans.map(function (el, i) {
      return {
        el: el,
        p: 0,            // 0 = start of travel, 1 = at rest
        launched: false,
        asleep: false,
        delay: LEAD + i * STAGGER,
        i: i
      };
    });

    /* One clock, seeded from the rAF timestamp, so a replay restarts cleanly.
       The sentinels are -1, not 0: a rAF timestamp of exactly 0 is falsy, so a
       `!started` test would fail to latch and elapsed would stay pinned at 0. */
    var raf = 0, last = -1, started = -1;
    var maxDelay = words[words.length - 1].delay;

    /* Decelerating cubic curve. Monotonic, so a word never travels backwards
       and never crosses its resting position. */
    function ease(t) { return 1 - Math.pow(1 - t, 3); }

    function rest(w) {
      w.p = 1;
      w.el.style.transform = "";
      w.el.style.opacity = "";
      w.asleep = true;
    }

    function step(elapsed) {
      var waiting = 0;
      var moving = 0;

      words.forEach(function (w) {
        if (w.asleep) return;
        if (!w.launched) {
          if (elapsed < w.delay) { waiting++; return; }
          w.launched = true;
          // Render the start pose on this frame. Without it the first frame
          // computes a eased offset of exactly DROP, `p >= 1` never holds, and
          // a word could be parked before it ever visibly moved.
          var start = DROP;
          w.el.style.willChange = "transform, opacity";
          w.el.style.transform = "translate3d(0," + start + "px,0)";
          w.el.style.opacity = "0.00";
          w.p = 0;
          moving++;
          return;
        }

        var p = Math.min(1, (elapsed - w.delay) / TRAVEL);
        if (p >= 1) { rest(w); return; }

        var eased = ease(p);
        w.p = p;
        w.el.style.willChange = "transform, opacity";
        w.el.style.transform = "translate3d(0," + (DROP * (1 - eased)).toFixed(2) + "px,0)";
        // Fade in over the first third of the travel, so a word never shows up
        // as a washed-out ghost parked above the line.
        w.el.style.opacity = Math.min(1, p / 0.34).toFixed(2);
        moving++;
      });

      if (elapsed > maxDelay) waiting = 0;
      return moving > 0 || waiting > 0;
    }

    function tick(now) {
      raf = 0;
      if (last < 0) last = now;
      if (started < 0) started = now;
      last = now;
      if (step(now - started)) raf = requestAnimationFrame(tick);
    }

    function start() {
      if (raf) return;
      raf = requestAnimationFrame(tick);
    }

    function stop() {
      if (!raf) return;
      cancelAnimationFrame(raf);
      raf = 0;
    }

    /* Restart the settle. Called on first paint and whenever the headline
       scrolls back into view, so scrolling up rewinds it and the next pass
       down replays it. */
    var resetting = false;
    function replay() {
      if (resetting) return;
      resetting = true;
      stop();
      if (reduced) {
        words.forEach(rest);
        h1.classList.remove("is-dropping");
        resetting = false;
        return;
      }
      /* Put every word at its start pose here, not on its first animated frame.
         Otherwise the word is briefly rendered at rest and then jumps up to
         its start, which is a visible flash of the finished line. */
      words.forEach(function (w) {
        w.launched = false;
        w.asleep = false;
        w.p = 0;
        w.el.style.willChange = "transform, opacity";
        w.el.style.transform = "translate3d(0," + DROP + "px,0)";
        w.el.style.opacity = "0.00";
      });
      h1.classList.add("is-dropping");
      started = -1;
      last = -1;
      start();
      resetting = false;
    }

    var remeasure;
    window.addEventListener("resize", function () {
      window.clearTimeout(remeasure);
      remeasure = window.setTimeout(replay, 180);
    });

    // Font metrics shift the line, so redo the settle once they are final.
    if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
      document.fonts.ready.then(function () {
        if (window.scrollY < window.innerHeight * 0.5) replay();
      });
    }

    // Replay on entry, park on exit. No rAF runs while the hero is off screen.
    if ("IntersectionObserver" in window) {
      var heroIo = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) { replay(); return; }
          stop();
          words.forEach(function (w) { if (!w.asleep) rest(w); });
        });
      }, { threshold: 0.2 });
      heroIo.observe(h1);
    }

    /* Run the settle now. The observer's initial callback is not guaranteed to
       report the headline as intersecting, so waiting for it can leave the
       headline sitting at rest with no animation on a fresh load. */
    replay();
  }

  /* ── 3 · Scroll entrances (reversible) ──────────────────────────────
   * Every element clears `is-in` when it leaves the viewport, so scrolling
   * back up rewinds the motion and the next pass down replays it. One
   * threshold, one rootMargin, no unobserving — entry and exit happen at the
   * same line, which is what keeps it from flickering.
   */
  function initReveals() {
    var targets = $$("[data-re-reveal], [data-re-stagger], .re-act, [data-re-shot], .re-term, .re-report");
    if (!targets.length) return;

    if (reduced || !("IntersectionObserver" in window)) {
      targets.forEach(function (el) { el.classList.add("is-in"); });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        entry.target.classList.toggle("is-in", entry.isIntersecting);
      });
    }, { rootMargin: "0px 0px -18% 0px", threshold: 0.08 });

    targets.forEach(function (el) { io.observe(el); });
  }

  /* ── 4 · Parallax + the hero's ambient planes ───────────────────── */
  function initParallax() {
    if (reduced) return;
    var layers = $$("[data-re-parallax]");
    var gridLines = $(".re-grid-lines");
    if (!layers.length && !gridLines) return;

    var ticking = false;
    var amp = window.innerWidth < 1000 ? 0.45 : 1;

    function apply() {
      ticking = false;
      var y = window.scrollY;
      // Foreground ratio per layer, declared in markup. Background runs slowest.
      layers.forEach(function (el) {
        var ratio = parseFloat(el.getAttribute("data-re-parallax")) || 0.08;
        el.style.transform = "translate3d(0," + (-y * ratio * amp).toFixed(2) + "px,0)";
      });
      if (gridLines) {
        gridLines.style.transform = "translate3d(0," + (y * 0.06 * amp).toFixed(2) + "px,0)";
      }
    }

    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(apply);
    }, { passive: true });

    window.addEventListener("resize", function () {
      amp = window.innerWidth < 1000 ? 0.45 : 1;
      apply();
    }, { passive: true });

    apply();
  }

  /* ── Boot ───────────────────────────────────────────────────────── */
  function boot() {
    initDrop();
    initReveals();
    initParallax();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
