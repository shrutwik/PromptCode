// login.js — externalized from login.html inline script
'use strict';

function nextDestination() {
  const next = new URLSearchParams(window.location.search).get('next') || '';
  // Same-origin paths only; never bounce back to auth pages.
  if (next.startsWith('/') && !next.startsWith('//') && !/^\/(login|signup)(\.html)?/.test(next)) return next;
  return '/dashboard';
}

if (PromptCodeAPI.isLoggedIn()) window.location.href = nextDestination();

function showLoginError(message) {
  const err = document.getElementById('loginError');
  err.hidden = false;
  err.style.display = '';
  err.textContent = message;
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById('email').value.trim();
  const pass = document.getElementById('password').value;
  const err = document.getElementById('loginError');
  const btn = document.querySelector('.btn-submit');
  document.getElementById('email').setAttribute('aria-invalid', email ? 'false' : 'true');
  document.getElementById('password').setAttribute('aria-invalid', pass ? 'false' : 'true');
  if (!email || !pass) {
    showLoginError('Enter your email and password.');
    return;
  }
  err.hidden = true;
  const label = btn.textContent;
  btn.textContent = 'Signing in…';
  btn.disabled = true;
  try {
    await PromptCodeAPI.login(email, pass);
    window.location.href = nextDestination();
  } catch (error) {
    const raw = error.message || '';
    showLoginError(!raw || /unauthori[sz]ed/i.test(raw) ? 'Incorrect email or password.' : raw);
    btn.textContent = label;
    btn.disabled = false;
  }
}

function oauthLogin(provider) {
  // OAuth not yet implemented — redirect to signup
  window.location.href = '/signup.html';
}

document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('loginForm').addEventListener('submit', handleLogin);
});
