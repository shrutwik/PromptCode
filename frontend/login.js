// login.js — externalized from login.html inline script
'use strict';

if (PromptCodeAPI.isLoggedIn()) window.location.href = '/challenges.html';

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById('email').value.trim();
  const pass = document.getElementById('password').value;
  const err = document.getElementById('loginError');
  if (!email || !pass) {
    err.style.display = 'block';
    err.textContent = 'please fill in all fields';
    return;
  }
  err.style.display = 'none';
  const btn = document.querySelector('.btn-submit');
  btn.textContent = 'signing in...';
  try {
    await PromptCodeAPI.login(email, pass);
    window.location.href = '/challenges.html';
  } catch (error) {
    err.style.display = 'block';
    err.textContent = error.message || 'incorrect email or password';
    btn.textContent = 'sign in \u2192';
  }
}

function oauthLogin(provider) {
  // OAuth not yet implemented — redirect to signup
  window.location.href = '/signup.html';
}

document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('loginForm').addEventListener('submit', handleLogin);
});
