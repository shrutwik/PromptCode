// profile.js — externalized from profile.html inline script
'use strict';

function timeAgo(dateStr) {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  const days = Math.floor(hrs / 24);
  if (days < 30) return days + 'd ago';
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function fmt(v, decimals = 2) {
  if (v == null) return '\u2014';
  return Number(v).toFixed(decimals);
}

function statusTone(status) {
  if (!status) return 'idle';
  const s = status.toLowerCase();
  if (s === 'completed' || s === 'passed') return 'success';
  if (s === 'failed') return 'danger';
  return 'warn';
}

function scoreClass(v) {
  if (v == null) return '';
  if (v >= 0.8) return 'good';
  if (v >= 0.65) return 'warn';
  return 'bad';
}

function renderHistory(list, emptyText) {
  const histList = document.getElementById('historyList');
  if (!histList) return;
  if (list.length === 0) {
    histList.innerHTML = `<tr><td colspan="5" class="cell-empty">${escHtml(emptyText)}</td></tr>`;
    return;
  }
  histList.innerHTML = '';
  list.forEach(s => {
    const href = `/submission.html?id=${encodeURIComponent(s.id)}`;
    const tr = document.createElement('tr');
    tr.className = 'sh-row';
    tr.dataset.href = href;
    const growth = s.growth_score != null ? fmt(s.growth_score) : '\u2014';
    tr.innerHTML = `
      <td class="title-cell"><a class="sh-name" href="${href}">${escHtml(s.challenge_title || 'Challenge #' + s.challenge_id)}</a><div class="sh-status"><span class="tag" data-tone="${statusTone(s.status)}">${escHtml(s.status)}</span></div></td>
      <td class="num sh-score ${scoreClass(s.score_overall)}">${s.score_overall != null ? fmt(s.score_overall) : '\u2014'}</td>
      <td class="num">${growth}</td>
      <td class="num">${s.total_cost_usd != null ? '$' + fmt(s.total_cost_usd) : '\u2014'}</td>
      <td class="num">${s.created_at ? timeAgo(s.created_at) : '\u2014'}</td>
    `;
    histList.appendChild(tr);
  });
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

function filterHistory(mode, btn) {
  document.querySelectorAll('#filterAll, #filterSolved').forEach(b => {
    b.classList.remove('is-active');
    b.setAttribute('aria-pressed', 'false');
  });
  btn.classList.add('is-active');
  btn.setAttribute('aria-pressed', 'true');
  const subs = window._allHistorySubs || [];
  const filtered = mode === 'solved'
    ? subs.filter(s => { const st = (s.status || '').toLowerCase(); return st === 'completed' || st === 'passed'; })
    : subs;
  renderHistory(filtered, 'No matching submissions');
}

function editProfile() {
  const user = PromptCodeAPI.getUser();
  if (!user) return;
  const overlay = document.createElement('div');
  overlay.className = 'modal';
  overlay.innerHTML = `
    <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="editProfileTitle">
      <div class="modal-head">
        <h2 id="editProfileTitle">Edit profile</h2>
        <button type="button" class="btn btn-quiet btn-sm btn-icon" id="editClose" aria-label="Close">
          <svg class="pc-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
        </button>
      </div>
      <div class="pc-field"><label for="editFirst">First name</label><input id="editFirst" type="text" autocomplete="given-name" value="${escHtml(user.first_name || '')}"></div>
      <div class="pc-field"><label for="editLast">Last name</label><input id="editLast" type="text" autocomplete="family-name" value="${escHtml(user.last_name || '')}"></div>
      <div class="pc-field"><label for="editBio">Bio</label><textarea id="editBio" rows="3">${escHtml(user.bio || '')}</textarea></div>
      <div class="pc-row" style="justify-content:flex-end">
        <button type="button" id="editCancel" class="btn btn-ghost">Cancel</button>
        <button type="button" id="editSave" class="btn btn-primary">Save</button>
      </div>
    </div>
  `;
  const opener = document.activeElement;
  const close = () => {
    overlay.remove();
    document.removeEventListener('keydown', onKey);
    if (opener && opener.focus) opener.focus();
  };
  const onKey = e => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  document.getElementById('editCancel').addEventListener('click', close);
  document.getElementById('editClose').addEventListener('click', close);
  document.getElementById('editFirst').focus();
  document.getElementById('editSave').addEventListener('click', async () => {
    const btn = document.getElementById('editSave');
    btn.textContent = 'Saving…';
    btn.disabled = true;
    try {
      await PromptCodeAPI.updateMe({
        first_name: document.getElementById('editFirst').value,
        last_name: document.getElementById('editLast').value,
        bio: document.getElementById('editBio').value,
      });
      close();
      location.reload();
    } catch (e) {
      btn.textContent = 'Error \u2014 retry';
      btn.disabled = false;
    }
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  PromptCodeAPI.updateNavAuth();

  const localUser = PromptCodeAPI.getUser();
  if (!localUser) {
    window.location.href = '/login.html';
    return;
  }

  const params = new URLSearchParams(window.location.search);
  const targetUsername = params.get('user') || localUser.username;
  const isOwnProfile = targetUsername === localUser.username;

  const editBtn = document.getElementById('editProfileBtn');
  const signOutBtn = document.getElementById('signOutBtn');
  if (isOwnProfile) {
    if (editBtn) editBtn.style.display = '';
    if (signOutBtn) signOutBtn.style.display = '';
  }

  const $ = id => document.getElementById(id);
  if (window.PCUI && $('historyLoading')) $('historyLoading').innerHTML = PCUI.skeletonRows(3);

  // Header placeholders from local user while API loads
  $('profileHandle').textContent = targetUsername;

  let profile;
  try {
    profile = await PromptCodeAPI.getUserProfile(targetUsername);
  } catch (e) {
    $('profileName').textContent = 'Could not load profile';
    renderHistory([], 'Profile unavailable');
    $('solvedList').innerHTML = '';
    console.error('Profile load failed:', e.message);
    return;
  }

  const user = profile.user || {};
  const stats = profile.stats || {};
  const subs = profile.recent_submissions || [];

  // --- Profile header ---
  const initials = ((user.first_name?.[0] || '') + (user.last_name?.[0] || '') || user.username?.substring(0, 2) || '??').toUpperCase();
  $('profileAvatar').textContent = initials;
  $('profileHandle').textContent = user.username || targetUsername;

  const nameParts = [user.first_name, user.last_name].filter(Boolean).join(' ');
  const joinDate = user.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
    : '';
  $('profileName').textContent = [nameParts, joinDate ? 'joined ' + joinDate : ''].filter(Boolean).join(' \u00b7 ') || user.username;

  if (user.bio) {
    $('profileBio').textContent = user.bio;
  } else {
    $('profileBio').style.display = 'none';
  }
  $('profileTags').style.display = 'none';

  // --- Stats row ---
  $('statAvgScore').textContent = fmt(stats.avg_score);
  $('statSolved').textContent = stats.challenges_solved ?? '\u2014';
  $('statSolvedLbl').textContent = stats.total_challenges
    ? `Solved / ${stats.total_challenges}`
    : 'Solved';
  $('statSubmissions').textContent = stats.total_submissions ?? '\u2014';
  $('statGrowth').textContent = fmt(stats.avg_growth_score);
  $('statCost').textContent = stats.total_cost_usd != null ? '$' + fmt(stats.total_cost_usd) : '\u2014';
  $('statLatency').textContent = stats.avg_latency_ms != null ? Math.round(stats.avg_latency_ms).toLocaleString() : '\u2014';

  // --- Score breakdown bars ---
  const breakdownMap = {
    Accuracy:      { val: stats.avg_accuracy,      el: 'bdAccuracy',      bar: 'bdAccuracyBar' },
    Reliability:   { val: stats.avg_reliability,    el: 'bdReliability',   bar: 'bdReliabilityBar' },
    Efficiency:    { val: stats.avg_efficiency,     el: 'bdEfficiency',    bar: 'bdEfficiencyBar' },
    Orchestration: { val: stats.avg_orchestration,  el: 'bdOrchestration', bar: 'bdOrchestrationBar' },
  };
  for (const [, cfg] of Object.entries(breakdownMap)) {
    const v = cfg.val;
    $(cfg.el).textContent = fmt(v);
    if (v != null) {
      const pct = Math.max(0, Math.min(100, Math.round(v * 100)));
      const bar = $(cfg.bar);
      bar.style.setProperty('--v', pct + '%');
      bar.parentElement.dataset.tone = v >= 0.8 ? 'success' : v >= 0.65 ? 'warn' : 'danger';
      bar.parentElement.setAttribute('aria-valuenow', String(pct));
      bar.style.animation = 'none';
      void bar.offsetWidth;
      bar.style.animation = '';
    }
  }

  // --- Your scores sidebar ---
  $('ysOverall').textContent = fmt(stats.avg_score);
  $('ysAccuracy').textContent = fmt(stats.avg_accuracy);
  $('ysEfficiency').textContent = fmt(stats.avg_efficiency);
  $('ysReliability').textContent = fmt(stats.avg_reliability);
  $('ysOrchestration').textContent = fmt(stats.avg_orchestration);
  $('ysGrowth').textContent = fmt(stats.avg_growth_score);

  // --- Submission history ---
  renderHistory(subs, 'No submissions yet');
  $('historyList').addEventListener('click', e => {
    const row = e.target.closest('tr[data-href]');
    if (!row || e.target.closest('a')) return;
    window.location.href = row.dataset.href;
  });

  // --- Solved challenges sidebar ---
  const solvedMap = new Map();
  subs.forEach(s => {
    const key = s.challenge_id;
    if (!solvedMap.has(key) || (s.score_overall || 0) > (solvedMap.get(key).score_overall || 0)) {
      solvedMap.set(key, s);
    }
  });
  const solved = [...solvedMap.values()].filter(s => {
    const st = (s.status || '').toLowerCase();
    return st === 'completed' || st === 'passed' || (s.score_overall && s.score_overall > 0);
  }).sort((a, b) => (b.score_overall || 0) - (a.score_overall || 0));

  $('solvedCount').textContent = solved.length > 0
    ? solved.length + (stats.total_challenges ? ' / ' + stats.total_challenges : '')
    : '';

  const solvedList = $('solvedList');
  if (solved.length === 0) {
    solvedList.innerHTML = '<div class="pc-empty is-compact"><h3>No solved challenges yet</h3></div>';
  } else {
    solvedList.innerHTML = '';
    solved.forEach(s => {
      const a = document.createElement('a');
      a.className = 'solved-item';
      a.href = `/submission.html?id=${s.id}`;
      const score = s.score_overall || 0;
      const tone = score >= 0.9 ? 'success' : score >= 0.75 ? 'info' : 'warn';
      a.className += ' tone-' + tone;
      a.innerHTML = `
        <span class="solved-dot" aria-hidden="true"></span>
        <span class="solved-name">${escHtml(s.challenge_title || 'Challenge #' + s.challenge_id)}</span>
        <span class="solved-score">${fmt(score)}</span>
      `;
      solvedList.appendChild(a);
    });
  }

  // --- Filter history buttons ---
  window._allHistorySubs = subs;

  // Wire filter buttons now that subs data is available
  const filterAll = document.getElementById('filterAll');
  const filterSolved = document.getElementById('filterSolved');
  if (filterAll) filterAll.addEventListener('click', function () { filterHistory('all', this); });
  if (filterSolved) filterSolved.addEventListener('click', function () { filterHistory('solved', this); });

  // Wire edit/sign-out buttons
  if (editBtn) editBtn.addEventListener('click', editProfile);
  if (signOutBtn) signOutBtn.addEventListener('click', () => PromptCodeAPI.logout());

  // Nav logout link
  const navLogoutLink = document.getElementById('navLogoutLink');
  if (navLogoutLink) navLogoutLink.addEventListener('click', () => PromptCodeAPI.logout());

  // Hamburger menu
  const hamburger = document.querySelector('.hamburger');
  if (hamburger) {
    hamburger.addEventListener('click', function () {
      const nl = this.closest('nav').querySelector('.nav-links');
      if (nl) nl.classList.toggle('mobile-open');
    });
  }
});
