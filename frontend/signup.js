// signup.js — externalized from signup.html inline script
'use strict';

if (PromptCodeAPI.isLoggedIn()) window.location.href = '/dashboard';

const USERNAME_RULE = 'Username must be 3-64 chars: letters, numbers, _ or -';

function usernameValid(value) {
  return /^[A-Za-z0-9](?:[A-Za-z0-9_-]{1,62}[A-Za-z0-9])$/.test(value);
}

function emailValid(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function passwordValidationError(value) {
  if (!value) return 'Password is required';
  if (value.length < 12) return 'Password must be at least 12 characters';
  if (!/[a-z]/.test(value)) return 'Password must include a lowercase letter';
  if (!/[A-Z]/.test(value)) return 'Password must include an uppercase letter';
  if (!/[0-9]/.test(value)) return 'Password must include a number';
  if (!/[^A-Za-z0-9]/.test(value)) return 'Password must include a symbol';
  if ((new TextEncoder().encode(value)).length > 72) return 'Password is too long';
  return '';
}

function setFieldError(id, message) {
  const input = document.getElementById(id);
  const err = document.getElementById(id + 'Error');
  input.setAttribute('aria-invalid', message ? 'true' : 'false');
  if (message) input.removeAttribute('data-valid');
  if (err) err.textContent = message || '';
}

function showFormError(message) {
  const alert = document.getElementById('signupError');
  alert.textContent = message;
  alert.hidden = !message;
}

function markLive(input, valid) {
  if (!input.value) {
    input.removeAttribute('data-valid');
    input.removeAttribute('aria-invalid');
    return;
  }
  input.setAttribute('data-valid', valid ? 'true' : 'false');
  if (valid) setFieldError(input.id, '');
}

function validateEmail(input) {
  markLive(input, emailValid(input.value));
}

function validateUsername(input) {
  markLive(input, usernameValid(input.value.trim()));
}

function checkStrength(val) {
  const bars = ['b1', 'b2', 'b3', 'b4'].map(id => document.getElementById(id));
  const label = document.getElementById('pwLabel');
  bars.forEach(b => { b.className = 'pw-bar'; });
  if (!val) { label.textContent = ''; label.removeAttribute('data-tone'); return; }
  const error = passwordValidationError(val);
  let score = 0;
  if (val.length >= 12) score++;
  if (/[a-z]/.test(val)) score++;
  if (/[A-Z]/.test(val)) score++;
  if (/[0-9]/.test(val)) score++;
  if (/[^A-Za-z0-9]/.test(val)) score++;
  const cls = score <= 2 ? 'weak' : score <= 3 ? 'ok' : 'strong';
  const labels = ['', 'Weak', 'Weak', 'OK', 'Strong', 'Strong'];
  // 5 criteria, 4 bars: never index past the last bar.
  for (let i = 0; i < Math.min(score, bars.length); i++) bars[i].classList.add(cls);
  label.textContent = error || labels[score];
  label.dataset.tone = error ? 'danger' : (score <= 2 ? 'warn' : 'success');
  if (!error) setFieldError('password', '');
}

async function handleSignup(e) {
  e.preventDefault();
  const btn = document.getElementById('submitBtn');
  const fname = document.getElementById('fname').value.trim();
  const lname = document.getElementById('lname').value.trim();
  const email = document.getElementById('email').value.trim();
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const passwordError = passwordValidationError(password);

  const errors = {
    email: email ? '' : 'Email is required',
    username: !username ? 'Username is required' : (usernameValid(username) ? '' : USERNAME_RULE),
    password: passwordError,
  };
  Object.entries(errors).forEach(([id, msg]) => setFieldError(id, msg));
  const firstBad = Object.keys(errors).find(id => errors[id]);
  if (firstBad) {
    showFormError(!email || !username || !password
      ? 'Please fill all required fields.'
      : 'Please fix the highlighted fields.');
    document.getElementById(firstBad).focus();
    return;
  }

  showFormError('');
  const label = btn.textContent;
  btn.textContent = 'Creating account…';
  btn.disabled = true;
  try {
    await PromptCodeAPI.signup({
      email,
      username,
      first_name: fname,
      last_name: lname,
      password,
    });
    window.location.href = '/onboarding';
  } catch (err) {
    showFormError(err.message || 'Signup failed — try again.');
    btn.textContent = label;
    btn.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('signupForm').addEventListener('submit', handleSignup);
  document.getElementById('email').addEventListener('input', function () { validateEmail(this); });
  document.getElementById('username').addEventListener('input', function () { validateUsername(this); });
  document.getElementById('password').addEventListener('input', function () { checkStrength(this.value); });
});
