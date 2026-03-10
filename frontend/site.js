'use strict';

(function () {
  function parseActionArgs(element) {
    const raw = element.dataset.actionArgs;
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [parsed];
    } catch (_) {
      return [];
    }
  }

  function invokeAction(attribute, event) {
    const element = event.target instanceof Element
      ? event.target.closest('[' + attribute + ']')
      : null;
    if (!element) return;

    const actionName = element.getAttribute(attribute);
    const action = actionName ? window[actionName] : null;
    if (typeof action !== 'function') return;

    if (event.type === 'click' && !element.hasAttribute('data-allow-default')) {
      event.preventDefault();
    }

    const args = [];
    if (element.dataset.passEvent === 'true') args.push(event);
    if (element.dataset.passElement === 'true') args.push(element);
    if (element.dataset.passValue === 'true') args.push(element.value);
    args.push(...parseActionArgs(element));
    action(...args);
  }

  function bindHamburgers() {
    document.querySelectorAll('.hamburger').forEach((button) => {
      if (button.dataset.siteBound === 'true') return;
      button.dataset.siteBound = 'true';
      if (!button.hasAttribute('aria-expanded')) {
        button.setAttribute('aria-expanded', 'false');
      }
      button.addEventListener('click', function () {
        const nav = this.closest('nav');
        const links = nav ? nav.querySelector('.nav-links') : null;
        if (!links) return;
        const isOpen = links.classList.toggle('mobile-open');
        this.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });
    });
  }

  document.addEventListener('click', function (event) {
    invokeAction('data-click-action', event);
  });

  document.addEventListener('input', function (event) {
    invokeAction('data-input-action', event);
  });

  document.addEventListener('change', function (event) {
    invokeAction('data-change-action', event);
  });

  document.addEventListener('keydown', function (event) {
    invokeAction('data-keydown-action', event);
  });

  document.addEventListener('DOMContentLoaded', bindHamburgers);
})();
