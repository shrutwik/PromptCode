document.documentElement.classList.add('lp-js');

(function revealOnScroll() {
  const items = document.querySelectorAll('.lp-reveal');
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const viewDriven = window.CSS && CSS.supports && CSS.supports('animation-timeline: view()');
  if (reduced || !items.length) {
    items.forEach(el => el.classList.add('is-in'));
    return;
  }
  if (viewDriven) return;
  if (!('IntersectionObserver' in window)) {
    items.forEach(el => el.classList.add('is-in'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-in');
      io.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
  items.forEach(el => io.observe(el));
})();

PromptCodeAPI.updateNavAuth();
