const sources = {
 badHire: ['BLS · developer salary by industry, May 2025', 'https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm'],
 benefits: ['BLS · employer compensation, March 2026', 'https://www.bls.gov/charts/employer-costs-for-employee-compensation/costs-per-hour.htm'],
 hireCost: ['SHRM · 2025 cost-per-hire', 'https://www.shrm.org/about/press-room/shrm-releases-2025-benchmarking-reports--how-does-your-organizat'],
 wages: ['BLS · May 2025 developer wages', 'https://www.bls.gov/news.release/ocwage.t01.htm'],
 census: ['U.S. Census · 2022 SUSB firm counts', 'https://www.census.gov/data/datasets/2022/econ/susb/2022-susb.html'],
 market: ['Polaris · candidate skills assessment market', 'https://www.polarismarketresearch.com/industry-analysis/candidate-skills-assessment-market'],
 recruiting: ['SHRM · 2026 recruiting benchmarks', 'https://www.shrm.org/topics-tools/research/recruiting-benchmarking'],
 fluency: ['HackerRank · AI Fluency methodology', 'https://support.hackerrank.com/articles/1773201418-ai-usage-summary'],
 csAssess: ['CodeSignal · technical assessments', 'https://codesignal.com/technical-assessments/'],
 csPricing: ['CodeSignal · published pricing', 'https://codesignal.com/pricing/'],
 survey: ['2025 Stack Overflow Developer Survey', 'https://survey.stackoverflow.co/2025/ai'],
 hackerrank: ['HackerRank · July 2026 product release', 'https://support.hackerrank.com/articles/8142080826-july-2026-release-notes'],
 codesignal: ['CodeSignal · AI Collection announcement', 'https://codesignal.com/newsroom/press-releases/codesignal-launches-ai-skills-assessments-to-evaluate-ai-talent-at-every-level/'],
 competition: ['Good Bull Pitch · Maroon Track', 'https://mcferrin.tamu.edu/program/good-bull-pitch/'],
 reference: ['Original PromptCode deck', 'https://promptcode.figma.site/']
};
const cite = (...ids) => ids.map(id => `<a href="${sources[id][1]}" target="_blank" rel="noopener noreferrer">${sources[id][0]} ↗</a>`).join(' · ');
const heading = (label, title) => `<div class="reveal"><p class="eyebrow">${label}</p><h2>${title}</h2></div>`;
const slides = [
  {
    "title": "PromptCode",
    "section": "Introduction",
    "time": "10 sec",
    "theme": "intro",
    "html": "<div class=\"hero-layout\"><promptcode-background aria-hidden=\"true\"></promptcode-background><div class=\"hero-copy\"><h1>Prompt<em>Code</em></h1><p class=\"hero-line\">AI writes code.<br><em>You hire judgment.</em></p><a class=\"hero-link\" href=\"#2\">Explore the pitch <span>↗</span></a></div><button class=\"hero-motion\" type=\"button\" aria-pressed=\"false\">Pause background</button></div>",
    "notes": "AI writes code. You hire judgment. PromptCode shows how candidates validate outputs, handle failure, and control cost.",
    "refs": [],
    "script": "AI writes code. You hire judgment. PromptCode makes that judgment visible."
  },
  {
    "title": "The cost of the wrong hire",
    "section": "The problem",
    "time": "35 sec",
    "html": "<div class=\"split\"><div class=\"stack reveal\"><p class=\"eyebrow\">THE PROBLEM</p><h1>Who can actually<br><em>build with AI?</em></h1><p class=\"lead\">Hiring teams need evidence of how candidates validate outputs, handle failures, and control model costs.</p></div><div class=\"stack reveal delay\"><div class=\"cost-visual\"><p class=\"label\">ESTIMATED COST EXPOSURE / FAILED ENGINEERING HIRE</p><div class=\"big-number accent\" style=\"margin:22px 0\">$53K</div><p class=\"statement\">One wrong decision.<br>A cost the business carries.</p><p class=\"label\" style=\"margin-top:24px\">THREE-MONTH SCENARIO · BLS + SHRM</p></div><p class=\"lead\">Wasted work. Lost momentum.<br>Another hiring cycle.</p></div></div>",
    "notes": "A failed engineering hire can put about fifty-three thousand dollars of compensation and replacement recruiting cost at stake in just three months. PromptCode aims to expose unreliable AI work before that commitment. This is an illustrative gross cost exposure, not a surveyed average loss or demonstrated product savings. Method: software developers in computer systems design and related services earned a median $132,050 annually in May 2025 (BLS), matching our entry market. Three months salary is $33,012.50. Apply the March 2026 private-industry benefits-to-wages ratio, $14.01 / $32.60, as a broad proxy: $14,187.27 benefits. Add one replacement recruitment at SHRM 2025 nonexecutive average $5,475: $52,674.77, rounded to $53K. Three months is an assumption, not observed failed-hire tenure. The 2026 SHRM public summary says nonexecutive costs remained relatively stable but does not disclose an updated dollar average, so the documented 2025 value is retained. Gross spend is not net loss: deduct useful work delivered when estimating economic loss. Excludes original recruiting, severance, additional training, vacancy and project-delay costs; no salary premium for AI roles. Benefits and recruitment benchmarks are cross-industry proxies. PromptCode must validate hiring impact in pilots.",
    "refs": [
      "badHire",
      "benefits",
      "hireCost"
    ],
    "script": "When a candidate uses AI, a correct answer tells you only part of the story. Can they catch errors, handle messy inputs, and control costs? Hiring without that evidence is an expensive decision. A three-month failed engineering hire can put roughly fifty-three thousand dollars in compensation and replacement recruiting at stake. That is an illustrative exposure, not a universal loss. PromptCode is built around the decision that comes before it: who should we hire?"
  },
  {
    "title": "AI adoption has outpaced verification",
    "section": "Why now",
    "time": "25 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">WHY NOW</p><h2>AI is already on the team.<br><em>Judgment is the scarce skill.</em></h2></div><div class=\"split reveal delay\"><div class=\"metrics\"><div class=\"metric\"><div class=\"big-number accent\">84<span style=\"font-size:.5em\">%</span></div><p>of survey respondents use<br>or plan to use AI in development.</p></div><div class=\"metric\"><div class=\"big-number accent\">51<span style=\"font-size:.5em\">%</span></div><p>of professional developers<br>use AI tools daily.</p></div></div><div class=\"stack\"><p class=\"statement\">Generating an answer is easy.<br>Knowing when it fails is valuable.</p><p class=\"lead\">Hiring teams need evidence of how an engineer validates outputs, handles messy inputs, and controls cost.</p></div></div><p class=\"source\"><a href=\"https://survey.stackoverflow.co/2025/ai\" target=\"_blank\" rel=\"noopener noreferrer\">2025 Stack Overflow Developer Survey ↗</a> · Self-reported 2025 survey; not an estimate of all developers.</p>",
    "notes": "AI is already part of everyday engineering. In Stack Overflow’s 2025 survey, eighty-four percent of respondents used or planned to use it, and fifty-one percent of professionals used it daily. The scarce skill is judgment: knowing what to delegate, how to validate the answer, and when the model is wrong. That is the skill we want employers to see.",
    "refs": [
      "survey"
    ],
    "script": "This matters now because AI is already part of engineering. Stack Overflow found that eighty-four percent of respondents use or plan to use AI, and fifty-one percent of professional developers use it daily. Access to a capable model is increasingly common. The hiring signal is how someone uses it: what they verify, when they retry, and which tradeoffs they make. That is what our assessment measures."
  },
  {
    "title": "Measure the engineer behind the AI",
    "section": "Solution",
    "time": "30 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">THE SOLUTION</p><h2>Measure the engineer<br><em>behind the AI.</em></h2></div><p class=\"lead reveal\">PromptCode evaluates real AI workflows on <strong>quality, reliability, and cost</strong>—then shows the evidence behind the result.</p><div class=\"flow reveal delay\"><div class=\"step\"><span class=\"label\">01 / Real work</span><h3>Solve a messy task</h3><p>Structured extraction, noisy records, and imperfect inputs.</p></div><span class=\"arrow\">→</span><div class=\"step\"><span class=\"label\">02 / Observed process</span><h3>Track every AI call</h3><p>Tokens, cost, latency, retries, and model choices.</p></div><span class=\"arrow\">→</span><div class=\"step\"><span class=\"label\">03 / Decision evidence</span><h3>Stress-test the result</h3><p>Repeated runs, hidden tests, and a reviewable scorecard.</p></div></div><p class=\"statement rule reveal delay2\">We chose work samples because <span class=\"accent\">the work itself is the evidence.</span></p>",
    "notes": "PromptCode gives an engineer a realistic task, instruments their AI calls, and stress-tests the workflow. The hiring team gets a scorecard with the supporting evidence. We chose this approach because the work sample exposes the decisions that matter: validation, recovery, model selection, and cost. The current codebase contains the SDK, sandbox, and evaluation pipeline; the next step is validating the signal with employers.",
    "refs": [],
    "script": "PromptCode gives candidates a realistic AI workflow to build. We instrument their model calls, run hidden and repeated tests, and produce a scorecard covering quality, reliability, and cost. We chose work samples because those decisions show up in the work itself. The employer can inspect the evidence and use it to guide an interview. Here is what that looks like."
  },
  {
    "title": "Same clean score. Different hiring signal.",
    "section": "Product demonstration",
    "time": "40 sec",
    "html": "<div class=\"split tight\"><div class=\"stack reveal\"><p class=\"eyebrow\">PRODUCT DEMONSTRATION</p><h2>Same clean score.<br><em>Different hiring signal.</em></h2><p class=\"lead\">Both score 96% on clean inputs.<br>Reveal what happens under stress.</p><div class=\"buyer\"><p>Give the hiring manager a reason to choose—backed by observed behavior.</p></div><p class=\"caption\">Interactive illustration. Values are synthetic;<br>this does not execute a live evaluation.</p></div><div class=\"demo reveal delay\" id=\"demo\"><div class=\"demo-top\"><span>EXTRACTION CHALLENGE / SCORECARD</span><button id=\"run-demo\">Reveal evidence ↗</button></div><div class=\"demo-grid\"><div class=\"candidate\"><h3>Candidate A</h3><div class=\"result-row\"><span>Clean accuracy</span><strong>96%</strong></div><div class=\"extra\"><div class=\"result-row\"><span>Stress-test pass rate</span><strong class=\"red\">62%</strong></div><div class=\"result-row\"><span>Cost / task</span><strong class=\"red\">$0.12</strong></div><div class=\"result-row\"><span>Retries</span><strong>5</strong></div><div class=\"result-row\"><span>Review</span><strong class=\"red\">Investigate</strong></div></div></div><div class=\"candidate\"><h3>Candidate B</h3><div class=\"result-row\"><span>Clean accuracy</span><strong>96%</strong></div><div class=\"extra\"><div class=\"result-row\"><span>Stress-test pass rate</span><strong class=\"accent\">94%</strong></div><div class=\"result-row\"><span>Cost / task</span><strong class=\"accent\">$0.02</strong></div><div class=\"result-row\"><span>Retries</span><strong>1</strong></div><div class=\"result-row\"><span>Review</span><strong class=\"accent\">Stronger signal</strong></div></div></div></div><div class=\"demo-bottom\" id=\"demo-status\" aria-live=\"polite\">Look beyond the clean-test result.</div></div></div>",
    "notes": "Both candidates get ninety-six percent on the clean input. Now reveal the evidence. One breaks on noisy inputs and costs six times more per task; the other is more robust and economical. These are synthetic demonstration values, not customer outcomes. This is the experience we are selling: a hiring manager can inspect why a candidate looks stronger, rather than trusting an unexplained number.",
    "refs": [],
    "script": "These two candidates both score ninety-six percent on clean inputs. From that score alone, they look similar. Now reveal the evidence. Candidate B holds up better under stress and runs at one-sixth the cost per task. These are synthetic examples, but they show the product experience: a hiring manager can see which workflow is stronger and what to investigate before making an offer."
  },
  {
    "title": "Help the manager make the hiring decision",
    "section": "Buyer / hiring economics",
    "time": "30 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">BUYER & HIRING ECONOMICS</p><h2>Better evidence.<br><em>Before the expensive interview.</em></h2></div><div class=\"split reveal delay\"><div class=\"stack\"><div class=\"buyer\"><p class=\"label\">INITIAL BUYER</p><h3>Engineering leaders at<br>20–199-person software-services firms</h3><p>Hiring engineers to build AI-powered products and client workflows.</p></div><p class=\"statement\">Screen → inspect evidence<br>→ focused interview → human decision</p></div><div class=\"research-list\"><div><h3>Recruiting already takes time</h3><p>SHRM reports a 39-day median time-to-fill for nonexecutive roles in 2026.</p></div><div><h3>A technical screen has a cost</h3><p>10 candidates × 2 engineers × 1 hour = 20 engineer-hours, or $1,308 at the BLS median wage.</p></div><div><h3>What a $199 pilot must earn</h3><p>Save at least 3.1 engineer-hours—or provide useful new evidence about the candidates.</p></div></div></div><p class=\"source\"><a href=\"https://www.shrm.org/topics-tools/research/recruiting-benchmarking\" target=\"_blank\" rel=\"noopener noreferrer\">SHRM · 2026 recruiting benchmarks ↗</a> · <a href=\"https://www.bls.gov/news.release/ocwage.t01.htm\" target=\"_blank\" rel=\"noopener noreferrer\">BLS · May 2025 developer wages ↗</a> · Interview format and $199 price are assumptions. Time saved and hiring impact require pilot validation.</p>",
    "notes": "Our initial buyer is an engineering leader at a twenty-to-one-hundred-ninety-nine-person software-services firm. Recruiting already takes a median thirty-nine days for nonexecutive roles, according to SHRM in 2026. Consider a screen with ten candidates and two one-hour engineering interviews each: twenty hours, about thirteen hundred dollars in wage cost. At our proposed one-hundred-ninety-nine-dollar price, a pilot needs to free about three engineer-hours or supply valuable evidence. We will measure both, rather than promise an untested reduction in bad hires.",
    "refs": [
      "recruiting",
      "wages"
    ],
    "script": "Our first buyer is an engineering leader at a software-services firm with twenty to one hundred ninety-nine employees. They hire people to build AI-powered products and client workflows. We place the assessment before the expensive engineering interview. A ten-candidate screen with two engineers can consume twenty engineer-hours. A hundred-ninety-nine-dollar pilot needs to free about three hours or provide useful new evidence. That gives us a concrete buying conversation."
  },
  {
    "title": "The value of better hiring evidence",
    "section": "Potential customer impact",
    "time": "35 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">CUSTOMER IMPACT</p><h2>Better evidence.<br><em>Engineering time back.</em></h2></div><div class=\"split tight reveal delay\"><div class=\"impact-research\"><p class=\"label\">THE VERIFICATION PROBLEM / 2025 SURVEY</p><div class=\"impact-stat\"><b>66<span>%</span></b><p>Encounter AI answers that are almost correct.</p></div><div class=\"impact-stat\"><b>45<span>%</span></b><p>Report that debugging AI-generated code is more time-consuming.</p></div><p class=\"caption\">Stack Overflow · 31,476 responses to the AI-frustrations question. Self-reported experiences, not measured defect rates.</p></div><div class=\"impact-model\"><p class=\"label accent\">ILLUSTRATIVE VALUE / ONE HIRING ROUND</p><div class=\"impact-hours\">10.3<span> hours</span></div><p class=\"lead\">Potential engineering time freed per role.</p><div class=\"impact-return\"><strong>$477</strong><p>Net capacity value after a<br>proposed $199 pilot fee.</p></div><p class=\"caption\">Scenario: 10 candidates → 4 interviews, with 10 minutes of report review per candidate. Two engineers per one-hour interview.</p></div></div><p class=\"statement rule reveal delay2\">Evaluate how candidates verify AI.<br><span class=\"accent\">Focus interview time on the strongest evidence.</span></p><p class=\"source\"><a href=\"https://survey.stackoverflow.co/2025/ai\" target=\"_blank\" rel=\"noopener noreferrer\">2025 Stack Overflow Developer Survey ↗</a> · <a href=\"https://www.bls.gov/news.release/ocwage.t01.htm\" target=\"_blank\" rel=\"noopener noreferrer\">BLS · May 2025 developer wages ↗</a> · Model uses $65.38/hour. Potential capacity, not cash savings or proven product impact. Pilot must validate time saved and qualified-candidate retention.</p>",
    "notes": "Why could this matter to a customer? In Stack Overflow’s 2025 survey, sixty-six percent of respondents to the AI-frustrations question encountered almost-correct answers, and forty-five percent said debugging AI-generated code was more time-consuming. That supports testing verification judgment. Our hiring scenario considers ten candidates, four final interviews, and ten minutes of report review per candidate. With two engineers in each one-hour interview, it frees ten-point-three engineer-hours. At the BLS median wage of sixty-five dollars and thirty-eight cents per hour, that is about four hundred seventy-seven dollars of capacity value after a one-hundred-ninety-nine-dollar pilot fee. These are assumptions to validate, not achieved savings. We must preserve qualified candidates while reducing review time. Arithmetic: 20 interview-hours minus 8 interview-hours minus 100/60 report-review hours equals 10.3333 hours; times $65.38 equals $675.5933; minus $199 equals $476.5933. Excludes setup, recruiter time, benefits and candidate effort. Survey percentages are independent observations, not inputs to the ROI calculation.",
    "refs": [
      "survey",
      "wages"
    ],
    "script": "There is a real verification problem: sixty-six percent of survey respondents report nearly correct AI answers, and forty-five percent report more time-consuming debugging. Our potential value is better evidence and more focused interviews. In the scenario shown, reviewing ten reports and interviewing four finalists frees ten-point-three engineer-hours, with about four hundred seventy-seven dollars of capacity value after the pilot fee. This is a model to validate, including whether qualified candidates are retained."
  },
  {
    "title": "A sourced market with a defined first segment",
    "section": "TAM / SAM / SOM",
    "time": "35 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">RESEARCHED MARKET SIZE</p><h2>A focused first market.<br><em>Room to expand.</em></h2></div><div class=\"split reveal delay\"><div class=\"market-stack\"><div class=\"market-band\"><div><span>TAM CONTEXT / GLOBAL CATEGORY</span><p>Candidate skills assessment · Polaris, 2025</p></div><strong>$3.18B</strong></div><div class=\"market-band\"><div><span>MODELED SAM / QUALIFIED ENTRY SEGMENT</span><p>25% of 9,467 firms × proposed $12K/year</p></div><strong>$28.4M</strong></div><div class=\"market-band\"><div><span>SOM / YEAR 3 EXECUTION TARGET</span><p>250 customers × $12K annual spend</p></div><strong>$3M</strong></div></div><div class=\"stack\"><p class=\"statement\"><span class=\"accent\">9,467 firms.</span><br>Counted by the U.S. Census.</p><p class=\"market-note muted\">Computer systems design and related services. U.S. enterprises with 20–199 employees. One industry group; no cross-industry double-counting.</p><p class=\"caption\">Global category is broader than PromptCode. All 9,467 firms at $12K/year imply a $113.6M ceiling. The 25% qualification rate, price, and SOM are assumptions; buyer demand is unvalidated.</p></div></div><p class=\"source\"><a href=\"https://www.polarismarketresearch.com/industry-analysis/candidate-skills-assessment-market\" target=\"_blank\" rel=\"noopener noreferrer\">Polaris · candidate skills assessment market ↗</a> · <a href=\"https://www.census.gov/data/datasets/2022/econ/susb/2022-susb.html\" target=\"_blank\" rel=\"noopener noreferrer\">U.S. Census · 2022 SUSB firm counts ↗</a> · Census 2022 data, released 2025; 2017 NAICS 5415. Exact size-bin calculation in the research file.</p>",
    "notes": "The market now starts with external research. Polaris estimates the global candidate-skills-assessment category at three-point-one-eight billion dollars in 2025; that includes products beyond our scope. For our entry segment, Census counts nine thousand four hundred sixty-seven computer-services firms with twenty to one hundred ninety-nine employees. At twelve thousand dollars annually, the revenue ceiling is one hundred thirteen-point-six million. If only a quarter qualify as buyers, it is twenty-eight-point-four million. Our three-million ARR goal remains an execution target, not market research.",
    "refs": [
      "market",
      "census"
    ],
    "script": "The broad candidate-assessment category is estimated at three-point-one-eight billion dollars. Our first segment is more specific: Census counts nine thousand four hundred sixty-seven computer-services firms with twenty to one hundred ninety-nine employees. If a quarter qualify and pay twelve thousand dollars annually, that models a twenty-eight-point-four-million-dollar serviceable segment. Those qualification and pricing assumptions need testing. It is our starting market; team development and additional roles provide the expansion path."
  },
  {
    "title": "Our advantage is production economics",
    "section": "Competitive differentiation",
    "time": "35 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">COMPETITIVE DIFFERENTIATION</p><h2>Our advantage:<br><em>production economics.</em></h2></div><div class=\"table-wrap reveal delay\"><table class=\"comparison\"><thead><tr><th>What the hiring team learns</th><th>HackerRank</th><th>CodeSignal</th><th>PromptCode</th></tr></thead><tbody><tr><td>Can the candidate use AI?</td><td>✓ AI Fluency</td><td>✓ AI skills assessments</td><td>✓ Instrumented AI workflow</td></tr><tr><td>What is being evaluated?</td><td>Assistant conversations<br>+ IDE behavior</td><td>Role-specific skills<br>+ AI-assisted tasks</td><td>✓ Executed workflow:<br>quality + reliability + cost</td></tr><tr><td>What does the result show?</td><td>A / B / C fluency grade<br>+ supporting excerpts</td><td>Certified assessment scores<br>+ skills reports</td><td>✓ Dollars, tokens, latency,<br>retries + pass rates</td></tr><tr><td>Why choose PromptCode<br>for AI workflow roles?</td><td colspan=\"2\">Their documented AI offerings emphasize skills and collaboration.</td><td>✓ Noisy + adversarial reruns<br>✓ Gain over a naive baseline</td></tr></tbody></table></div><p class=\"statement rule\">Choose on <span class=\"accent\">what the workflow costs and survives.</span></p><p class=\"source\"><a href=\"https://support.hackerrank.com/articles/1773201418-ai-usage-summary\" target=\"_blank\" rel=\"noopener noreferrer\">HackerRank · AI Fluency methodology ↗</a> · <a href=\"https://codesignal.com/technical-assessments/\" target=\"_blank\" rel=\"noopener noreferrer\">CodeSignal · technical assessments ↗</a> · Comparison of documented approaches, not proof competitors lack other features. PromptCode capabilities reflect implementation; superior hiring outcomes remain to be validated.</p>",
    "notes": "Our distinction is production economics. HackerRank grades AI fluency from assistant conversations and IDE behavior. CodeSignal offers certified skills assessments and AI-assisted tasks. PromptCode evaluates the executed AI workflow: what it costs, how it handles noisy inputs, and how much value the engineer adds over a naive baseline. That gives a hiring manager evidence directly relevant to running an AI product. This is a focused product advantage; it is not a claim that either competitor lacks every related capability.",
    "refs": [
      "fluency",
      "csAssess"
    ],
    "script": "HackerRank and CodeSignal already assess AI skills. Our differentiation is the operational evidence from the executed workflow: cost, retries, reliability under changed inputs, and performance against a baseline. That is the evidence our initial buyer needs for AI workflow roles. We are not claiming that competitors cannot offer related features. We are testing whether this focused report earns a place in the employer’s hiring process."
  },
  {
    "title": "Employers pay for hiring confidence",
    "section": "Revenue model",
    "time": "25 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">REVENUE MODEL</p><h2>Employers pay.<br><em>Engineers build the signal.</em></h2></div><div class=\"pricing reveal delay\"><div class=\"price-col\"><span class=\"label\">ENTRY / HIRING PILOT</span><h3>Start with one role</h3><div class=\"price\">$199<span> / month</span></div><p>10 assessments included.<br>One hiring workflow.<br>Reviewable candidate reports.</p></div><div class=\"price-col featured\"><span class=\"label accent\">CORE / GROWING TEAM</span><h3>Expand across hiring</h3><div class=\"price accent\">$1,000<span> / month</span></div><p>100 assessments included.<br>Team comparison and reporting.<br>$15 per additional assessment.</p></div><div class=\"price-col\"><span class=\"label\">EXPANSION / LATER</span><h3>Recurring upskilling</h3><div class=\"price\">$49<span> / seat / month</span></div><p>Proposed team learning plan.<br>Recurring skill benchmarks.<br>Employer-funded development.</p></div></div><div class=\"highlight-line reveal delay2\"><span>Free practice attracts engineers. Paid evaluation serves employers.</span><span class=\"accent\">Land → expand → retain</span></div><p class=\"caption\">Proposed pricing, not current revenue. $15 overage applies to hiring plans. Usage limits protect evaluation economics.</p>",
    "notes": "The payer is the employer. We propose a one-hundred-ninety-nine-dollar entry plan for one role and a thousand-dollar monthly team plan. Assessments are metered so usage does not outrun revenue. Free practice helps engineers discover the platform. After proving hiring value, we can add recurring team development at forty-nine dollars per seat. Pricing and conversion are hypotheses we will test in paid pilots.",
    "refs": [],
    "script": "The employer pays. A hundred-ninety-nine dollars per month starts with ten assessments. The thousand-dollar team plan expands to a hundred assessments, with metered overages. Later, recurring skill development could add per-seat revenue. These are proposed prices. The commercial test is whether the report is useful enough for a pilot to become a renewal."
  },
  {
    "title": "Use the Aggie network to reach buyers",
    "section": "Go to market",
    "time": "30 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">GO TO MARKET</p><h2>Start at A&amp;M.<br><em>Sell to the hiring manager.</em></h2></div><div class=\"timeline reveal delay\"><div><span class=\"label accent\">DAYS 01–30 / DISCOVER</span><h3>Find urgent hiring needs</h3><p>Founder outreach to Aggie alumni, startup founders, and engineering leaders.</p></div><div><span class=\"label\">DAYS 31–60 / PILOT</span><h3>Run one real workflow</h3><p>Co-design a role-specific assessment. Compare the report with a manager’s review.</p></div><div><span class=\"label\">DAYS 61–90 / CONVERT</span><h3>Earn a paid renewal</h3><p>Convert useful pilots into subscriptions. Ask for an introduction to the next team.</p></div></div><div class=\"funnel reveal delay2\"><div><b>50</b><span>Targeted outreaches</span></div><i>→</i><div><b>15</b><span>Buyer interviews</span></div><i>→</i><div><b>5</b><span>Design partners</span></div><i>→</i><div><b class=\"accent\">3</b><span>Paid pilots</span></div></div><p class=\"caption\">90-day targets, not completed traction. Campus activity recruits users; outreach to software-services employers generates revenue. No university partnership is claimed.</p>",
    "notes": "A&M gives us a place to begin distribution, not a guaranteed customer base. We will use founder outreach to reach alumni and engineering leaders with open roles. In ninety days, the target is fifty outreaches, fifteen interviews, five design partners, and three paid pilots. Campus challenges can recruit engineers, but the sales motion goes directly to the hiring manager. We will track conversion and renewal before expanding acquisition spend.",
    "refs": [],
    "script": "We will start with founder outreach through Aggie alumni, founders, and engineering leaders. The first ninety-day funnel is fifty targeted outreaches, fifteen buyer interviews, five design partners, and three paid pilots. We will co-design one real workflow, compare the report with a manager’s judgment, and ask for a paid continuation. Those are targets, not current traction. Renewal and referrals tell us whether to expand."
  },
  {
    "title": "Grow through accounts and expansion",
    "section": "Financial model",
    "time": "35 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">FINANCIAL MODEL</p><h2>A path to <em>$3M ARR.</em><br>Built account by account.</h2></div><div class=\"split tight reveal delay\"><div><div class=\"chart\" role=\"img\" aria-label=\"Illustrative year-end ARR: Year 1 $120,000; Year 2 $720,000; Year 3 $3 million.\"><div class=\"chart-column\"><strong>$120K</strong><div class=\"chart-bar\" style=\"--height:4%\"></div></div><div class=\"chart-column\"><strong>$720K</strong><div class=\"chart-bar\" style=\"--height:24%\"></div></div><div class=\"chart-column\"><strong class=\"accent\">$3M</strong><div class=\"chart-bar\" style=\"--height:100%\"></div></div></div><div class=\"chart-labels\"><span>Y1 / 20 CUSTOMERS</span><span>Y2 / 80</span><span>Y3 / 250</span></div><p class=\"caption\" style=\"margin-top:22px\">Year-end annual contract value: $6K → $9K → $12K.<br>Illustrative targets; ARR is a run rate, not recognized revenue.</p></div><div class=\"stack\"><div class=\"unit-grid\"><div><b>$1,000</b><span>Monthly team-plan revenue</span></div><div><b>$250</b><span>Monthly variable costs*</span></div><div><b>75%</b><span>Illustrative gross margin</span></div><div><b>4 months</b><span>Payback at $3K acquisition cost</span></div></div><p class=\"caption\">*100 assessments × $2 plus $50 allocated hosting/support. Assumes full plan usage. Excludes fixed R&amp;D, sales salaries, and overhead. Cost and acquisition assumptions require pilot measurement.</p></div></div>",
    "notes": "We model twenty customers at the end of year one, eighty in year two, and two hundred fifty in year three. Annual contract value rises as accounts expand. That produces three million dollars in year-three ARR, not three million in recognized revenue. For a thousand-dollar monthly account, assumed variable costs of two hundred fifty dollars give seventy-five percent gross margin. At a three-thousand-dollar acquisition cost, payback is four months. None of this is historical performance.",
    "refs": [],
    "script": "The growth model is account by account: twenty customers, then eighty, then two hundred fifty. As account value rises, that reaches a three-million-dollar year-end ARR target in year three. At the proposed thousand-dollar monthly plan, assumed variable costs of two hundred fifty dollars imply seventy-five percent gross margin. These are planning assumptions, not financial history. We must measure compute cost, acquisition cost, and renewal before scaling spend."
  },
  {
    "title": "Expand within teams, then across roles",
    "section": "Market expansion",
    "time": "25 sec",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">MARKET EXPANSION</p><h2>One hiring workflow.<br><em>A recurring skills business.</em></h2></div><div class=\"expansion reveal delay\"><div><div class=\"large-number\">01</div><h3>Hire AI engineers</h3><p>Own a narrow, urgent decision: who can build an economical, reliable AI workflow?</p><span class=\"label\">ENTRY / TECHNICAL HIRING</span></div><div><div class=\"large-number\">02</div><h3>Develop existing teams</h3><p>Reuse the evidence to find skill gaps, measure progress, and benchmark new models.</p><span class=\"label\">EXPAND / LEARNING BUDGET</span></div><div><div class=\"large-number\">03</div><h3>Extend into new roles</h3><p>Add data and operations workflows, then distribution through talent platforms.</p><span class=\"label\">SCALE / ROLE LIBRARY + API</span></div></div><p class=\"statement rule reveal delay2\">One evaluation engine. <span class=\"accent\">More roles, teams, and distribution partners.</span></p><p class=\"caption\">Expansion roadmap. Advance only after paid retention and assessment usefulness are demonstrated. Later roles require separate validation.</p>",
    "notes": "Hiring is the entry point. Once a customer trusts the evidence, the same workflow can help develop the engineers already on the team. That makes the relationship recurring rather than tied only to open positions. Later, we can add data and operations roles and distribute through talent platforms. Each new role requires its own validation. This is how a focused product could become a scalable skills business.",
    "refs": [],
    "script": "Hiring is the first use case. Within a customer, the same assessment approach could identify skill gaps and measure development over time. Then we can add data and operations workflows and reach employers through talent-platform partners. The scaling idea is one evaluation engine reused across roles, teams, and channels. Each new role needs validation, and expansion follows paid retention."
  },
  {
    "title": "Build the benchmark employers trust",
    "section": "Defensibility",
    "time": "25 sec",
    "html": "<div class=\"split\"><div class=\"stack reveal\"><p class=\"eyebrow\">DEFENSIBILITY</p><h2>Build the benchmark<br><em>employers trust.</em></h2><p class=\"lead\">The long-term asset is a benchmark employers can explain—and keep using.</p></div><div class=\"moat-list reveal delay\"><div><b>01</b><div><h3>Reproducible evidence</h3><p>Versioned challenges, hidden tests, run manifests, and baseline comparisons.</p></div></div><div><b>02</b><div><h3>Role-specific benchmarks</h3><p>With consent, build calibrated comparisons across real workflows and candidate cohorts.</p></div></div><div><b>03</b><div><h3>Outcome validation</h3><p>Test whether scores agree with independent work reviews and later job performance.</p></div></div></div></div><p class=\"caption\">Benchmark scale and predictive validity are future goals. Human review remains part of the hiring decision.</p>",
    "notes": "Our scoring formula is not a moat by itself. The defensible asset would be a trusted benchmark built from reproducible evaluations and role-specific evidence. We need to test agreement with independent expert reviews, check consistency, and eventually study job outcomes with consent. Employers should be able to inspect the evidence and make their own decision. Predictive validity is a goal, not a claim we have already proven.",
    "refs": [],
    "script": "The lasting advantage would be a benchmark employers trust. We can build toward it through reproducible runs, role-specific comparisons, and evidence that agrees with independent work reviews. More relevant evaluations could strengthen that benchmark, with consent. That is a defensibility plan, not an established moat. The next funding should help us prove the first part: that employers find the evidence useful and will pay for it."
  },
  {
    "title": "Prove employers will pay",
    "section": "The ask",
    "time": "30 sec",
    "theme": "closing",
    "html": "<div class=\"reveal\"><p class=\"eyebrow\">GOOD BULL PITCH / MAROON TRACK</p><h1>Fund the next 90 days.<br><em>Prove employers will pay.</em></h1></div><p class=\"lead reveal delay\">Non-dilutive funding + introductions to engineering leaders.<br>Turn the product into paid, repeatable hiring workflows.</p><div class=\"columns reveal delay2\"><div><h3>45% · Product</h3><p>Role-specific challenges and clearer employer reports.</p></div><div><h3>35% · Evaluation</h3><p>Pilot compute and independent rubric calibration.</p></div><div><h3>20% · Customer discovery</h3><p>Recruit design partners and test paid conversion.</p></div></div><div class=\"rule reveal delay2\"><p class=\"statement\">90-day targets: <strong>5 design partners · 100 evaluations · 3 paid pilots</strong></p><p class=\"caption\" style=\"margin-top:14px\">Proposed allocation of any award. Monthly progress check-ins and four months of capitalization-table updates, including non-dilutive funding.</p></div>",
    "notes": "We are asking Good Bull Pitch for non-dilutive support and introductions to engineering leaders. Whatever the award size, we propose forty-five percent for product, thirty-five percent for evaluation, and twenty percent for customer discovery. In ninety days we aim for five design partners, one hundred evaluations, and three paid pilots. We will report progress monthly and maintain the required capitalization table. Help us prove that better hiring evidence can become a scalable business.",
    "refs": [
      "competition"
    ],
    "script": "We are asking Good Bull for non-dilutive support and introductions to engineering leaders. We propose forty-five percent of the award for product, thirty-five percent for evaluation, and twenty percent for customer discovery. In ninety days, the targets are five design partners, one hundred evaluations, and three paid pilots. We will report progress monthly. The goal is a repeatable paid workflow we can grow beyond campus."
  },
  {
    "title": "Hire the skill. See the proof.",
    "section": "PromptCode",
    "time": "10 sec",
    "theme": "finale",
    "html": "<div class=\"finale-lockup\"><p class=\"eyebrow reveal\">PROMPTCODE</p><h1 class=\"reveal delay\">Hire the skill.<br><em>See the proof.</em></h1><div class=\"finale-rule reveal delay2\"></div><p class=\"finale-line reveal delay2\">Hire with evidence.</p><a class=\"finale-contact reveal delay2\" href=\"mailto:shrutwik2006@gmail.com\">Shrutwik Muppa <span>↗</span> shrutwik2006@gmail.com</a></div>",
    "notes": "Hire the skill. See the proof. PromptCode helps teams hire with evidence. Thank you.",
    "refs": [],
    "script": "Hire the skill. See the proof. Thank you."
  }
];

const deck = document.querySelector('#deck');
deck.innerHTML = slides.map((slide,i)=>`<section id="slide-${i+1}" class="slide ${slide.theme||''}" aria-label="${i===0?'Landing page':`${i}. ${slide.title}`}" aria-hidden="true" inert>${i===0?slide.html:`<div class="slide-content">${slide.html}</div>`}</section>`).join('');
const sections=[...deck.children];
const dots=document.querySelector('#dots');
dots.innerHTML=slides.slice(1).map((slide,i)=>`<button class="" aria-label="Go to slide ${i+1}: ${slide.title}" data-slide="${i+1}"></button>`).join('');
let current=-1;
function show(index){
  const next=Math.max(0,Math.min(slides.length-1,Number.isFinite(index)?index:0));
  if(next===current)return;
  current=next;
  document.body.classList.toggle('on-landing',current===0);
  sections.forEach((section,i)=>{section.classList.toggle('active',i===current);section.setAttribute('aria-hidden',String(i!==current));section.inert=i!==current;if(i===current)section.scrollTop=0;});
  [...dots.children].forEach((dot,i)=>dot.setAttribute('aria-current',String(i+1===current)));
  document.querySelector('#counter').textContent=current===0?'':`${String(current).padStart(2,'0')} / ${String(slides.length-1).padStart(2,'0')}`;
  document.querySelector('#section-name').textContent=slides[current].section.toUpperCase();
  document.querySelector('#previous').disabled=current===0;
  document.querySelector('#next').disabled=current===slides.length-1;
  document.querySelector('#progress').style.width=`${current/(slides.length-1)*100}%`;
  fitSlide(sections[current]);
  history.replaceState(null,'',`#${current+1}`);
  document.title=`PromptCode · ${slides[current].title}`;
}
// Fit the complete content, including tables, inside the available slide area.
function fitSlide(section){
  const content=section.querySelector('.slide-content');
  if(!content)return;
  const style=getComputedStyle(section);
  const width=section.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight);
  const height=section.clientHeight-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom);
  if(width<=0||height<=0)return;
  content.style.width=`${width}px`;
  const naturalWidth=Math.max(width,content.scrollWidth);
  const naturalHeight=content.scrollHeight;
  const scale=Math.min(1,width/naturalWidth,height/Math.max(1,naturalHeight));
  content.style.transform=`translate(-50%,-50%) scale(${scale})`;
  // Center any intrinsically wider content (for example, a comparison table).
  content.style.marginLeft=`${-(naturalWidth-width)*scale/2}px`;
}
const fitActive=()=>{if(current>=0)fitSlide(sections[current]);};
window.addEventListener('resize',fitActive);
document.fonts?.ready.then(fitActive);
const contentResize=new ResizeObserver(fitActive);
sections.forEach(section=>{const content=section.querySelector('.slide-content');if(content)contentResize.observe(content);});
document.querySelector('#next').addEventListener('click',()=>show(current+1));
document.querySelector('#previous').addEventListener('click',()=>show(current-1));
document.querySelectorAll('[data-slide]').forEach(button=>button.addEventListener('click',()=>{show(Number(button.dataset.slide));}));
async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{document.querySelector('#announcement').textContent='Fullscreen is unavailable in this browser. Use your browser presentation or fullscreen control.';}}
document.addEventListener('keydown',event=>{
  if(event.altKey||event.ctrlKey||event.metaKey||/INPUT|TEXTAREA|SELECT/.test(event.target.tagName))return;
  if(['ArrowRight','PageDown','ArrowLeft','PageUp','Home','End'].includes(event.key)){event.preventDefault();if(['ArrowRight','PageDown'].includes(event.key))show(current+1);if(['ArrowLeft','PageUp'].includes(event.key))show(current-1);if(event.key==='Home')show(0);if(event.key==='End')show(slides.length-1);}
  if(event.code==='Space'&&!event.composedPath().some(node=>node.matches?.('button,a'))){event.preventDefault();show(current+1);}
  if(event.key.toLowerCase()==='f')fullscreen();
});
let touchStart=null;
deck.addEventListener('touchstart',event=>{if(event.composedPath().some(node=>node.matches?.('button,a,.table-wrap')))return;touchStart={x:event.changedTouches[0].screenX,y:event.changedTouches[0].screenY};},{passive:true});
deck.addEventListener('touchend',event=>{if(!touchStart)return;const dx=event.changedTouches[0].screenX-touchStart.x,dy=event.changedTouches[0].screenY-touchStart.y;touchStart=null;if(Math.abs(dx)>75&&Math.abs(dx)>Math.abs(dy)*1.5)show(current+(dx<0?1:-1));},{passive:true});
window.addEventListener('hashchange',()=>show(Number(location.hash.slice(1))-1));
show(Number(location.hash.slice(1))-1);
document.querySelector('#run-demo').addEventListener('click',event=>{
  const button=event.currentTarget,demo=document.querySelector('#demo');
  if(demo.classList.contains('revealed')){demo.classList.remove('revealed');button.textContent='Reveal evidence ↗';document.querySelector('#demo-status').textContent='Look beyond the clean-test result.';return;}
  button.disabled=true;button.textContent='Revealing…';demo.classList.add('processing');
  document.querySelector('#demo-status').textContent='Comparing illustrative stress-test results…';
  setTimeout(()=>{demo.classList.remove('processing');demo.classList.add('revealed');button.disabled=false;button.textContent='Replay ↺';document.querySelector('#demo-status').textContent='Candidate B: stronger robustness, one-sixth the cost. Synthetic example.';},900);
});
