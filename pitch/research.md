# PromptCode: market, hiring economics, and competitive research

Research checked September 9, 2026. Public sources establish benchmarks and product descriptions; they do not establish PromptCode customer traction or performance.

## Market size

**Category context:** Polaris estimates the global candidate skills assessment market at **$3.18 billion in 2025**, following $2.86 billion in 2024. This includes software and services, corporate and education use, and coding, personality, and other assessments. It is a broader category ceiling, not an independently measured PromptCode TAM. The public summary was reviewed; its paid underlying model was not audited.

Source: [Polaris Market Research](https://www.polarismarketresearch.com/industry-analysis/candidate-skills-assessment-market).

**Initial U.S. customer pool:** Census 2022 Statistics of U.S. Businesses, released in 2025, counts **9,467 firms** in computer systems design and related services with 20–199 employees. Industry is NAICS **5415 under the 2017 classification**, which the source uses even though the data year is 2022. It includes custom programming, systems design, facilities management, and related services. Not every firm builds AI workflows or has enough hiring volume to buy the proposed product.

| Enterprise employee range | Firms |
|---|---:|
| 20–24 | 1,834 |
| 25–29 | 1,267 |
| 30–34 | 910 |
| 35–39 | 738 |
| 40–49 | 1,123 |
| 50–74 | 1,504 |
| 75–99 | 833 |
| 100–149 | 841 |
| 150–199 | 417 |
| **Total** | **9,467** |

Method: select STATE=00, NAICS=5415; sum FIRM for these nine non-overlapping enterprise-size descriptions. Use firm counts, not establishment counts. Do not add software-publisher or programming-subindustry totals: firms may span industries, and subindustries would overlap this group. The data are a historical market map, not a live list of prospects.

Sources: [Census dataset page](https://www.census.gov/data/datasets/2022/econ/susb/2022-susb.html), [underlying detailed-size data](https://www2.census.gov/programs-surveys/susb/tables/2022/us_state_naics_detailedsizes_2022.txt).

**Revenue opportunity:** at a proposed $12,000 annual contract value, 9,467 firms imply a **$113,604,000 ceiling**. Qualification must be tested against AI workload, hiring frequency, budget, and willingness to pay. If 25% qualify, the conditional SAM is **$28,401,000**; 50% gives **$56,802,000**. These are sensitivity scenarios, not measured adoption. The market category estimate and these calculations are different methods and are not additive.

**SOM:** 250 paying organizations × $12,000 = **$3 million year-end ARR**. This is an execution target: 2.64% of the full Census pool, or 10.56% of a 25%-qualified pool. ARR is a run rate, not the year's recognized revenue. Counts outside the U.S. and future upskilling revenue are excluded from this entry calculation.

## What the hiring decision costs

BLS May 2025 reports software developers' median hourly wage of **$65.38**, mean hourly wage of $71.20, and mean annual wage of $148,100. The deck uses the median hourly figure consistently.

Source: [BLS May 2025 national occupation wage table](https://www.bls.gov/news.release/ocwage.t01.htm), software-developer row. The $148,100 annual figure is a **mean**, not a median.

**Updated failed-hire estimate, reviewed September 9, 2026: $53,000 gross cost exposure.** This replaces the historical 2017 $14,900 survey headline. It models a software-services developer hire that fails after three months; it is not a measured average bad-hire loss.

| Input | Value | Evidence / assumption |
|---|---:|---|
| Annual median developer salary, computer systems design and related services | $132,050 | BLS May 2025; matches our entry industry |
| Salary for three months | $33,012.50 | Assumed tenure: one quarter of annual salary |
| Benefits-to-wages ratio | 14.01 / 32.60 = 42.98% | BLS March 2026 private-industry averages; broad proxy |
| Three-month benefits estimate | $14,187.27 | Salary times benefits ratio |
| Replacement recruitment | $5,475 | SHRM 2025 nonexecutive mean, cross-role proxy |
| Total gross exposure | **$52,674.77 ≈ $53K** | Compensation plus one replacement recruitment |

Sources: [BLS industry-specific developer salary](https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm), [BLS March 2026 compensation](https://www.bls.gov/charts/employer-costs-for-employee-compensation/costs-per-hour.htm), [SHRM 2025 cost-per-hire](https://www.shrm.org/about/press-room/shrm-releases-2025-benchmarking-reports--how-does-your-organizat).

**Latest recruiting check:** [SHRM 2026 public summary](https://www.shrm.org/topics-tools/research/recruiting-benchmarking) reports relatively stable nonexecutive cost-per-hire and a 39-day median time-to-fill. Its public page does not disclose a new nonexecutive dollar mean; the model retains the explicitly published 2025 $5,475 figure rather than inventing a 2026 number. SHRM 2025 surveyed 2,371 members; metric sample sizes vary and results are unweighted.

**Interpretation:** This is money committed to an unsuccessful hire and recruiting a replacement, not necessarily wasted in full. Net economic loss must subtract useful work delivered and may add documented disruption costs. The model excludes original recruiting, severance, extra training, vacancy cost, and delayed revenue to avoid unsupported additions and double counting. Three months is a scenario assumption, not an observed detection period. Benefits are a broad private-industry proxy, not software-specific. No AI-engineer pay premium or PromptCode savings is asserted. A six-month scenario under the same assumptions is $99,874.55; the deck uses the shorter three-month case.

[Robert Half guidance](https://www.roberthalf.com/us/en/insights/research/how-to-calculate-the-cost-of-a-bad-hire-for-your-business) likewise treats costs as business-specific. PromptCode may help employers inspect robustness, cost control, and validation before hiring; reduction in bad hires must be measured in pilots. The slide shows only the estimate and scenario label; arithmetic stays in notes and this research file.

### A pilot ROI scenario to validate

| Assumption / calculation | Without the proposed screen | With the proposed screen |
|---|---:|---:|
| Candidates considered | 10 | 10 |
| Engineering interview labor | 10 × 2 interviewers × 1 hour = 20 h | 4 finalists × 2 interviewers × 1 hour = 8 h |
| Report review labor | — | 10 reports × 10 minutes = 1.67 h |
| Total engineering labor | 20 h | 9.67 h |
| Wage value at $65.38/h | $1,307.60 | $632.01 |
| Proposed one-month pilot fee | — | $199 |
| Combined modeled cost | $1,307.60 | $831.01 |

This scenario frees **10.33 engineer-hours**, valued at **$675.59**, for **$476.59 net capacity value** after the proposed pilot fee. Salaried time released is generally capacity, not immediate cash savings. No real customer result is claimed. It assumes the manager can narrow ten candidates to four without losing relevant candidates; the pilot must test that assumption. Candidate burden, recruiter labor, benefits, setup, and ongoing operating costs are excluded.

Break-even on time alone: $199 ÷ $65.38 = **3.04 engineer-hours**, shown conservatively as 3.1 hours. The broader goal is to provide useful evidence for selection, not simply minimize interview time.

### Where PromptCode fits the decision

1. Hiring manager defines the actual task, required quality, and operational budget.
2. Candidates perform a relevant work sample using tracked AI calls.
3. The evaluator reports clean accuracy, noisy/adversarial behavior, repeated-run consistency, cost, latency, and baseline gain.
4. The manager investigates weak points in a focused interview and makes the decision using the complete evidence.

Before claiming hiring impact, measure report review time, manager-rated usefulness, repeatability, qualified-candidate retention, paid conversion, and eventual job-performance relationships with appropriate consent. A technical benchmark alone is not validation of an employment selection procedure.

## Competitive distinction

**HackerRank:** its documented AI Fluency evaluation examines candidate conversations and IDE activity using context quality, critical thinking, and collaboration. Reports assign A/B/C/NA grades with supporting excerpts; it is an AI add-on. This is meaningful evidence about using an assistant, not merely a pass/fail coding test.

Source: [HackerRank AI Fluency methodology](https://support.hackerrank.com/articles/1773201418-ai-usage-summary).

**CodeSignal:** publishes certified technical assessments, skills reporting, and AI-assisted tasks using its integrated assistant. Its AI Collection includes literacy, prompt engineering, and research assessments. It has established assessment offerings and validation work that PromptCode should not claim to have already matched.

Sources: [technical assessments](https://codesignal.com/technical-assessments/), [AI Collection](https://codesignal.com/newsroom/press-releases/codesignal-launches-ai-skills-assessments-to-evaluate-ai-talent-at-every-level/).

**PromptCode's specific advantage:** its implemented evaluation contract treats the submitted AI workflow as a runtime system. It exposes per-call cost/tokens/latency/retries; repeated perturbed and adversarial outcomes; quality-gated efficiency; and gain over a naive baseline on the same run plan. This is a direct fit for a buyer asking whether an engineer can build a reliable and economical AI workflow. Source: repository `docs/SCORING_SPEC.md` and SDK telemetry model. Implementation is not an independently verified hiring outcome.

The deck compares documented evaluation approaches. It does not use invented crosses to imply competitors lack every related feature. Public marketing and help pages cannot conclusively prove that a feature is absent from every plan. Ask vendors to demonstrate the exact same task, cost report, stress-run breakdown, and baseline comparison before making an exclusivity claim.

### Pricing reality check

CodeSignal lists Build at $99 monthly for five credits and Grow at $599 monthly for 35 credits; annual billing lists $79 and $479 per month respectively. A credit is used when a candidate begins a covered assessment or interview. Product scope and allowances differ from PromptCode's proposed plans; included capacity is not necessarily utilization. PromptCode should not claim to be the cheapest: CodeSignal's published entry price is lower than the proposed $199 pilot.

Source: [CodeSignal pricing](https://codesignal.com/pricing/), reviewed September 9, 2026. PromptCode's $199 and $1,000 plans remain proposals, not current commercial traction.


## Customer impact slide — research and pilot hypothesis

Verified September 9, 2026 against the [2025 Stack Overflow AI survey](https://survey.stackoverflow.co/2025/ai), AI tool frustrations section: 66% of respondents encountered almost-correct AI answers, and 45% reported that debugging AI-generated code is more time-consuming. The question received 31,476 responses and permitted multiple selections. These are self-reported frustrations, not error rates, causal productivity estimates, or PromptCode outcomes.

The slide pairs these findings with the existing pilot ROI scenario above: 10.3333 engineer-hours released × the [BLS May 2025 median developer wage](https://www.bls.gov/news.release/ocwage.t01.htm) of $65.38/hour − $199 proposed pilot fee = $476.59, displayed as $477. The survey findings are not used to derive the model. Validate report-review time, finalists selected, qualified-candidate retention and setup effort in actual pilots before claiming savings.
