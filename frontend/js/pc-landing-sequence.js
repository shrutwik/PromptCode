/** PromptCode landing — continuous, native-scroll product story. */
(function () {
  const reduced =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function $$(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function showStatic() {
    document.querySelectorAll(".pc-seq-stage").forEach((s) => {
      s.style.opacity = "1";
      s.style.visibility = "visible";
      s.classList.add("is-live");
    });
    const hint = $(".pc-seq-scrollhint");
    if (hint) hint.hidden = true;
    const ring = $(".pc-seq-ring");
    if (ring) {
      ring.style.setProperty("--score", "72");
      ring.textContent = "72";
    }
    $$(".pc-seq-dim-bar").forEach((b) => {
      b.style.setProperty("--fill", b.getAttribute("data-fill") || "80");
    });
    $$(".pc-seq-term-fail").forEach((el) => {
      el.style.opacity = "1";
    });
    $$(".pc-seq-term-pass, .pc-seq-term-sum").forEach((el) => {
      el.style.opacity = "1";
    });
  }

  function finePointer() {
    return (
      !reduced &&
      window.matchMedia("(hover: hover) and (pointer: fine)").matches
    );
  }

  /** Light on the opening and closing beats follows the cursor. No tracking when motion is reduced. */
  function bindPointerLight() {
    if (!finePointer()) return;
    const root = $(".pc-seq-sticky");
    if (!root) return;
    let frame = 0;
    let px = 0;
    let py = 0;
    root.addEventListener(
      "pointermove",
      (event) => {
        px = event.clientX;
        py = event.clientY;
        if (frame) return;
        frame = requestAnimationFrame(() => {
          frame = 0;
          const rect = root.getBoundingClientRect();
          const x = ((px - rect.left) / Math.max(rect.width, 1)) * 100;
          const y = ((py - rect.top) / Math.max(rect.height, 1)) * 100;
          root.style.setProperty("--pc-seq-x", x.toFixed(1) + "%");
          root.style.setProperty("--pc-seq-y", y.toFixed(1) + "%");
        });
      },
      { passive: true }
    );
  }

  /** CTA buttons lean a few pixels toward the pointer. */
  function bindButtonPull() {
    if (!finePointer()) return;
    $$(".pc-seq-actions .btn").forEach((btn) => {
      btn.addEventListener("pointermove", (event) => {
        const rect = btn.getBoundingClientRect();
        const dx = ((event.clientX - (rect.left + rect.width / 2)) / Math.max(rect.width, 1)) * 4;
        const dy = ((event.clientY - (rect.top + rect.height / 2)) / Math.max(rect.height, 1)) * 3;
        btn.style.translate = dx.toFixed(1) + "px " + dy.toFixed(1) + "px";
      });
      btn.addEventListener("pointerleave", () => {
        btn.style.translate = "";
      });
    });
  }

  function boot() {
    showStatic();
    bindPointerLight();
    bindButtonPull();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
