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

function showForgotError(message) {
  const err = document.getElementById('forgotError');
  err.hidden = false;
  err.style.display = '';
  err.textContent = message;
}

function showForgotForm(event) {
  if (event) event.preventDefault();
  document.getElementById('loginForm').hidden = true;
  document.getElementById('forgotForm').hidden = false;
  const email = document.getElementById('email').value.trim();
  if (email) document.getElementById('forgotEmail').value = email;
  document.getElementById('forgotEmail').focus();
}

function showSignInForm(event) {
  if (event) event.preventDefault();
  document.getElementById('forgotForm').hidden = true;
  document.getElementById('loginForm').hidden = false;
}

async function handleForgot(event) {
  event.preventDefault();
  const email = document.getElementById('forgotEmail').value.trim();
  const notice = document.getElementById('forgotNotice');
  const err = document.getElementById('forgotError');
  const btn = document.getElementById('forgotSubmit');
  notice.hidden = true;
  err.hidden = true;
  if (!email) {
    showForgotError('Enter your email.');
    return;
  }
  const label = btn.textContent;
  btn.textContent = 'Sending…';
  btn.disabled = true;
  try {
    const resp = await fetch(window.location.origin + '/api/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email }),
    });
    const data = await resp.json().catch(function () { return {}; });
    if (!resp.ok) {
      const detail = data && data.detail;
      showForgotError(typeof detail === 'string' ? detail : 'Could not send reset instructions.');
      return;
    }
    notice.hidden = false;
    notice.style.display = '';
    notice.textContent = (data && data.message) || 'If an account exists for that email, we sent password reset instructions.';
    if (data && data.reset_token) {
      notice.appendChild(document.createTextNode(' '));
      const link = document.createElement('a');
      link.href = '/reset-password.html?token=' + encodeURIComponent(data.reset_token);
      link.textContent = 'Continue to reset';
      notice.appendChild(link);
    }
  } catch (_) {
    showForgotError('Could not send reset instructions.');
  } finally {
    btn.textContent = label;
    btn.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('loginForm').addEventListener('submit', handleLogin);
  document.getElementById('forgotPasswordLink').addEventListener('click', showForgotForm);
  document.getElementById('backToSignIn').addEventListener('click', showSignInForm);
  document.getElementById('forgotForm').addEventListener('submit', handleForgot);
});
