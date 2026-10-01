  document.addEventListener('DOMContentLoaded', async () => {
    PromptCodeAPI.updateNavAuth();

    const loading = document.getElementById('challengeLoading');
    if (loading && window.PCUI) loading.innerHTML = PCUI.skeletonRows(6);

    const loggedIn = PromptCodeAPI.isLoggedIn();
    const user = PromptCodeAPI.getUser();

    // Kick off parallel fetches — challenges always, user data only if logged in
    const challengesP = PromptCodeAPI.getChallenges().catch(() => null);
    let profileP = Promise.resolve(null);
    let submissionsP = Promise.resolve([]);
    if (loggedIn && user) {
      profileP = PromptCodeAPI.getUserProfile(user.username).catch(() => null);
      submissionsP = PromptCodeAPI.getMySubmissions().catch(() => []);
    }

    const [challenges, profile, submissions] = await Promise.all([challengesP, profileP, submissionsP]);

    // --- Build per-challenge submission lookup ---
    // Map: challengeId -> { bestScore, status }
    const challengeStats = {};
    if (Array.isArray(submissions)) {
      for (const sub of submissions) {
        const cid = sub.challenge_id;
        if (!challengeStats[cid]) {
          challengeStats[cid] = { bestScore: null, status: 'attempted' };
        }
        const score = sub.score_overall ?? sub.overall_score ?? sub.score ?? null;
        if (score != null && (challengeStats[cid].bestScore == null || score > challengeStats[cid].bestScore)) {
          challengeStats[cid].bestScore = score;
        }
        if (sub.status === 'completed' || sub.status === 'graded') {
          challengeStats[cid].status = 'solved';
        } else if (sub.status === 'failed' && challengeStats[cid].status !== 'solved') {
          challengeStats[cid].status = 'attempted';
        }
      }
    }

    const totalChallenges = challenges ? challenges.length : 0;
    const firstChallengeId = totalChallenges ? challenges[0].id : null;
    if (firstChallengeId) {
      const target = `/challenge.html?id=${firstChallengeId}`;
      const startBtn = document.getElementById('startChallengeBtn');
      const weeklyBtn = document.getElementById('weeklyAttemptBtn');
      if (startBtn) startBtn.href = target;
      if (weeklyBtn) weeklyBtn.href = target;
    }
    const stats = profile && profile.stats ? profile.stats : null;
    const solved = stats ? (stats.challenges_solved || 0) : 0;
    const avgScore = stats ? (stats.avg_score || 0) : 0;
    const totalCost = stats ? (stats.total_cost_usd || 0) : 0;
    const totalSubmissions = stats ? (stats.total_submissions || 0) : 0;

    // --- Sidebar ---
    const el = id => document.getElementById(id);
    el('sidebarChallengeCount').textContent = totalChallenges || '—';
    if (loggedIn && stats) {
      el('sidebarSubmissionCount').textContent = totalSubmissions;
      el('sidebarUserRank').textContent = '—';
      const pct = totalChallenges > 0 ? Math.round((solved / totalChallenges) * 100) : 0;
      el('sidebarProgFill').style.setProperty('--v', pct + '%');
      el('sidebarProgFill').parentElement.setAttribute('aria-valuenow', String(pct));
      el('sidebarProgText').textContent = `${solved} / ${totalChallenges} solved` + (avgScore ? ` · avg score ${avgScore.toFixed(2)}` : '');
    }

    // --- Stats cards ---
    if (loggedIn && stats) {
      el('statSolved').textContent = solved;
      el('statAvgScore').textContent = avgScore ? avgScore.toFixed(2) : '—';
      el('statRank').textContent = '—';
      el('statCost').textContent = totalCost ? `$${totalCost.toFixed(2)}` : '$0.00';
    }

    // --- Page subtitle ---
    const cats = challenges ? [...new Set(challenges.map(c => c.category))].length : 0;
    el('pageSubtitle').textContent = totalChallenges
      ? `${totalChallenges} problems across ${cats} ${cats === 1 ? 'category' : 'categories'}. Ranked by difficulty.`
      : challenges ? 'No challenges available yet.' : 'Challenges could not be loaded.';

    // --- Challenge table ---
    const tbody = el('challengeRows');
    const esc = (s) => (window.PCUI ? PCUI.esc(s) : String(s ?? ''));
    if (challenges && challenges.length > 0) {
      tbody.innerHTML = '';

      const diffTone = { easy: 'success', medium: 'warn', hard: 'danger' };
      const diffLabel = { easy: 'easy', medium: 'med', hard: 'hard' };
      let currentCat = '';

      challenges.forEach((c, i) => {
        if (c.category !== currentCat) {
          currentCat = c.category;
          const divider = document.createElement('tr');
          divider.className = 'section-divider';
          divider.dataset.cat = currentCat;
          divider.innerHTML = `<td colspan="7">${esc(currentCat)}</td>`;
          tbody.appendChild(divider);
        }

        const cs = challengeStats[c.id];
        let scoreText = '—';
        let statusTone = 'idle';
        let statusTitle = 'Not started';
        if (cs) {
          scoreText = cs.bestScore != null ? cs.bestScore.toFixed(2) : '—';
          if (cs.status === 'solved') {
            statusTone = 'success';
            statusTitle = 'Solved';
          } else {
            statusTone = 'warn';
            statusTitle = 'Attempted';
          }
        }

        const href = `/challenge.html?id=${c.id}`;
        const row = document.createElement('tr');
        row.className = 'challenge-row';
        row.dataset.href = href;
        row.dataset.cat = c.category;
        row.dataset.diff = c.difficulty;
        row.innerHTML = `
          <td class="row-num">${String(i + 1).padStart(2, '0')}</td>
          <td class="title-cell">
            <a class="row-name" href="${href}">${esc(c.title)}</a>
            <span class="row-desc">${esc(c.company_context || c.slug)}</span>
          </td>
          <td class="row-cat col-cat">${esc(c.category)}</td>
          <td><span class="tag" data-tone="${diffTone[c.difficulty] || 'warn'}">${esc(diffLabel[c.difficulty] || c.difficulty)}</span></td>
          <td class="row-solved col-solved num">—</td>
          <td class="row-score num">${scoreText}</td>
          <td class="row-status"><span class="tag" data-tone="${statusTone}">${statusTitle}</span></td>
        `;
        tbody.appendChild(row);
      });

      el('tableFooter').textContent = `Showing ${challenges.length} challenges`;
    } else {
      tbody.innerHTML = `<tr><td colspan="7">${window.PCUI
        ? PCUI.emptyState(challenges ? 'No challenges yet' : 'Challenges unavailable', challenges ? 'New prompt challenges will appear here.' : 'Something went wrong loading challenges. Try again in a moment.', challenges ? '' : '<button type="button" class="btn btn-secondary btn-sm" data-pc-reload>Retry</button>')
        : ''}</td></tr>`;
    }

    tbody.addEventListener('click', (e) => {
      const row = e.target.closest('tr[data-href]');
      if (!row || e.target.closest('a')) return;
      window.location.href = row.dataset.href;
    });
  });

  function syncSectionDividers() {
    document.querySelectorAll('.challenge-table tr.section-divider').forEach(div => {
      let next = div.nextElementSibling;
      let visible = false;
      while (next && !next.classList.contains('section-divider')) {
        if (next.style.display !== 'none') { visible = true; break; }
        next = next.nextElementSibling;
      }
      div.style.display = visible ? '' : 'none';
    });
  }
  function setFilter(btn, val) {
    document.querySelectorAll('.filter-btn').forEach(b => {
      b.classList.remove('is-active');
      b.setAttribute('aria-pressed', 'false');
    });
    btn.classList.add('is-active');
    btn.setAttribute('aria-pressed', 'true');
    const rows = document.querySelectorAll('.challenge-row');
    rows.forEach(row => {
      if (val === 'all') { row.style.display = ''; return; }
      const cat = row.dataset.cat || '';
      const diff = row.dataset.diff || '';
      row.style.display = (cat === val || diff === val) ? '' : 'none';
    });
    syncSectionDividers();
  }
  function filterSearch(q) {
    const rows = document.querySelectorAll('.challenge-row');
    rows.forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q.toLowerCase()) ? '' : 'none';
    });
    syncSectionDividers();
  }
  function filterCat(cat) {
    document.querySelectorAll('.sidebar-link[data-click-action="filterCat"]').forEach(a => {
      const on = (a.dataset.actionArgs || '').includes(`"${cat}"`);
      a.classList.toggle('is-active', on);
      if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
    });
    const btn = document.querySelector(`.filter-btn[data-filter="${cat}"]`);
    if (btn) { btn.click(); return; }
    setFilter(document.querySelector('.filter-btn[data-filter="all"]'), cat);
    document.querySelector('.filter-btn[data-filter="all"]').classList.remove('is-active');
    document.querySelector('.filter-btn[data-filter="all"]').setAttribute('aria-pressed', 'false');
  }
