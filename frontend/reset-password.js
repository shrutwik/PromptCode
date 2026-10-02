'use strict';

function showResetError(message) {
  const err = document.getElementById('resetError');
  err.hidden = false;
  err.style.display = '';
  err.textContent = message;
}

function readDetail(data) {
  const detail = data && data.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map(function (item) { return item.msg || item.message || ''; }).filter(Boolean).join(' ');
  }
  return '';
}

async function handleReset(event) {
  event.preventDefault();
  const token = document.getElementById('token').value.trim();
  const password = document.getElementById('newPassword').value;
  const confirm = document.getElementById('confirmPassword').value;
  const notice = document.getElementById('resetNotice');
  const err = document.getElementById('resetError');
  const btn = document.querySelector('.btn-submit');
  notice.hidden = true;
  err.hidden = true;
  if (!token || !password) {
    showResetError('Enter the reset token and a new password.');
    return;
  }
  if (password !== confirm) {
    showResetError('Passwords do not match.');
    return;
  }
  const label = btn.textContent;
  btn.textContent = 'Updating…';
  btn.disabled = true;
  try {
    const resp = await fetch(window.location.origin + '/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token, new_password: password }),
    });
    const data = await resp.json().catch(function () { return {}; });
    if (!resp.ok) {
      showResetError(readDetail(data) || 'Could not reset password.');
      btn.textContent = label;
      btn.disabled = false;
      return;
    }
    notice.hidden = false;
    notice.style.display = '';
    notice.textContent = (data && data.message) || 'Password updated.';
    window.setTimeout(function () {
      window.location.href = '/login.html';
    }, 800);
  } catch (_) {
    showResetError('Could not reset password.');
    btn.textContent = label;
    btn.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', function () {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token') || '';
  if (token) document.getElementById('token').value = token;
  document.getElementById('resetForm').addEventListener('submit', handleReset);
});
