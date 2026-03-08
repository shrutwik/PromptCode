// signup.js — externalized from signup.html inline script
'use strict';

if (PromptCodeAPI.isLoggedIn()) window.location.href = '/challenges.html';

function validateEmail(input) {
  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value);
  input.className = 'form-input ' + (input.value ? (valid ? 'valid' : 'invalid') : '');
}

function validateUsername(input) {
  const valid = /^[a-zA-Z0-9_]{3,}$/.test(input.value);
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
  let score = 0;
  if (val.length >= 8) score++;
  if (/[A-Z]/.test(val)) score++;
  if (/[0-9]/.test(val)) score++;
  if (/[^A-Za-z0-9]/.test(val)) score++;
  const cls = score <= 1 ? 'weak' : score <= 2 ? 'ok' : 'strong';
  const labels = ['', 'weak', 'weak', 'ok', 'strong'];
  for (let i = 0; i < score; i++) bars[i].classList.add(cls);
  label.textContent = labels[score];
  label.style.color = score <= 1 ? 'var(--danger)' : score <= 2 ? 'var(--warn)' : 'var(--success)';
}

async function handleSignup(e) {
  e.preventDefault();
  const btn = document.getElementById('submitBtn');
  const fname = document.getElementById('fname').value.trim();
  const email = document.getElementById('email').value.trim();
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;

  if (!email || !username || !password || password.length < 8) {
    btn.textContent = 'please fill all fields (password \u2265 8 chars)';
    setTimeout(() => { btn.textContent = 'create account \u2192'; }, 2000);
    return;
  }
  btn.textContent = 'creating account...';
  btn.disabled = true;
  try {
    await PromptCodeAPI.signup({
      email,
      username,
      first_name: fname,
      last_name: '',
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
