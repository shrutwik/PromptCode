  let cmView = null;
  let currentLang = 'python';
  const chatHistory = [];
  let submitBusy = false;
  let latestChallengeSubmission = null;
  let draftSaveTimer = null;

  const LANG_META = {
    python:     { entrypoint: 'main.py',   ext: 'py' },
    javascript: { entrypoint: 'main.js',   ext: 'js' },
    typescript: { entrypoint: 'main.ts',   ext: 'ts' },
    java:       { entrypoint: 'Main.java', ext: 'java' },
    cpp:        { entrypoint: 'main.cpp',  ext: 'cpp' },
    c:          { entrypoint: 'main.c',    ext: 'c' },
    rust:       { entrypoint: 'main.rs',   ext: 'rs' },
    go:         { entrypoint: 'main.go',   ext: 'go' },
  };

  function getStarterCode(lang, title) {
    const t = title || 'this challenge';
    const starters = {
      python: `import json
from pathlib import Path

from promptcode import llm

MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are helping solve '${t}'. Return only valid JSON with no markdown."""


def _load_input():
    for candidate in (Path("/workspace/input.json"), Path("input.json")):
        if candidate.exists():
            return json.loads(candidate.read_text())
    return {}


def main():
    input_data = _load_input()
    prompt = (
        "Solve this challenge and return ONLY valid JSON. "
        "Replace this starter prompt with the exact schema and rules from the problem statement.\\n\\n"
        "Challenge title: ${t}\\n\\n"
        f"Input payload:\\n{json.dumps(input_data, indent=2)}"
    )
    raw = llm.call(
        model=MODEL,
        system=SYSTEM_PROMPT,
        prompt=prompt,
        temperature=0,
        max_tokens=1200,
        retries=1,
    )

    try:
        parsed = json.loads(raw)
        print(json.dumps(parsed))
        return
    except json.JSONDecodeError:
        repaired = llm.call(
            model=MODEL,
            system="You repair outputs into strict JSON only.",
            prompt=(
                "Convert this response into valid JSON only.\\n\\n"
                f"Original response:\\n{raw}"
            ),
            temperature=0,
            max_tokens=1200,
            retries=1,
        )
        print(repaired)


if __name__ == "__main__":
    main()
`,
      javascript: `const { llm } = require('promptcode');

async function solve(inputData) {
  // Your solution for: ${t}
  const result = await llm.call({
    model: 'gpt-4o',
    prompt: \`Process this data:\\n\\n\${inputData}\`,
    temperature: 0,
  });
  return JSON.parse(result);
}

module.exports = { solve };
`,
      typescript: `import { llm } from 'promptcode';

async function solve(inputData: string): Promise<Record<string, unknown>> {
  // Your solution for: ${t}
  const result = await llm.call({
    model: 'gpt-4o',
    prompt: \`Process this data:\\n\\n\${inputData}\`,
    temperature: 0,
  });
  return JSON.parse(result);
}

export { solve };
`,
      java: `import com.promptcode.LLM;
import org.json.JSONArray;

public class Main {
    // Your solution for: ${t}
    public static String solve(String inputData) throws Exception {
        String result = LLM.call(
            "gpt-4o",
            "Process this data:\\n\\n" + inputData,
            0.0
        );
        return result;
    }

    public static void main(String[] args) throws Exception {
        String input = new String(System.in.readAllBytes());
        System.out.println(solve(input));
    }
}
`,
      cpp: `#include <iostream>
#include <string>
#include "promptcode/llm.h"

// Your solution for: ${t}
std::string solve(const std::string& input_data) {
    auto result = llm::call(
        "gpt-4o",
        "Process this data:\\n\\n" + input_data,
        0.0
    );
    return result;
}

int main() {
    std::string input(
        (std::istreambuf_iterator<char>(std::cin)),
        std::istreambuf_iterator<char>()
    );
    std::cout << solve(input) << std::endl;
    return 0;
}
`,
      c: `#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "promptcode/llm.h"

/* Your solution for: ${t} */
char* solve(const char* input_data) {
    char prompt[4096];
    snprintf(prompt, sizeof(prompt),
        "Process this data:\\n\\n%s", input_data);
    return llm_call("gpt-4o", prompt, 0.0);
}

int main() {
    char input[65536];
    size_t len = fread(input, 1, sizeof(input)-1, stdin);
    input[len] = '\\0';
    char* result = solve(input);
    printf("%s\\n", result);
    free(result);
    return 0;
}
`,
      rust: `use promptcode::llm;
use serde_json::Value;

/// Your solution for: ${t}
fn solve(input_data: &str) -> Result<Value, Box<dyn std::error::Error>> {
    let result = llm::call(
        "gpt-4o",
        &format!("Process this data:\\n\\n{}", input_data),
        0.0,
    )?;
    let parsed: Value = serde_json::from_str(&result)?;
    Ok(parsed)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    std::io::stdin().read_line(&mut input)?;
    let output = solve(&input)?;
    println!("{}", serde_json::to_string_pretty(&output)?);
    Ok(())
}
`,
      go: `package main

import (
\t"encoding/json"
\t"fmt"
\t"io"
\t"os"

\t"promptcode/llm"
)

// Your solution for: ${t}
func solve(inputData string) (interface{}, error) {
\tresult, err := llm.Call(
\t\t"gpt-4o",
\t\tfmt.Sprintf("Process this data:\\n\\n%s", inputData),
\t\t0.0,
\t)
\tif err != nil {
\t\treturn nil, err
\t}
\tvar parsed interface{}
\terr = json.Unmarshal([]byte(result), &parsed)
\treturn parsed, err
}

func main() {
\tdata, _ := io.ReadAll(os.Stdin)
\tresult, err := solve(string(data))
\tif err != nil {
\t\tfmt.Fprintf(os.Stderr, "Error: %v\\n", err)
\t\tos.Exit(1)
\t}
\tout, _ := json.MarshalIndent(result, "", "  ")
\tfmt.Println(string(out))
}
`,
    };
    return starters[lang] || starters.python;
  }

  function getDraftStorageKey(challengeId, lang = currentLang) {
    const cid = challengeId || window._challengeId;
    if (!cid) return null;
    return `pc_draft:${cid}:${lang || 'python'}`;
  }

  function setDraftState(text) {
    const el = document.getElementById('draftState');
    if (el) el.textContent = text;
  }

  function loadSavedDraft(challengeId, lang = currentLang) {
    const key = getDraftStorageKey(challengeId, lang);
    if (!key) return '';
    try {
      return localStorage.getItem(key) || '';
    } catch (_) {
      return '';
    }
  }

  function persistDraftNow() {
    const key = getDraftStorageKey();
    if (!key) return;
    const code = getEditorCode();
    try {
      if (code && code.trim()) {
        localStorage.setItem(key, code);
        setDraftState(`saved ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
      } else {
        localStorage.removeItem(key);
        setDraftState('draft cleared');
      }
    } catch (_) {
      setDraftState('auto-save unavailable');
    }
  }

  function scheduleDraftSave() {
    setDraftState('saving…');
    clearTimeout(draftSaveTimer);
    draftSaveTimer = setTimeout(persistDraftNow, 250);
  }

  function getDraftOrStarter(lang, title) {
    return loadSavedDraft(window._challengeId, lang) || getStarterCode(lang, title);
  }

  function updateRunButton(submission) {
    const btn = document.getElementById('runBtn');
    if (!btn) return;
    if (!submission || !submission.id) {
      btn.textContent = 'Latest run';
      btn.disabled = submitBusy;
      btn.title = 'Submit a solution to create a run report';
      return;
    }
    const status = String(submission.status || '').toLowerCase();
    if (status === 'pending' || status === 'running') {
      btn.textContent = 'Open live run';
    } else {
      btn.textContent = 'Open last run';
    }
    btn.disabled = submitBusy;
    btn.title = `Open ${status || 'latest'} submission`;
  }

  function setSubmitBusyState(isBusy) {
    submitBusy = isBusy;
    const submitBtn = document.getElementById('submitBtn');
    const runBtn = document.getElementById('runBtn');
    if (submitBtn) {
      submitBtn.disabled = isBusy;
      submitBtn.textContent = isBusy ? 'Submitting…' : 'Submit';
    }
    if (runBtn) runBtn.disabled = isBusy;
  }

  let fallbackTextarea = null;

  function initFallbackTextarea() {
    const ta = document.getElementById('fallbackEditor');
    if (!ta) return null;
    if (!ta._pcInit) {
      ta._pcInit = true;
      ta.addEventListener('keydown', e => {
        if (e.key === 'Tab') {
          e.preventDefault();
          const s = ta.selectionStart, en = ta.selectionEnd;
          ta.value = ta.value.substring(0, s) + '    ' + ta.value.substring(en);
          ta.selectionStart = ta.selectionEnd = s + 4;
        }
      });
      ta.addEventListener('input', () => scheduleDraftSave());
    }
    fallbackTextarea = ta;
    return ta;
  }

  function getEditorCode() {
    if (cmView) return cmView.state.doc.toString();
    if (fallbackTextarea) return fallbackTextarea.value;
    return '';
  }

  function setEditorCode(code) {
    if (cmView) {
      cmView.dispatch({ changes: { from: 0, to: cmView.state.doc.length, insert: code } });
    } else if (fallbackTextarea) {
      fallbackTextarea.value = code;
    }
  }

  function initCodeMirror(code, lang) {
    const parent = document.getElementById('editorBody');
    if (!parent) return;

    if (!fallbackTextarea) fallbackTextarea = initFallbackTextarea();

    const oldHost = parent.querySelector('.cm-host');
    if (oldHost) oldHost.remove();
    if (cmView) { cmView.destroy(); cmView = null; }

    const CM = window._CM;
    if (!CM || window._cmFailed) {
      if (fallbackTextarea) {
        fallbackTextarea.style.display = '';
        fallbackTextarea.hidden = false;
        fallbackTextarea.value = code || '';
      }
      return;
    }

    if (fallbackTextarea) { fallbackTextarea.hidden = true; fallbackTextarea.style.display = 'none'; }

    try {
      const host = document.createElement('div');
      host.className = 'cm-host';
      host.style.cssText = 'position:absolute;inset:0;';
      parent.appendChild(host);

      const langExt = CM.langExtensions[lang] || CM.langExtensions.python;
      cmView = new CM.EditorView({
        state: CM.EditorState.create({
          doc: code || '',
          extensions: [
            CM.basicSetup,
            CM.keymap.of([CM.indentWithTab]),
            langExt(),
            CM.oneDark,
            CM.customTheme,
            CM.EditorView.updateListener.of(update => {
              if (update.docChanged) scheduleDraftSave();
            }),
          ],
        }),
        parent: host,
      });
    } catch (e) {
      console.warn('CodeMirror init failed, using textarea fallback:', e);
      const failedHost = parent.querySelector('.cm-host');
      if (failedHost) failedHost.remove();
      cmView = null;
      if (fallbackTextarea) {
        fallbackTextarea.style.display = '';
        fallbackTextarea.hidden = false;
        fallbackTextarea.value = code || '';
      }
    }
  }

  function switchLanguage(lang) {
    if (lang !== 'python') {
      showNotif('Evaluator currently supports Python submissions only');
      const sel = document.getElementById('langSelect');
      if (sel) sel.value = 'python';
      lang = 'python';
    }
    currentLang = lang;
    const meta = LANG_META[lang] || LANG_META.python;
    document.getElementById('entrypointLabel').textContent = meta.entrypoint;
    const title = window._challengeTitle || 'this challenge';
    const code = getDraftOrStarter(lang, title);
    initCodeMirror(code, lang);
  }

  function populateChallenge(c) {
    document.querySelector('.problem-title').textContent = c.title;
    document.querySelector('.challenge-crumb .name').textContent = c.title;

    const diffMap = { easy: 'success', medium: 'warn', hard: 'danger' };
    const badge = document.querySelector('.challenge-crumb .diff-badge');
    if (badge) {
      badge.dataset.tone = diffMap[c.difficulty] || 'warn';
      badge.textContent = c.difficulty.substring(0, 3);
    }
    const metaBadge = document.querySelector('.problem-meta .diff-badge');
    if (metaBadge) {
      metaBadge.dataset.tone = diffMap[c.difficulty] || 'warn';
      metaBadge.textContent = c.difficulty;
    }
    const tags = document.querySelector('.problem-meta');
    if (tags && c.tags) {
      tags.querySelectorAll('.tag:not(.diff-badge)').forEach(t => t.remove());
      c.tags.forEach(tag => {
        const span = document.createElement('span');
        span.className = 'tag';
        span.textContent = tag;
        tags.appendChild(span);
      });
    }

    if (c.description) {
      const descEl = document.getElementById('problemDescription');
      const paragraphs = c.description.split('\n\n').filter(Boolean);
      descEl.innerHTML = paragraphs.map(p => {
        if (p.trim().startsWith('from promptcode') || p.trim().startsWith('    ')) {
          return `<div class="code-snippet">${escapeHtml(p.trim())}</div>`;
        }
        const lines = p.split('\n');
        if (lines.length > 1 && /^\d+\./.test(lines[0].trim())) {
          return '<ol>' +
            lines.map(l => `<li>${escapeHtml(l.replace(/^\d+\.\s*/, ''))}</li>`).join('') +
            '</ol>';
        }
        return `<p>${escapeHtml(p)}</p>`;
      }).join('');
    }

    if (c.constraints) {
      const box = document.getElementById('problemConstraints');
      const list = document.getElementById('constraintsList');
      box.style.display = '';
      list.innerHTML = Object.entries(c.constraints)
        .map(([k, v]) => `<p class="constraint"><code>${escapeHtml(k)}</code>: ${escapeHtml(String(v))}</p>`)
        .join('');
    }

    if (c.sample_input) {
      document.getElementById('problemSampleInput').style.display = '';
      const txt = typeof c.sample_input === 'string' ? c.sample_input : JSON.stringify(c.sample_input, null, 2);
      document.getElementById('sampleInputBody').textContent = txt;
    }
    if (c.sample_output) {
      document.getElementById('problemSampleOutput').style.display = '';
      const txt = typeof c.sample_output === 'string' ? c.sample_output : JSON.stringify(c.sample_output, null, 2);
      document.getElementById('sampleOutputBody').textContent = txt;
    }

    window._challengeTitle = c.title;
    const starter = getDraftOrStarter(currentLang, c.title);
    initCodeMirror(starter, currentLang);
    setDraftState(loadSavedDraft(c.id, currentLang) ? 'draft restored' : 'auto-save ready');
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function formatMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
      `<pre><code>${code.trim()}</code></pre>`);
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/^[-•] (.+)$/gm, '<div class="md-li"><span class="md-bullet">→</span><span>$1</span></div>');
    html = html.replace(/^\d+\. (.+)$/gm, (_, item) =>
      `<div class="md-li"><span class="md-bullet">•</span><span>${item}</span></div>`);
    html = html.replace(/\n/g, '<br>');
    html = html.replace(/(<br>){3,}/g, '<br><br>');
    return html;
  }

  async function populateDrawer(challengeId) {
    try {
      const allChallenges = await PromptCodeAPI.getChallenges();
      if (!allChallenges || !allChallenges.length) return;
      const drawer = document.getElementById('drawer');
      const sections = drawer.querySelectorAll('.drawer-section');
      sections.forEach(s => s.remove());
      const divider = drawer.querySelector('.drawer-divider');
      const categories = {};
      allChallenges.forEach(c => {
        if (!categories[c.category]) categories[c.category] = [];
        categories[c.category].push(c);
      });
      const diffMap = { easy: 'success', medium: 'warn', hard: 'danger' };
      const diffLabel = { easy: 'easy', medium: 'med', hard: 'hard' };
      Object.entries(categories).forEach(([cat, items]) => {
        const section = document.createElement('div');
        section.className = 'drawer-section';
        section.innerHTML = `<div class="drawer-label">${escapeHtml(cat)}</div>`;
        items.forEach(c => {
          const isActive = c.id === challengeId;
          const a = document.createElement('a');
          a.className = 'challenge-item' + (isActive ? ' active' : '');
          a.href = `/challenge.html?id=${c.id}`;
          a.innerHTML = `<div class="${isActive ? 'solved-dot' : 'unsolved-dot'}"></div><span class="ci-name">${escapeHtml(c.title)}</span><span class="tag" data-tone="${diffMap[c.difficulty] || 'warn'}">${escapeHtml(diffLabel[c.difficulty] || c.difficulty)}</span>`;
          if (isActive) a.setAttribute('aria-current', 'page');
          section.appendChild(a);
        });
        if (divider) drawer.insertBefore(section, divider);
        else drawer.appendChild(section);
      });
    } catch (e) {
      PromptCodeAPI.debugLog('Drawer: using static data');
    }
  }

  function formatNumber(n) {
    if (n == null || isNaN(n)) return '—';
    return Number(n).toLocaleString();
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '—';
    const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  function fillColor(val) {
    if (val >= 0.8) return 'success';
    if (val >= 0.6) return 'warn';
    return 'danger';
  }

  function setScoreBar(fill, pct, tone) {
    const v = Math.max(0, Math.min(100, Number(pct) || 0));
    fill.style.setProperty('--v', v.toFixed(0) + '%');
    const track = fill.parentElement;
    if (track) {
      track.dataset.tone = tone;
      track.setAttribute('aria-valuenow', v.toFixed(0));
    }
    fill.style.animation = 'none';
    void fill.offsetWidth;
    fill.style.animation = '';
  }

  function setMetricStyle(el, val, thresholds) {
    if (!el) return;
    el.className = 'mv';
    if (val === '—' || val == null) return;
    const num = typeof val === 'number' ? val : parseFloat(String(val).replace(/[$,]/g, ''));
    if (isNaN(num)) return;
    if (thresholds && thresholds.warn != null && num >= thresholds.warn) el.classList.add('wn');
    if (thresholds && thresholds.danger != null && num >= thresholds.danger) { el.classList.remove('wn'); el.classList.add('dn'); }
  }

  function setTrackingStatus(kind, text) {
    const normalized = (kind === 'done' || kind === 'warn' || kind === 'fail') ? kind : 'idle';
    const dot = document.getElementById('trackingStatusDot');
    const label = document.getElementById('trackingStatusText');
    const tabDot = document.getElementById('trackingTabDot');
    if (dot) dot.className = `status-dot ${normalized}`;
    if (label) label.textContent = text || 'idle';
    if (tabDot) {
      tabDot.className = normalized === 'idle' ? 'tab-dot idle' : 'tab-dot accent';
    }
  }

  function setRunStatus(kind, whenText) {
    const normalized = (kind === 'done' || kind === 'warn' || kind === 'fail') ? kind : 'idle';
    const dot = document.getElementById('statusRunDot');
    const time = document.getElementById('statusLastRunTime');
    if (dot) dot.className = `status-dot ${normalized}`;
    if (time) time.textContent = whenText || '—';
  }

  function resetTrackingMetrics() {
    document.getElementById('bestScore').textContent = '—';
    document.getElementById('statusPasses').textContent = '—';
    document.getElementById('runTokens').textContent = '—';
    document.getElementById('runCost').textContent = '—';
    document.getElementById('runCalls').textContent = '—';
    document.getElementById('runLatency').textContent = '—';

    const metricIds = [
      'metricPromptTokens',
      'metricCompletionTokens',
      'metricTotalTokens',
      'metricLlmCalls',
      'metricRetries',
      'metricCost',
      'metricLatency',
    ];
    metricIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.textContent = '—';
        el.className = 'mv';
      }
    });

    const scores = [
      'Accuracy',
      'PromptQuality',
      'RuleAdherence',
      'EdgeCases',
      'Efficiency',
      'Reliability',
      'Orchestration',
      'CodeQuality',
    ];
    scores.forEach((id) => {
      const el = document.getElementById('score' + id);
      const bar = document.getElementById('bar' + id);
      if (el) el.textContent = '—';
      if (bar) setScoreBar(bar, 0, 'info');
    });
  }

  function setTrackingTips(items) {
    const container = document.getElementById('trackingTips');
    if (!container) return;
    const tips = (Array.isArray(items) ? items : [])
      .map((item) => String(item || '').trim())
      .filter(Boolean)
      .slice(0, 5);
    if (!tips.length) {
      container.innerHTML = '<div class="tip-item"><span class="tip-arrow">→</span>No guidance available yet. Submit a run to unlock targeted coaching.</div>';
      return;
    }
    container.innerHTML = tips.map((tip) =>
      `<div class="tip-item"><span class="tip-arrow">→</span>${escapeHtml(tip)}</div>`
    ).join('');
  }

  function _extractGateSignals(report) {
    const credibility = report.credibility || {};
    const signals = credibility.signals || {};
    const ci = report.confidence_intervals || {};
    const runCI = ci.run_accuracy || {};
    const pq = report.prompt_quality_details || {};
    const trail = Array.isArray(report.audit_trail) ? report.audit_trail : [];
    const capReasons = [];
    trail.forEach((event) => {
      if (event && event.event === 'score_cap_applied' && event.details && event.details.reason) {
        const reason = String(event.details.reason).trim();
        if (reason && !capReasons.includes(reason)) capReasons.push(reason);
      }
    });
    const calibrationSamplesRaw = Number(signals.calibration_samples ?? (report.calibration_details || {}).samples);
    const runCiRaw = Number(runCI.half_width ?? signals.run_accuracy_ci_half_width);
    return {
      credibilityScore: Number(credibility.score),
      promptJudgeMethod: String(signals.prompt_judge_method || pq.method || 'unknown'),
      calibrationSamples: Number.isFinite(calibrationSamplesRaw) ? calibrationSamplesRaw : null,
      runAccuracyCiHalfWidth: Number.isFinite(runCiRaw) ? runCiRaw : null,
      capReasons,
    };
  }

  function _buildTrackingTips(report) {
    const tips = [];
    const actions = Array.isArray(report.coaching_actions) ? report.coaching_actions : [];
    actions.slice(0, 3).forEach((action) => {
      const title = String(action.title || 'Action');
      const change = String(action.suggested_change || '').trim();
      tips.push(change ? `${title}: ${change}` : title);
    });

    const diagnostics = Array.isArray(report.diagnostics) ? report.diagnostics : [];
    diagnostics.slice(0, 2).forEach((diag) => {
      const msg = String(diag.message || '').trim();
      if (msg) tips.push(msg);
    });

    const gate = _extractGateSignals(report);
    if (gate.promptJudgeMethod !== 'llm_judge') {
      tips.push(`Prompt judge method is "${gate.promptJudgeMethod}". Move back to llm_judge to restore score confidence.`);
    }
    if (gate.calibrationSamples != null && gate.calibrationSamples <= 3) {
      tips.push(`Calibration samples are low (${gate.calibrationSamples}). Add stronger per-run confidence evidence.`);
    }
    if (gate.runAccuracyCiHalfWidth != null && gate.runAccuracyCiHalfWidth >= 0.15) {
      tips.push(`Run accuracy confidence interval is wide (±${gate.runAccuracyCiHalfWidth.toFixed(2)}). Reduce run-to-run variance.`);
    }
    if (gate.capReasons.length) {
      tips.push(`Confidence caps active: ${gate.capReasons.join(', ').replace(/_/g, ' ')}.`);
    }
    if (Number.isFinite(gate.credibilityScore) && gate.credibilityScore < 0.55) {
      tips.push(`Score credibility is low (${gate.credibilityScore.toFixed(2)}). Focus on reproducibility and fallback reduction.`);
    }

    const leverage = report.ai_leverage || {};
    if (leverage.leverage_gain != null && Number(leverage.leverage_gain) <= 0) {
      tips.push(`Leverage gain is ${Number(leverage.leverage_gain).toFixed(2)}. Your strategy is not beating counterfactual baseline yet.`);
    }
    return tips;
  }

  async function loadTrackingData(challengeId) {
    const currentUser = PromptCodeAPI.getUser();
    const currentUsername = currentUser ? currentUser.username : null;

    // --- Leaderboard ---
    try {
      const lb = await PromptCodeAPI.getLeaderboard(challengeId, 5);
      const entries = Array.isArray(lb) ? lb : (lb.entries || lb.results || []);
      document.getElementById('leaderboardCount').textContent = `${formatNumber(entries.length)} top entries`;

      const container = document.getElementById('trackingLeaderboard');
      const header = container.querySelector('.lb-row');
      container.innerHTML = '';
      if (header) container.appendChild(header);

      if (entries.length === 0) {
        container.insertAdjacentHTML('beforeend', '<div class="lb-empty">No entries yet</div>');
      } else {
        const rankClasses = ['gold', 'silver', 'bronze'];
        entries.forEach(entry => {
          const rank = entry.rank;
          const isMe = currentUsername && entry.username === currentUsername;
          const initials = (entry.username || '??').substring(0, 2).toLowerCase();
          const rankClass = rank <= 3 ? rankClasses[rank - 1] : '';
          const row = document.createElement('div');
          row.className = 'lb-row';
          if (isMe) {
            row.classList.add('is-me');
          }
          row.innerHTML =
            `<span class="lb-rank ${isMe ? 'you' : rankClass}">${rank}</span>` +
            `<span class="lb-user ${isMe ? 'you' : ''}"><div class="avatar ${isMe ? 'you' : ''}">${isMe ? 'me' : initials}</div>${isMe ? 'you' : escapeHtml(entry.username)}</span>` +
            `<span class="lb-score">${entry.score_overall != null ? entry.score_overall.toFixed(2) : '—'}</span>` +
            `<span class="lb-cost">${entry.total_cost_usd != null ? '$' + entry.total_cost_usd.toFixed(2) : '—'}</span>`;
          container.appendChild(row);
        });
      }
    } catch (e) {
      PromptCodeAPI.debugLog('Leaderboard load failed:', e.message);
      document.getElementById('leaderboardCount').textContent = '—';
      const container = document.getElementById('trackingLeaderboard');
      const header = container.querySelector('.lb-row');
      container.innerHTML = '';
      if (header) container.appendChild(header);
      container.insertAdjacentHTML('beforeend', '<div class="lb-empty">Unable to load</div>');
    }

    // --- User submissions (best score + SDK metrics + status) ---
    if (!PromptCodeAPI.isLoggedIn()) {
      latestChallengeSubmission = null;
      updateRunButton(null);
      resetTrackingMetrics();
      setTrackingStatus('idle', 'sign in to track');
      setRunStatus('idle', '—');
      setTrackingTips(['Sign in and submit a run to activate live coaching, score gates, and SDK telemetry.']);
      return;
    }

    try {
      const rawSubs = await PromptCodeAPI.getMySubmissions(challengeId);
      const subs = Array.isArray(rawSubs) ? rawSubs.slice() : [];
      if (!subs.length) {
        latestChallengeSubmission = null;
        updateRunButton(null);
        resetTrackingMetrics();
        setTrackingStatus('idle', 'no submissions');
        setRunStatus('idle', '—');
        setTrackingTips(['Submit your first attempt to unlock per-dimension scores, integrity checks, and guided improvements.']);
        return;
      }

      subs.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
      const latest = subs[0];
      latestChallengeSubmission = latest;
      updateRunButton(latest);
      const latestStatus = String(latest.status || '').toLowerCase();
      const completedSubs = subs.filter(s => String(s.status || '').toLowerCase() === 'completed');
      const best = completedSubs.length
        ? completedSubs.reduce((a, b) => ((a.score_overall || 0) >= (b.score_overall || 0) ? a : b))
        : null;

      if (latestStatus === 'completed') {
        setTrackingStatus('done', 'evaluated');
        setRunStatus('done', timeAgo(latest.created_at));
      } else if (latestStatus === 'running' || latestStatus === 'pending') {
        setTrackingStatus('warn', latestStatus);
        setRunStatus('warn', timeAgo(latest.created_at));
      } else if (latestStatus === 'failed') {
        setTrackingStatus('fail', 'failed');
        setRunStatus('fail', timeAgo(latest.created_at));
      } else {
        setTrackingStatus('idle', latestStatus || 'submitted');
        setRunStatus('idle', timeAgo(latest.created_at));
      }

      // Best scores
      const overall = best ? best.score_overall : null;
      document.getElementById('bestScore').textContent = overall != null ? overall.toFixed(2) : '—';

      const scores = [
        { id: 'Accuracy', key: 'score_accuracy' },
        { id: 'PromptQuality', key: 'score_prompt_quality' },
        { id: 'RuleAdherence', key: 'score_rule_adherence' },
        { id: 'EdgeCases', key: 'score_edge_cases' },
        { id: 'Efficiency', key: 'score_efficiency' },
        { id: 'Reliability', key: 'score_reliability' },
        { id: 'Orchestration', key: 'score_orchestration' },
        { id: 'CodeQuality', key: 'score_code_quality' },
      ];
      scores.forEach(({ id, key }) => {
        const val = best ? best[key] : null;
        const el = document.getElementById('score' + id);
        const bar = document.getElementById('bar' + id);
        if (el) el.textContent = val != null ? val.toFixed(2) : '—';
        if (bar && val != null) {
          setScoreBar(bar, val * 100, fillColor(val));
        } else if (bar) {
          setScoreBar(bar, 0, 'info');
        }
      });

      // Use latest completed report for SDK metrics and coaching.
      const reportSource = (latestStatus === 'completed') ? latest : completedSubs[0];
      if (!reportSource) {
        document.getElementById('statusPasses').textContent = '—';
        setTrackingTips(['Your latest run is still being evaluated. Completed-run guidance will appear here once scoring finishes.']);
        return;
      }

      try {
        const report = await PromptCodeAPI.getSubmissionReport(reportSource.id);
        const m = report.metrics || report;

        const promptTok = m.prompt_tokens;
        const completionTok = m.completion_tokens;
        const totalTok = (promptTok != null && completionTok != null) ? promptTok + completionTok : m.total_tokens;

        document.getElementById('metricPromptTokens').textContent = formatNumber(promptTok);
        document.getElementById('metricCompletionTokens').textContent = formatNumber(completionTok);

        const totalEl = document.getElementById('metricTotalTokens');
        totalEl.textContent = formatNumber(totalTok);
        setMetricStyle(totalEl, totalTok, { warn: 2000 });

        const callsEl = document.getElementById('metricLlmCalls');
        callsEl.textContent = formatNumber(m.llm_calls);
        setMetricStyle(callsEl, m.llm_calls, { warn: 4 });

        const retriesEl = document.getElementById('metricRetries');
        retriesEl.textContent = formatNumber(m.retries != null ? m.retries : m.retry_count);
        setMetricStyle(retriesEl, m.retries || m.retry_count, { danger: 1 });

        const cost = m.cost_usd != null ? m.cost_usd : m.total_cost_usd;
        document.getElementById('metricCost').textContent = cost != null ? '$' + cost.toFixed(2) : '—';

        const latency = m.latency_ms != null ? m.latency_ms : m.latency;
        document.getElementById('metricLatency').textContent = latency != null ? formatNumber(Math.round(latency)) + 'ms' : '—';

        // Run bar (reflects latest run)
        document.getElementById('runTokens').textContent = formatNumber(totalTok);
        document.getElementById('runCost').textContent = cost != null ? '$' + cost.toFixed(3) : '—';
        document.getElementById('runCalls').textContent = m.llm_calls != null ? m.llm_calls : '—';
        document.getElementById('runLatency').textContent = latency != null ? (latency / 1000).toFixed(1) + 's' : '—';

        // Passes
        const passes = m.tests_passed != null ? m.tests_passed : m.passes;
        const total = m.tests_total != null ? m.tests_total : m.total_tests;
        if (passes != null && total != null) {
          document.getElementById('statusPasses').textContent = `${passes} / ${total}`;
        } else {
          document.getElementById('statusPasses').textContent = '—';
        }
        setTrackingTips(_buildTrackingTips(m));
      } catch (re) {
        PromptCodeAPI.debugLog('Report load failed:', re.message);
        setTrackingTips(['Unable to load the latest report. Open the submission page for detailed diagnostics and retry after evaluation completes.']);
      }
    } catch (e) {
      PromptCodeAPI.debugLog('Submissions load failed:', e.message);
      latestChallengeSubmission = null;
      updateRunButton(null);
      resetTrackingMetrics();
      setTrackingStatus('fail', 'unable to load');
      setRunStatus('idle', '—');
      setTrackingTips(['Could not load submission history from the API. Check backend health and authentication state.']);
    }
  }

  async function bootEditor() {
    const params = new URLSearchParams(window.location.search);
    const challengeId = params.get('id');

    // Show starter code immediately so the editor is never blank
    const defaultCode = getStarterCode('python', 'this challenge');
    initCodeMirror(defaultCode, 'python');

    if (challengeId) {
      window._challengeId = challengeId;
      try {
        const c = await PromptCodeAPI.getChallenge(challengeId);
        populateChallenge(c);
      } catch (e) {
        PromptCodeAPI.debugLog('Challenge load failed:', e.message);
      }
      populateDrawer(challengeId);
      loadTrackingData(challengeId);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    PromptCodeAPI.updateNavAuth();
    initFallbackTextarea();

    window._cmReadyCallback = () => {
      if (window._CM && !window._cmFailed) {
        const existing = getEditorCode();
        const code = existing || getStarterCode(currentLang, window._challengeTitle || 'this challenge');
        initCodeMirror(code, currentLang);
      }
    };
    if (window._cmReady && window._CM && !window._cmFailed) {
      window._cmReadyCallback();
    }
    bootEditor();
    hydrateCoachPrefillFromUrl();
  });

  function hydrateCoachPrefillFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const coachText = params.get('coach');
    if (!coachText) return;

    const input = document.getElementById('chatInput');
    if (!input) return;
    input.value = coachText;
    switchRightTab('chat');
    showNotif('Coach action loaded. Press Enter to send.');
  }

  function switchRightTab(tab) {
    document.querySelectorAll('.right-tab').forEach(t => {
      const on = t.dataset.tab === tab;
      t.classList.toggle('active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    document.getElementById('panelTracking').classList.toggle('active', tab === 'tracking');
    document.getElementById('panelChat').classList.toggle('active', tab === 'chat');
    if (tab === 'chat') {
      const msgs = document.getElementById('chatMessages');
      msgs.scrollTop = msgs.scrollHeight;
    }
  }

  function toggleDrawer() {
    const open = document.getElementById('drawer').classList.toggle('open');
    document.getElementById('overlay').classList.toggle('open', open);
    document.getElementById('drawer').setAttribute('aria-hidden', open ? 'false' : 'true');
    document.getElementById('drawer').inert = !open;
    const btn = document.querySelector('.menu-btn');
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      const first = document.querySelector('#drawer a');
      if (first) first.focus();
    } else if (btn) {
      btn.focus();
    }
  }

  function showNotif(msg) {
    if (window.PCUI && PCUI.toast) { PCUI.toast(msg); return; }
    const n = document.getElementById('notif');
    document.getElementById('notifText').textContent = msg;
    n.classList.remove('hidden');
    clearTimeout(n._t);
    n._t = setTimeout(() => n.classList.add('hidden'), 3000);
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
  }

  let chatBusy = false;

  function handleRunAction() {
    if (!PromptCodeAPI.isLoggedIn()) {
      showNotif('Please sign in to access runs');
      setTimeout(() => window.location.href = '/login.html', 1200);
      return;
    }
    if (!latestChallengeSubmission || !latestChallengeSubmission.id) {
      showNotif('No run yet. Submit your solution to generate a report.');
      return;
    }
    window.location.href = `/submission.html?id=${latestChallengeSubmission.id}`;
  }

  async function sendMsg() {
    if (chatBusy) return;
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;

    const msgs = document.getElementById('chatMessages');

    const userMsg = document.createElement('div');
    userMsg.className = 'msg';
    userMsg.innerHTML = `<div class="msg-avatar user">me</div><div class="msg-body"><div class="msg-sender">you</div><div class="msg-text">${escapeHtml(text)}</div></div>`;
    msgs.appendChild(userMsg);
    input.value = '';

    chatHistory.push({ role: 'user', content: text });

    const typing = document.createElement('div');
    typing.className = 'msg';
    typing.id = 'typingIndicator';
    typing.innerHTML = `<div class="msg-avatar ai">✦</div><div class="msg-body"><div class="msg-sender">assistant</div><div class="msg-text is-pending">Thinking…</div></div>`;
    msgs.appendChild(typing);
    msgs.scrollTop = msgs.scrollHeight;

    chatBusy = true;
    const challengeId = window._challengeId;

    if (!challengeId) {
      typing.remove();
      const errMsg = document.createElement('div');
      errMsg.className = 'msg';
      errMsg.innerHTML = `<div class="msg-avatar ai">✦</div><div class="msg-body"><div class="msg-sender">assistant</div><div class="msg-text is-error">No challenge loaded. Open a challenge from the challenges page first.</div></div>`;
      msgs.appendChild(errMsg);
      msgs.scrollTop = msgs.scrollHeight;
      chatBusy = false;
      return;
    }

    try {
      const code = getEditorCode();
      const resp = await PromptCodeAPI.chatWithAssistant(challengeId, chatHistory, code);
      typing.remove();

      const reply = resp.reply || 'No response.';
      chatHistory.push({ role: 'assistant', content: reply });

      const aiMsg = document.createElement('div');
      aiMsg.className = 'msg';
      const formatted = formatMarkdown(reply);
      aiMsg.innerHTML = `<div class="msg-avatar ai">✦</div><div class="msg-body"><div class="msg-sender">assistant</div><div class="msg-text">${formatted}</div></div>`;
      msgs.appendChild(aiMsg);
      msgs.scrollTop = msgs.scrollHeight;
    } catch (e) {
      typing.remove();
      const errMsg = document.createElement('div');
      errMsg.className = 'msg';
      errMsg.innerHTML = `<div class="msg-avatar ai">✦</div><div class="msg-body"><div class="msg-sender">assistant</div><div class="msg-text is-error">${escapeHtml(e.message || 'Failed to get response')}</div></div>`;
      msgs.appendChild(errMsg);
      msgs.scrollTop = msgs.scrollHeight;
    } finally {
      chatBusy = false;
    }
  }

  async function handleSubmit() {
    if (submitBusy) return;
    if (!PromptCodeAPI.isLoggedIn()) {
      showNotif('Please sign in to submit');
      setTimeout(() => window.location.href = '/login.html', 1200);
      return;
    }
    const code = getEditorCode();
    const challengeId = window._challengeId;
    if (!challengeId) {
      showNotif('No challenge selected');
      return;
    }
    if (!code.trim()) {
      showNotif('Write some code first');
      return;
    }
    const entrypoint = (LANG_META[currentLang] || LANG_META.python).entrypoint;
    try {
      setSubmitBusyState(true);
      persistDraftNow();
      showNotif('Submitting...');
      const submission = await PromptCodeAPI.submitSolution(challengeId, code, entrypoint);
      latestChallengeSubmission = submission;
      updateRunButton(submission);
      showNotif('Submitted! Generating report...');
      loadTrackingData(challengeId);
      setTimeout(() => {
        window.location.href = `/submission.html?id=${submission.id}`;
      }, 1500);
    } catch (e) {
      showNotif(e.message || 'Submission failed');
    } finally {
      setSubmitBusyState(false);
    }
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('drawer').classList.contains('open')) {
      toggleDrawer();
      return;
    }
    const tab = e.target instanceof Element ? e.target.closest('.right-tab') : null;
    if (tab && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
      e.preventDefault();
      const next = tab.dataset.tab === 'chat' ? 'tracking' : 'chat';
      switchRightTab(next);
      const btn = document.querySelector(`.right-tab[data-tab="${next}"]`);
      if (btn) btn.focus();
    }
  });

  // ── Splitter drag logic ──
  (function initSplitters() {
    const workspace = document.querySelector('.workspace');
    const problemPane = document.querySelector('.problem-pane');
    const rightPane = document.getElementById('rightPane');
    const splitterLeft = document.getElementById('splitterLeft');
    const splitterRight = document.getElementById('splitterRight');

    let activeSplitter = null, startX = 0, startWidth = 0;

    function onMouseDown(e, splitter, pane, direction) {
      e.preventDefault();
      activeSplitter = { splitter, pane, direction };
      startX = e.clientX;
      startWidth = pane.getBoundingClientRect().width;
      splitter.classList.add('active');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    splitterLeft.addEventListener('mousedown', e => onMouseDown(e, splitterLeft, problemPane, 'left'));
    splitterRight.addEventListener('mousedown', e => onMouseDown(e, splitterRight, rightPane, 'right'));

    document.addEventListener('mousemove', e => {
      if (!activeSplitter) return;
      const { pane, direction } = activeSplitter;
      const delta = e.clientX - startX;
      const min = parseInt(getComputedStyle(pane).minWidth) || 200;
      const max = parseInt(getComputedStyle(pane).maxWidth) || 600;
      let newWidth;
      if (direction === 'left') {
        newWidth = Math.max(min, Math.min(max, startWidth + delta));
      } else {
        newWidth = Math.max(min, Math.min(max, startWidth - delta));
      }
      pane.style.width = newWidth + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (!activeSplitter) return;
      activeSplitter.splitter.classList.remove('active');
      activeSplitter = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    });
  })();
