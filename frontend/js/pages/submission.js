  let _reportCache = null;
  let _currentChallengeId = null;

  function fmtNum(n) { return n == null ? '—' : n.toLocaleString(); }
  function fmtScore(n) { return n == null ? '—' : n.toFixed(2); }
  function fmtCost(n) { return n == null ? '—' : '$' + n.toFixed(4); }
  function fmtMs(n) { return n == null ? '—' : fmtNum(Math.round(n)) + 'ms'; }
  function asNumber(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }
  function labelize(v) { return String(v == null ? 'unknown' : v).replace(/_/g, ' '); }

  function scoreClass(v) {
    if (v == null) return '';
    if (v >= 0.8) return 'good';
    if (v >= 0.65) return 'warn';
    return 'bad';
  }

  function scoreTone(cls) {
    if (cls === 'good') return 'success';
    if (cls === 'warn') return 'warn';
    return 'danger';
  }

  function replayAnimation(el) {
    el.style.animation = 'none';
    void el.offsetWidth;
    el.style.animation = '';
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '—';
    const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + ' minutes ago';
    if (diff < 86400) return Math.floor(diff / 3600) + ' hours ago';
    return Math.floor(diff / 86400) + ' days ago';
  }

  function updateScoreCell(id, value) {
    const cell = document.getElementById(id);
    if (!cell) return;
    const cls = scoreClass(value);
    cell.className = 'stat score-cell' + (cls ? ' ' + cls : '');
    const valEl = cell.querySelector('.sc-val');
    valEl.textContent = fmtScore(value);
    valEl.className = 'sc-val' + (cls ? ' ' + cls : '');
    const fill = cell.querySelector('.pc-bar-fill');
    const pct = value != null ? Math.max(0, Math.min(100, value * 100)) : 0;
    fill.style.setProperty('--v', pct + '%');
    fill.parentElement.dataset.tone = scoreTone(cls);
    fill.parentElement.setAttribute('aria-valuenow', String(Math.round(pct)));
    replayAnimation(fill);
  }

  function updateHeroRing(overall) {
    const el = document.getElementById('heroScore');
    const sub = document.getElementById('heroScoreSub');
    const ring = document.getElementById('heroRing');
    if (el) el.textContent = fmtScore(overall);
    if (sub) sub.textContent = 'overall';
    if (ring && overall != null) {
      const cls = scoreClass(overall);
      ring.style.setProperty('--pc-score', Math.round(Math.max(0, Math.min(1, overall)) * 100));
      ring.style.setProperty('--pc-ring-color', `var(--pc-${scoreTone(cls)})`);
      replayAnimation(ring);
    }
  }

  function buildPassRow(run, idx) {
    const type = (run.run_type || 'clean').toLowerCase();
    let badgeTone = 'success';
    if (type.includes('perturb')) badgeTone = 'warn';
    else if (type.includes('advers')) badgeTone = 'danger';

    const sc = run.accuracy;
    const scCls = scoreClass(sc);
    const passed = run.status === 'passed' || run.status === 'pass';

    return `<tr>
      <td class="mono faint">${idx + 1}</td>
      <td><span class="tag" data-tone="${badgeTone}">${PCUI.esc(type)}</span></td>
      <td class="num pass-score${scCls ? ' ' + scCls : ''}">${fmtScore(sc)}</td>
      <td class="num">${fmtNum(run.tokens_total)}</td>
      <td class="num">${fmtCost(run.cost_usd)}</td>
      <td class="num">${fmtMs(run.latency_ms)}</td>
      <td>${passed
        ? '<span class="tag" data-tone="success">pass</span>'
        : '<span class="tag" data-tone="warn">' + PCUI.esc(run.status || 'partial') + '</span>'
      }</td>
    </tr>`;
  }

  function renderJsonReport(report) {
    const el = document.getElementById('jsonReport');
    if (!el) return;
    const fields = {
      accuracy: report.accuracy,
      efficiency: report.efficiency,
      reliability: report.reliability,
      orchestration: report.orchestration,
      overall: report.overall,
      cost_usd: report.cost_usd,
      latency_ms: report.latency_ms,
      llm_calls: report.llm_calls,
    };
    function valColor(k, v) {
      if (typeof v === 'number' && v <= 1) {
        const cls = scoreClass(v);
        if (cls === 'good') return 'jv-g';
        if (cls === 'warn') return 'jv-w';
        return 'jv-r';
      }
      return 'jv-b';
    }
    let html = '{\n';
    const keys = Object.keys(fields);
    keys.forEach((k, i) => {
      const v = fields[k];
      const disp = v != null ? (typeof v === 'number' && v <= 1 ? v.toFixed(2) : v) : 'null';
      html += `&nbsp;&nbsp;<span class="jk">"${k}"</span>: <span class="${valColor(k, v)}">${disp}</span>${i < keys.length - 1 ? ',' : ''}\n`;
    });
    html += '}';
    el.innerHTML = html.replace(/\n/g, '<br>');
  }

  function renderSDKUsage(report, sub) {
    const el = document.getElementById('sdkUsageBody');
    if (!el) return;
    const calls = report.llm_calls || 0;
    const latMs = report.latency_ms || 0;
    const runs = report.runs || [];
    let totalTokens = 0;
    runs.forEach(r => { totalTokens += (r.tokens_total || 0); });
    if (totalTokens === 0 && report.llm_calls) totalTokens = report.llm_calls * 400;
    const usage = report.usage_breakdown || {};
    const usageTotals = usage.totals || {};
    const models = Array.isArray(usage.models) ? usage.models : [];
    const topModel = models.length ? models[0] : null;
    const credibility = report.credibility || {};

    const rows = [
      ['total calls', fmtNum(calls), calls > 3 ? 'wn' : ''],
      ['total tokens', fmtNum(totalTokens), totalTokens > 2000 ? 'wn' : ''],
      ['avg call latency', fmtMs(calls > 0 ? latMs / calls : 0), ''],
      ['total latency', fmtMs(latMs), ''],
      ['total cost', fmtCost(report.cost_usd), ''],
    ];
    const leverage = report.ai_leverage || {};
    if (leverage.reliance_calibration_score != null) {
      rows.push(['reliance calibration', fmtScore(Number(leverage.reliance_calibration_score)), Number(leverage.reliance_calibration_score) >= 0.65 ? 'ac' : 'wn']);
    }
    if (leverage.leverage_gain != null) {
      const gain = Number(leverage.leverage_gain);
      const sign = gain > 0 ? '+' : '';
      rows.push(['leverage gain', `${sign}${gain.toFixed(2)}`, gain > 0 ? 'ac' : (gain < 0 ? 'dn' : 'wn')]);
    }
    if (credibility.score != null) {
      rows.push(['score credibility', fmtScore(Number(credibility.score)), Number(credibility.score) >= 0.75 ? 'ac' : 'wn']);
    }
    if (credibility.band) {
      rows.push(['credibility band', String(credibility.band), String(credibility.band) === 'high' ? 'ac' : 'wn']);
    }
    if (topModel && topModel.model) {
      rows.push(['top model', `${String(topModel.model)} (${fmtNum(topModel.calls || 0)} calls)`, '']);
    }
    if (usageTotals.avg_tokens_per_call != null) {
      rows.push(['avg tokens/call', fmtNum(usageTotals.avg_tokens_per_call), Number(usageTotals.avg_tokens_per_call) > 1200 ? 'wn' : '']);
    }
    el.innerHTML = rows.map(([k, v, cls]) =>
      `<div class="metric-row"><span class="mk">${k}</span><span class="mv${cls ? ' ' + cls : ''}">${v}</span></div>`
    ).join('');
  }

  function extractScoreCapEvents(report) {
    const trail = Array.isArray(report.audit_trail) ? report.audit_trail : [];
    return trail
      .filter(e => e && e.event === 'score_cap_applied' && e.details && typeof e.details === 'object')
      .map(e => e.details);
  }

  function getCoreIntegritySignals(report) {
    const pqDetails = report.prompt_quality_details || {};
    const evalCfg = report.evaluation_config || {};
    const credibility = report.credibility || {};
    const credSignals = credibility.signals || {};
    const ci = report.confidence_intervals || {};
    const runAccuracyCI = ci.run_accuracy || {};
    const calibration = report.calibration_details || {};
    const leverageSignals = (report.ai_leverage || {}).signals || {};
    const counterfactual = leverageSignals.counterfactual || {};
    const aggregate = counterfactual.aggregate || {};
    const capEvents = extractScoreCapEvents(report);
    const capReasons = [];
    capEvents.forEach((event) => {
      const reason = String(event.reason || '').trim();
      if (reason && !capReasons.includes(reason)) capReasons.push(reason);
    });

    return {
      evaluationMode: String(evalCfg.mode || 'sandbox'),
      promptJudgeMethod: String(credSignals.prompt_judge_method || pqDetails.method || 'unknown'),
      judgeModel: String(pqDetails.judge_model || evalCfg.judge_model || 'n/a'),
      calibrationSamples: asNumber(credSignals.calibration_samples ?? calibration.samples),
      runAccuracyCiHalfWidth: asNumber(runAccuracyCI.half_width ?? credSignals.run_accuracy_ci_half_width),
      runTypeCoverage: asNumber(credSignals.run_type_coverage),
      runCount: asNumber(credSignals.run_count ?? evalCfg.run_count),
      hiddenSetCount: asNumber(credSignals.hidden_set_count ?? evalCfg.hidden_set_count),
      counterfactualStatus: String(credSignals.counterfactual_status || counterfactual.status || 'unknown'),
      aggregateMethod: aggregate.method ? String(aggregate.method) : '',
      selectedStrategyId: aggregate.selected_strategy_id ? String(aggregate.selected_strategy_id) : '',
      variantsOk: asNumber(aggregate.variants_ok),
      variantsTotal: asNumber(aggregate.variants_total),
      capReasons,
    };
  }

  function renderCoreIntegrity(report) {
    const card = document.getElementById('integrityCard');
    const body = document.getElementById('integrityBody');
    if (!card || !body) return;

    const integrity = getCoreIntegritySignals(report);
    const rows = [
      ['evaluation mode', labelize(integrity.evaluationMode), integrity.evaluationMode === 'sandbox' ? 'ac' : 'wn'],
      ['judge mode', labelize(integrity.promptJudgeMethod), integrity.promptJudgeMethod === 'llm_judge' ? 'ac' : 'wn'],
      ['judge model', integrity.judgeModel || 'n/a', ''],
    ];

    if (integrity.calibrationSamples != null) {
      rows.push([
        'calibration samples',
        fmtNum(integrity.calibrationSamples),
        integrity.calibrationSamples >= 6 ? 'ac' : 'wn',
      ]);
    }
    if (integrity.runAccuracyCiHalfWidth != null) {
      rows.push([
        'run accuracy ci',
        `±${integrity.runAccuracyCiHalfWidth.toFixed(2)}`,
        integrity.runAccuracyCiHalfWidth < 0.15 ? 'ac' : 'wn',
      ]);
    }
    if (integrity.runTypeCoverage != null) {
      rows.push([
        'run-type coverage',
        `${Math.round(integrity.runTypeCoverage * 100)}%`,
        integrity.runTypeCoverage >= 0.99 ? 'ac' : (integrity.runTypeCoverage >= 0.67 ? 'wn' : 'dn'),
      ]);
    }
    if (integrity.runCount != null) {
      rows.push(['run count', fmtNum(integrity.runCount), integrity.runCount >= 8 ? 'ac' : 'wn']);
    }
    if (integrity.hiddenSetCount != null) {
      rows.push(['hidden-set runs', fmtNum(integrity.hiddenSetCount), integrity.hiddenSetCount > 0 ? 'ac' : 'wn']);
    }
    rows.push([
      'counterfactual status',
      labelize(integrity.counterfactualStatus),
      integrity.counterfactualStatus === 'ok' ? 'ac' : 'wn',
    ]);
    if (integrity.aggregateMethod) {
      const ok = integrity.variantsOk != null ? integrity.variantsOk : 0;
      const total = integrity.variantsTotal != null ? integrity.variantsTotal : 0;
      const summary = total > 0
        ? `${labelize(integrity.aggregateMethod)} (${fmtNum(ok)}/${fmtNum(total)} ok)`
        : labelize(integrity.aggregateMethod);
      rows.push(['baseline aggregate', summary, ok > 0 ? 'ac' : 'wn']);
    }
    if (integrity.selectedStrategyId) {
      rows.push(['selected baseline', integrity.selectedStrategyId, '']);
    }
    if (integrity.capReasons.length) {
      rows.push(['confidence caps', integrity.capReasons.map(labelize).join(', '), 'dn']);
    } else {
      rows.push(['confidence caps', 'none', 'ac']);
    }

    body.innerHTML = rows.map(([k, v, cls]) =>
      `<div class="metric-row"><span class="mk">${k}</span><span class="mv${cls ? ' ' + cls : ''}">${v}</span></div>`
    ).join('');
    card.style.display = '';
  }

  function _cmpClass(you, top, higherBetter = true) {
    if (you == null || top == null) return '';
    if (higherBetter) return you >= top ? 'ac' : 'wn';
    return you <= top ? 'ac' : 'wn';
  }

  function _setCmpCell(id, value, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'mv' + (cls ? ' ' + cls : '');
    el.textContent = value;
  }

  async function renderTopComparison(challengeId, report) {
    try {
      const entries = await PromptCodeAPI.getLeaderboard(challengeId, 1);
      const top = Array.isArray(entries) ? entries[0] : null;
      if (!top) return;

      const youOverall = report.overall;
      const topOverall = top.score_overall;
      _setCmpCell('cmpYouOverall', fmtScore(youOverall), _cmpClass(youOverall, topOverall, true));
      _setCmpCell('cmpTopOverall', fmtScore(topOverall), 'ac');

      const youAccuracy = report.accuracy;
      const topAccuracy = top.score_accuracy;
      _setCmpCell('cmpYouAccuracy', fmtScore(youAccuracy), _cmpClass(youAccuracy, topAccuracy, true));
      _setCmpCell('cmpTopAccuracy', fmtScore(topAccuracy), 'ac');

      const youCalls = Number(report.llm_calls || 0);
      const topCalls = Number(top.total_llm_calls || 0);
      _setCmpCell('cmpYouCalls', fmtNum(youCalls), _cmpClass(youCalls, topCalls, false));
      _setCmpCell('cmpTopCalls', fmtNum(topCalls), 'ac');

      const youCost = Number(report.cost_usd || 0);
      const topCost = Number(top.total_cost_usd || 0);
      _setCmpCell('cmpYouCost', fmtCost(youCost), _cmpClass(youCost, topCost, false));
      _setCmpCell('cmpTopCost', fmtCost(topCost), 'ac');

      const youRel = Number(report.reliability || 0);
      const topRel = Number(top.score_reliability || 0);
      _setCmpCell('cmpYouRel', fmtScore(youRel), _cmpClass(youRel, topRel, true));
      _setCmpCell('cmpTopRel', fmtScore(topRel), 'ac');
    } catch (_) {
      // Keep default placeholders if leaderboard is unavailable.
    }
  }

  async function updateHeroRank(challengeId, submissionId) {
    const heroRank = document.getElementById('heroRank');
    if (!heroRank || !challengeId || !submissionId) return;
    heroRank.textContent = '—';
    try {
      const entries = await PromptCodeAPI.getLeaderboard(challengeId, 100);
      const list = Array.isArray(entries) ? entries : (entries.entries || entries.leaderboard || []);
      const match = list.find(entry => String(entry.submission_id) === String(submissionId));
      if (match && match.rank != null) {
        heroRank.textContent = `#${match.rank}`;
      }
    } catch (e) {
      PromptCodeAPI.debugLog('Rank load failed:', e.message);
    }
  }

  async function loadReport(submissionId, sub) {
    try {
      const report = await PromptCodeAPI.getSubmissionReport(submissionId);
      _reportCache = report;

      updateHeroRing(report.overall);
      updateScoreCell('cell-accuracy', report.accuracy);
      updateScoreCell('cell-efficiency', report.efficiency);
      updateScoreCell('cell-reliability', report.reliability);
      updateScoreCell('cell-orchestration', report.orchestration);

      // Hero meta
      const runs = report.runs || [];
      const passedCount = runs.filter(r => r.status === 'passed' || r.status === 'pass').length;
      const pill = document.getElementById('heroPassPill');
      const countEl = document.getElementById('heroPassCount');
      if (countEl) countEl.textContent = `${passedCount} / ${runs.length} passes`;
      if (pill) {
        pill.dataset.tone = passedCount === runs.length ? 'success' : 'danger';
      }
      const latEl = document.getElementById('heroLatency');
      if (latEl) latEl.textContent = fmtMs(report.latency_ms) + ' total';
      const timeEl = document.getElementById('heroSubmittedTime');
      if (timeEl && sub) timeEl.textContent = 'submitted ' + timeAgo(sub.created_at);
      const heroSub = document.getElementById('heroScoreSub');
      if (heroSub) {
        heroSub.textContent = 'overall';
      }

      // Passes table
      const tbody = document.getElementById('passesBody');
      const countLabel = document.getElementById('passesCount');
      if (tbody) {
        if (runs.length) {
          tbody.innerHTML = runs.map((r, i) => buildPassRow(r, i)).join('');
        } else {
          tbody.innerHTML = '<tr><td colspan="7" class="cell-empty">No evaluation runs found</td></tr>';
        }
      }
      if (countLabel) {
        countLabel.textContent = `${passedCount} / ${runs.length} completed`;
        countLabel.dataset.tone = passedCount === runs.length ? 'success' : 'warn';
      }

      // Feedback card
      const feedbackCard = document.getElementById('feedbackCard');
      const feedbackTitle = document.getElementById('feedbackTitle');
      const feedbackBody = document.getElementById('feedbackBody');
      if (report.feedback) {
        feedbackCard.style.display = '';
        if (feedbackTitle) feedbackTitle.textContent = 'Feedback';
        feedbackBody.textContent = String(report.feedback);
      } else {
        feedbackCard.style.display = 'none';
      }

      // JSON report
      renderJsonReport(report);

      // SDK usage
      renderSDKUsage(report, sub);
      renderCoreIntegrity(report);
      await renderTopComparison(sub.challenge_id, report);
      await updateHeroRank(sub.challenge_id, submissionId);

    } catch (e) {
      PromptCodeAPI.debugLog('Report not yet available:', e.message);
      document.getElementById('heroScore').textContent = '—';
      document.getElementById('heroScoreSub').textContent = 'finalizing';
    }
  }

  async function pollStatus(submissionId, sub) {
    const heroScore = document.getElementById('heroScore');
    const heroSub = document.getElementById('heroScoreSub');
    if (heroScore) heroScore.textContent = '...';
    if (heroSub) heroSub.textContent = 'evaluating';

    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const status = await PromptCodeAPI.getSubmissionStatus(submissionId);
        if (status.status === 'completed') {
          if (heroSub) heroSub.textContent = 'overall';
          await loadReport(submissionId, sub);
          return;
        } else if (status.status === 'failed') {
          if (heroScore) heroScore.textContent = '✗';
          if (heroSub) heroSub.textContent = 'failed';
          return;
        }
        if (heroSub) heroSub.textContent = status.status;
      } catch (e) {
        PromptCodeAPI.debugLog('Polling error:', e.message);
      }
    }
    if (heroSub) heroSub.textContent = 'timeout';
  }

  document.addEventListener('DOMContentLoaded', async () => {
    PromptCodeAPI.updateNavAuth();
    const params = new URLSearchParams(window.location.search);
    const submissionId = params.get('id');
    if (!submissionId) {
      showReportEmpty('No submission selected', 'Open a submission from your prompt profile, or submit a solution to a challenge to generate a report.');
      return;
    }
    const loading = document.getElementById('passesLoading');
    if (loading) loading.innerHTML = PCUI.skeletonRows(3);

    try {
      const sub = await PromptCodeAPI.getSubmission(submissionId);
      _currentChallengeId = sub.challenge_id;
      const challengeUrl = `/challenge.html?id=${sub.challenge_id}`;
      document.getElementById('backToChallenge').href = challengeUrl;
      document.getElementById('breadcrumbChallenge').href = challengeUrl;
      document.getElementById('improveBtn').href = challengeUrl;
      document.getElementById('improveBtn2').href = challengeUrl;
      document.getElementById('breadcrumbSubmission').textContent = `submission #${sub.id}`;
      document.getElementById('heroChallengeLine').textContent = `RUN #${sub.id}`;

      // Fetch challenge title for breadcrumb
      try {
        const challenge = await PromptCodeAPI.getChallenge(sub.challenge_id);
        const title = challenge.title || 'Challenge';
        document.getElementById('breadcrumbChallenge').textContent = title;
        document.getElementById('heroChallengeLine').textContent = `${title.toUpperCase()} · RUN #${sub.id}`;
        if (challenge.difficulty) {
          const diffEl = document.getElementById('heroDiffBadge');
          const d = challenge.difficulty.toLowerCase();
          const tone = d === 'easy' ? 'success' : d === 'hard' ? 'danger' : 'warn';
          if (diffEl) diffEl.innerHTML = `<span class="tag" data-tone="${tone}">${PCUI.esc(d)}</span>`;
        }
      } catch (_) {}

      if (sub.status === 'completed') {
        await loadReport(submissionId, sub);
      } else if (sub.status === 'pending' || sub.status === 'running') {
        pollStatus(submissionId, sub);
      } else if (sub.status === 'failed') {
        document.getElementById('heroScore').textContent = '✗';
        document.getElementById('heroScoreSub').textContent = 'failed';
        document.getElementById('passesBody').innerHTML = '<tr><td colspan="7" class="cell-empty" data-tone="danger">Submission failed</td></tr>';
        document.getElementById('passesCount').textContent = 'failed';
        document.getElementById('passesCount').dataset.tone = 'danger';
      }
    } catch (e) {
      document.getElementById('heroScore').textContent = '✗';
      document.getElementById('heroScoreSub').textContent = 'error';
      showReportEmpty('Submission unavailable', 'This submission could not be loaded. It may not exist, or it belongs to another account.');
      console.error('Failed to load submission:', e.message);
    }
  });

  function showReportEmpty(title, body) {
    const empty = document.getElementById('reportEmpty');
    const content = document.getElementById('reportContent');
    if (content) content.hidden = true;
    if (!empty) return;
    empty.innerHTML = PCUI.emptyState(title, body, '<div class="pc-row" style="justify-content:center"><a class="btn btn-primary btn-sm" href="/challenges.html">Browse challenges</a><a class="btn btn-ghost btn-sm" href="/profile.html">My submissions</a></div>');
    empty.hidden = false;
    const crumb = document.getElementById('breadcrumbChallenge');
    if (crumb && crumb.textContent === 'Loading…') crumb.textContent = 'Challenge';
  }

  function copyJSON() {
    if (!_reportCache) return;
    const { accuracy, efficiency, reliability, orchestration, overall, cost_usd, latency_ms, llm_calls } = _reportCache;
    const json = JSON.stringify({ accuracy, efficiency, reliability, orchestration, overall, cost_usd, latency_ms, llm_calls }, null, 2);
    navigator.clipboard.writeText(json).catch(() => {});
    const btn = document.querySelector('.pc-panel-head .btn-sm');
    if (btn) { btn.textContent = 'Copied'; setTimeout(() => btn.textContent = 'Copy', 2000); }
  }

  function shareReport(button) {
    navigator.clipboard.writeText(window.location.href).then(() => {
      button.textContent = 'Link copied';
      setTimeout(() => {
        button.textContent = 'Share report';
      }, 2000);
    }).catch(() => {});
  }
