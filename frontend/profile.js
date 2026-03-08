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

function statusClass(status) {
  if (!status) return '';
  const s = status.toLowerCase();
  if (s === 'completed' || s === 'passed') return 'diff-easy';
  if (s === 'failed') return 'diff-hard';
  return 'diff-med';
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

function filterHistory(mode, btn) {
  document.querySelectorAll('.card-header .btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const subs = window._allHistorySubs || [];
  const histList = document.getElementById('historyList');
  if (!histList) return;

  const filtered = mode === 'solved'
    ? subs.filter(s => { const st = (s.status || '').toLowerCase(); return st === 'completed' || st === 'passed'; })
    : subs;

  if (filtered.length === 0) {
    histList.innerHTML = '<div style="padding:24px 14px;text-align:center;font-size:12px;color:var(--muted)">no matching submissions</div>';
    return;
  }
  histList.innerHTML = '';
  filtered.forEach(s => {
    const a = document.createElement('a');
    a.className = 'sh-row';
    a.href = `/submission.html?id=${s.id}`;
    a.style.gridTemplateColumns = '1fr 70px 70px 80px 70px';
    const growth = s.growth_score != null ? fmt(s.growth_score) : '\u2014';
    a.innerHTML = `
      <div><div class="sh-name">${escHtml(s.challenge_title || 'Challenge #' + s.challenge_id)}</div><div class="sh-desc"><span class="diff-badge ${statusClass(s.status)}">${escHtml(s.status)}</span></div></div>
      <span class="sh-score">${s.score_overall != null ? fmt(s.score_overall) : '\u2014'}</span>
      <span class="sh-val">${growth}</span>
      <span class="sh-val">${s.total_cost_usd != null ? '$' + fmt(s.total_cost_usd) : '\u2014'}</span>
      <span class="sh-time">${s.created_at ? timeAgo(s.created_at) : '\u2014'}</span>
    `;
    histList.appendChild(a);
  });
}

function editProfile() {
  const user = PromptCodeAPI.getUser();
  if (!user) return;
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px)';
  overlay.innerHTML = `
    <div style="background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:24px;width:380px;max-width:90vw">
      <div style="font-family:'Instrument Serif',serif;font-size:20px;margin-bottom:16px">edit profile</div>
      <div style="display:flex;flex-direction:column;gap:10px">
        <label style="font-size:11px;color:var(--muted)">first name
          <input id="editFirst" type="text" value="${escHtml(user.first_name || '')}" style="width:100%;margin-top:4px;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);color:var(--text);font-family:'DM Mono',monospace;font-size:12px">
        </label>
        <label style="font-size:11px;color:var(--muted)">last name
          <input id="editLast" type="text" value="${escHtml(user.last_name || '')}" style="width:100%;margin-top:4px;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);color:var(--text);font-family:'DM Mono',monospace;font-size:12px">
        </label>
        <label style="font-size:11px;color:var(--muted)">bio
          <textarea id="editBio" rows="3" style="width:100%;margin-top:4px;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);color:var(--text);font-family:'DM Mono',monospace;font-size:12px;resize:vertical">${escHtml(user.bio || '')}</textarea>
        </label>
      </div>
      <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
        <button id="editCancel" class="btn btn-ghost">cancel</button>
        <button id="editSave" class="btn btn-primary">save</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  document.getElementById('editCancel').addEventListener('click', () => overlay.remove());
  document.getElementById('editSave').addEventListener('click', async () => {
    const btn = document.getElementById('editSave');
    btn.textContent = 'saving...';
    btn.disabled = true;
    try {
      const updated = await PromptCodeAPI.updateMe({
        first_name: document.getElementById('editFirst').value,
        last_name: document.getElementById('editLast').value,
        bio: document.getElementById('editBio').value,
      });
      localStorage.setItem('pc_user', JSON.stringify(updated));
      overlay.remove();
      location.reload();
    } catch (e) {
      btn.textContent = 'error \u2014 retry';
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

  // Header placeholders from local user while API loads
  $('profileHandle').textContent = targetUsername;
  document.title = targetUsername + ' \u2014 PromptCode';

  let profile;
  try {
    profile = await PromptCodeAPI.getUserProfile(targetUsername);
  } catch (e) {
    $('profileName').textContent = 'could not load profile';
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
  document.title = (user.username || targetUsername) + ' \u2014 PromptCode';

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
    ? `solved / ${stats.total_challenges}`
    : 'solved';
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
      $(cfg.bar).style.setProperty('--w', Math.round(v * 100) + '%');
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
  const histList = $('historyList');
  if (subs.length === 0) {
    histList.innerHTML = '<div style="padding:24px 14px;text-align:center;font-size:12px;color:var(--muted)">no submissions yet</div>';
  } else {
    histList.innerHTML = '';
    subs.forEach(s => {
      const a = document.createElement('a');
      a.className = 'sh-row';
      a.href = `/submission.html?id=${s.id}`;
      a.style.gridTemplateColumns = '1fr 70px 70px 80px 70px';
      const growth = s.growth_score != null ? fmt(s.growth_score) : '\u2014';
      a.innerHTML = `
        <div><div class="sh-name">${escHtml(s.challenge_title || 'Challenge #' + s.challenge_id)}</div><div class="sh-desc"><span class="diff-badge ${statusClass(s.status)}">${escHtml(s.status)}</span></div></div>
        <span class="sh-score">${s.score_overall != null ? fmt(s.score_overall) : '\u2014'}</span>
        <span class="sh-val">${growth}</span>
        <span class="sh-val">${s.total_cost_usd != null ? '$' + fmt(s.total_cost_usd) : '\u2014'}</span>
        <span class="sh-time">${s.created_at ? timeAgo(s.created_at) : '\u2014'}</span>
      `;
      histList.appendChild(a);
    });
  }

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
    solvedList.innerHTML = '<div style="padding:18px 14px;text-align:center;font-size:12px;color:var(--muted)">no solved challenges yet</div>';
  } else {
    solvedList.innerHTML = '';
    solved.forEach(s => {
      const a = document.createElement('a');
      a.className = 'solved-item';
      a.href = `/submission.html?id=${s.id}`;
      const score = s.score_overall || 0;
      const color = score >= 0.9 ? 'var(--success)' : score >= 0.75 ? 'var(--accent)' : 'var(--warn)';
      a.innerHTML = `
        <div class="solved-dot" style="background:${color}"></div>
        <span class="solved-name">${escHtml(s.challenge_title || 'Challenge #' + s.challenge_id)}</span>
        <span class="solved-score" style="color:${color}">${fmt(score)}</span>
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
