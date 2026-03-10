// signup.js — externalized from signup.html inline script
'use strict';

if (PromptCodeAPI.isLoggedIn()) window.location.href = '/challenges.html';

function usernameValid(value) {
  return /^[A-Za-z0-9](?:[A-Za-z0-9_-]{1,62}[A-Za-z0-9])$/.test(value);
}

function passwordValidationError(value) {
  if (!value) return 'password is required';
  if (value.length < 12) return 'password must be at least 12 characters';
  if (!/[a-z]/.test(value)) return 'password must include a lowercase letter';
  if (!/[A-Z]/.test(value)) return 'password must include an uppercase letter';
  if (!/[0-9]/.test(value)) return 'password must include a number';
  if (!/[^A-Za-z0-9]/.test(value)) return 'password must include a symbol';
  if ((new TextEncoder().encode(value)).length > 72) return 'password is too long';
  return '';
}

function validateEmail(input) {
  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value);
  input.className = 'form-input ' + (input.value ? (valid ? 'valid' : 'invalid') : '');
}

function validateUsername(input) {
  const valid = usernameValid(input.value.trim());
  input.className = 'form-input ' + (input.value ? (valid ? 'valid' : 'invalid') : '');
}

function checkStrength(val) {
  const bars = [
    document.getElementById('b1'),
    document.getElementById('b2'),
    document.getElementById('b3'),
    document.getElementById('b4'),
  ];
  const label = document.getElementById('pwLabel');
  bars.forEach(b => { b.className = 'pw-bar'; });
  if (!val) { label.textContent = ''; return; }
  const error = passwordValidationError(val);
  let score = 0;
  if (val.length >= 12) score++;
  if (/[a-z]/.test(val)) score++;
  if (/[A-Z]/.test(val)) score++;
  if (/[0-9]/.test(val)) score++;
  if (/[^A-Za-z0-9]/.test(val)) score++;
  const cls = score <= 2 ? 'weak' : score <= 3 ? 'ok' : 'strong';
  const labels = ['', 'weak', 'weak', 'ok', 'strong', 'strong'];
  for (let i = 0; i < score; i++) bars[i].classList.add(cls);
  label.textContent = error || labels[score];
  label.style.color = error ? 'var(--danger)' : (score <= 2 ? 'var(--warn)' : 'var(--success)');
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

  if (!email || !username || !password) {
    btn.textContent = 'please fill all required fields';
    setTimeout(() => { btn.textContent = 'create account \u2192'; }, 2000);
    return;
  }
  if (!usernameValid(username)) {
    btn.textContent = 'username must be 3-64 chars: letters, numbers, _ or -';
    setTimeout(() => { btn.textContent = 'create account \u2192'; }, 2500);
    return;
  }
  if (passwordError) {
    btn.textContent = passwordError;
    setTimeout(() => { btn.textContent = 'create account \u2192'; }, 2500);
    return;
  }
  btn.textContent = 'creating account...';
  btn.disabled = true;
  try {
    await PromptCodeAPI.signup({
      email,
      username,
      first_name: fname,
      last_name: lname,
      password,
    });
    window.location.href = '/challenges.html';
  } catch (err) {
    btn.textContent = err.message || 'signup failed \u2014 try again';
    btn.disabled = false;
    setTimeout(() => { btn.textContent = 'create account \u2192'; }, 3000);
  }
}

document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('signupForm').addEventListener('submit', handleSignup);
  document.getElementById('email').addEventListener('input', function () { validateEmail(this); });
  document.getElementById('username').addEventListener('input', function () { validateUsername(this); });
  document.getElementById('password').addEventListener('input', function () { checkStrength(this.value); });
});
