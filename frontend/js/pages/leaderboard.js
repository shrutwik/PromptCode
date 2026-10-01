(function() {
  const $ = id => document.getElementById(id);
  const esc = s => PCUI.esc(s);
  const initials = name => (name || '??').substring(0, 2).toLowerCase();
  const fmt = (v, d = 2) => v != null ? Number(v).toFixed(d) : '—';
  const fmtCost = v => v != null ? '$' + Number(v).toFixed(2) : '—';

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
  }

  function renderPodium(entries) {
    const container = $('podium-container');
    if (!entries || entries.length === 0) {
      container.innerHTML = '';
      container.hidden = true;
      return;
    }
    container.hidden = false;
    container.innerHTML = entries.slice(0, 3).map((e, i) => {
      const pos = i + 1;
      return `<div class="pc-card lb-pod${pos === 1 ? ' is-first' : ''}">
        <span class="lb-pod-rank">#${pos}</span>
        <span class="pc-avatar" aria-hidden="true">${esc(initials(e.username))}</span>
        <div style="min-width:0">
          <div class="lb-pod-name">${esc(e.username)}</div>
          <div class="lb-pod-meta">${fmtCost(e.total_cost_usd)} cost · ${e.total_llm_calls || 0} calls</div>
        </div>
        <span class="lb-pod-score">${fmt(e.score_overall)}</span>
      </div>`;
    }).join('');
  }

  function renderTable(entries) {
    const rows = $('lb-rows');
    const footer = $('lb-footer');
    const table = $('lb-table');
    const empty = $('lb-empty');
    const currentUser = PromptCodeAPI.getUser();
    const currentUsername = currentUser ? currentUser.username : null;

    if (!entries || entries.length === 0) {
      rows.innerHTML = '';
      table.hidden = true;
      empty.hidden = false;
      footer.textContent = '';
      return;
    }
    table.hidden = false;
    empty.hidden = true;

    rows.innerHTML = entries.map(e => {
      const isYou = currentUsername && e.username === currentUsername;
      const badge = isYou
        ? '<span class="tag" data-tone="accent">You</span>'
        : (e.rank === 1 ? '<span class="tag" data-tone="success">Top 1%</span>' : '');
      const pct = Math.round((e.score_overall || 0) * 100);
      return `<tr${isYou ? ' class="is-you"' : ''}>
        <td class="num" style="text-align:left">${esc(e.rank)}</td>
        <td><div class="lb-user"><span class="pc-avatar" aria-hidden="true">${esc(initials(e.username))}</span><strong>${esc(e.username)}</strong>${badge}</div></td>
        <td class="num"><span class="lb-score">${PCUI.bar(pct, isYou ? '' : 'success')}<span>${fmt(e.score_overall)}</span></span></td>
        <td class="num">${fmt(e.score_accuracy)}</td>
        <td class="num">${fmt(e.score_efficiency)}</td>
        <td class="num">${e.total_llm_calls ?? '—'}</td>
        <td class="num">${fmtCost(e.total_cost_usd)}</td>
      </tr>`;
    }).join('');

    footer.textContent = `Showing ${entries.length} entries`;
  }

  function panel(title, body, extra) {
    return `<section class="pc-panel">
      <div class="pc-panel-head"><h2>${title}</h2>${extra || ''}</div>
      <div class="pc-panel-body">${body}</div>
    </section>`;
  }

  const attemptBtn = '<a class="btn btn-primary btn-block" href="/challenges.html">Attempt a challenge</a>';

  function renderSidebar(profile) {
    const sidebar = $('sidebar');
    if (!PromptCodeAPI.isLoggedIn()) {
      sidebar.innerHTML =
        panel('Your stats', '<div class="lb-side-empty"><a href="/login.html" class="btn btn-secondary btn-sm">Sign in</a><p>to see your stats</p></div>') +
        attemptBtn;
      return;
    }

    if (!profile) {
      sidebar.innerHTML = panel('Your stats', '<span class="pc-skeleton pc-skeleton-text"></span><span class="pc-skeleton pc-skeleton-text" style="--w:80%"></span><span class="pc-skeleton pc-skeleton-text" style="--w:60%"></span>');
      return;
    }

    const s = profile.stats || {};
    const subs = profile.recent_submissions || [];
    const effWarn = s.avg_efficiency != null && s.avg_efficiency < 0.75;
    const metric = (k, v, cls) => `<div class="lb-metric"><span>${k}</span><b${cls ? ` class="${cls}"` : ''}>${v}</b></div>`;

    const statsBody =
      metric('Challenges solved', `${s.challenges_solved ?? 0} / ${s.total_challenges ?? '—'}`) +
      metric('Avg accuracy', fmt(s.avg_accuracy)) +
      metric('Avg efficiency', fmt(s.avg_efficiency), effWarn ? 'is-warn' : '') +
      metric('Avg orchestration', fmt(s.avg_orchestration)) +
      metric('Avg reliability', fmt(s.avg_reliability)) +
      metric('Total cost', fmtCost(s.total_cost_usd)) +
      metric('Total submissions', s.total_submissions ?? 0);

    const subsBody = subs.length === 0
      ? '<p class="lb-side-empty">No submissions yet</p>'
      : subs.map(sub => `<div class="lb-sub">
          <div>${esc(sub.challenge_title || sub.challenge_id || '—')}<small>${timeAgo(sub.created_at)}</small></div>
          <b>${fmt(sub.score_overall)}</b>
        </div>`).join('');

    sidebar.innerHTML =
      panel('Your stats', statsBody, `<span class="mono">${fmt(s.avg_score)}</span>`) +
      panel('Recent submissions', subsBody) +
      attemptBtn;
  }

  async function loadLeaderboard(challengeId) {
    if (!challengeId) {
      $('lb-count').textContent = '0';
      renderPodium([]);
      renderTable([]);
      return;
    }
    try {
      const entries = await PromptCodeAPI.getLeaderboard(challengeId);
      const list = Array.isArray(entries) ? entries : (entries.entries || entries.leaderboard || []);
      $('lb-count').textContent = list.length;
      renderPodium(list);
      renderTable(list);
    } catch (err) {
      console.error('Leaderboard load failed:', err);
      $('lb-count').textContent = '0';
      renderPodium([]);
      renderTable([]);
    }
  }

  async function loadSidebar() {
    if (!PromptCodeAPI.isLoggedIn()) {
      renderSidebar(null);
      return;
    }
    renderSidebar(null);
    try {
      const user = PromptCodeAPI.getUser();
      const profile = await PromptCodeAPI.getUserProfile(user.username);
      renderSidebar(profile);
    } catch (err) {
      console.error('Profile load failed:', err);
      $('sidebar').innerHTML = panel('Your stats', '<p class="lb-side-empty">Could not load stats</p>') + attemptBtn;
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    PromptCodeAPI.updateNavAuth();

    const select = $('challenge-select');
    const params = new URLSearchParams(window.location.search);
    const requestedChallengeId = params.get('id') || params.get('challenge_id');

    try {
      const challenges = await PromptCodeAPI.getChallenges();
      const list = Array.isArray(challenges) ? challenges : (challenges.challenges || []);
      select.innerHTML = '';
      if (list.length === 0) {
        select.innerHTML = '<option value="">No challenges available</option>';
      } else {
        list.forEach((c) => {
          const opt = document.createElement('option');
          opt.value = c.id;
          opt.textContent = c.title || c.name || c.id;
          select.appendChild(opt);
        });
      }

      select.addEventListener('change', async () => {
        const nextId = select.value || '';
        const url = new URL(window.location.href);
        if (nextId) url.searchParams.set('id', nextId);
        else url.searchParams.delete('id');
        history.replaceState(null, '', url.toString());
        await loadLeaderboard(nextId);
      });

      if (list.length > 0) {
        if (requestedChallengeId && list.some(c => c.id === requestedChallengeId)) {
          select.value = requestedChallengeId;
        }
        await loadLeaderboard(select.value);
      } else {
        $('lb-count').textContent = '0';
        renderPodium([]);
        renderTable([]);
      }
    } catch (err) {
      console.error('Failed to load challenges:', err);
      select.innerHTML = '<option value="">Failed to load</option>';
      $('lb-count').textContent = '0';
      renderPodium([]);
      renderTable([]);
    }

    loadSidebar();
  });
})();
