# Evidence review: scoring AI-enabled software engineering

Research date: October 8, 2026. Scope: PromptCode's twenty featured exercises and the six-dimensional evidence-based review already present in `backend/app/services/interview/grading.py`. This report proposes changes; it does not change live scoring.

## Findings and confidence

A useful interview asks whether someone can turn a requirement into trustworthy software while using available tools responsibly. The recurring signals are requirement framing, codebase comprehension, functional correctness, implementation quality, verification, and ownership of AI output. Tool names, prompt length, agent count, typing speed and generated line count are poor substitutes for these outcomes.

The evidence supports those constructs more strongly than any particular numerical weighting. No reviewed source validates PromptCode's current 35/15/15/10/15/10 split, the proposed 30/15/15/10/20/10 split, or a hiring cutoff. Local reliability and predictive validation remain necessary.

“Software engineer who uses AI” and “engineer building AI products” are different job families. The former needs normal engineering fundamentals plus effective delegation and review. The latter additionally needs model evaluation, data quality, leakage prevention, latency/cost tradeoffs, model failure handling and production monitoring. A general SWE interview should not penalize someone for lacking RAG terminology when the assignment contains no AI product requirements.

Evidence confidence:

| Conclusion | Confidence | Boundary |
|---|---|---|
| Correctness, review, testing and ownership should remain central | High across employer guidance and engineering research | Exact weights unvalidated |
| AI is permitted or encouraged in some major-company interview formats | High for named formats | Not universal across companies or rounds |
| More AI usage means better performance | Unsupported | Tool use and outcomes can diverge |
| Productivity gains depend on task, experience, context and tooling | High | Published estimates are not interchangeable |
| Unaided explanation can expose missing comprehension | Moderate | A standardized, announced probe needs local calibration |
| AI-generated tests alone prove correctness | Unsupported | Shared assumptions and weak oracles can survive |
| An LLM can safely supply the final candidate grade | Unsupported here | Agreement on unrelated benchmarks is insufficient |

## Search coverage and limitations

This is a broad, targeted evidence review, not an exhaustive systematic review of every related paper. Searches covered AI-assisted interviews, employer AI policies, engineering vacancies, human–AI collaboration, coding productivity, learning, security, testing, code review, developer productivity, personnel selection and LLM judging. Official employer material and primary research were preferred. Practitioner videos and Reddit were used to identify concrete behaviors and candidate experiences, not to estimate industry prevalence.

Thirty research sources are annotated below. Reading depth is explicit: selected methods/results/limitations, converted PDF sections, publisher summaries, or abstracts. Survey authors' hundreds of included studies were not individually reviewed here. Recent arXiv manuscripts are identified as preprints; a hosted manuscript is not automatically peer reviewed. Older model results cannot be presented as current model performance.

No private employer scorecard was obtained. Job descriptions establish work expectations, not interview AI permission. Search-index-only vacancies and unavailable pages are separated from verified live sources. Public discussions can contain ads, reposts, selection bias and unverifiable claims. Video evidence below comes from accessible transcripts or publisher excerpts; it is not a claim that every recording was watched.

## Employer evidence

| Employer / source | What was verified | Implication and limits |
|---|---|---|
| [Canva: AI in interviews](https://www.canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews/) | Official June 2025 engineering guidance: realistic tasks, clarification, code fluency, review and responsible AI assistance | Assess engineering decisions and the resulting code. This is format-specific guidance, not a published weighting formula. |
| [Shopify: internship expectations](https://internships.shopify.com/pages/zero-experience-infinite-leverage) | Official essay emphasizes curiosity, contextual assistance, iteration and understanding output | Useful qualitative expectations; internal usage/improvement claims do not validate candidate scoring. |
| [Shopify CTO interview](https://newsletter.pragmaticengineer.com/p/how-ai-is-changing-software-engineering) | Publisher excerpts of Farhan Thawar's interview explicitly discuss AI allowed in coding interviews and reviewing whether code is good | Primary speaker account. Do not infer every team's current process or exact scoring weights. |
| [Meta: official pilot announcement](https://www.linkedin.com/posts/meta_metacareers-interviewing-softwareengineering-activity-7386046074240737280-wnwA) | Meta describes piloting an AI-enabled coding format reflecting practical workflows | Supports a real pilot. Does not prove universal adoption, access to every tool, or an official four-category rubric. |
| [OpenAI: interview guide](https://openai.com/interview-guide/) | Quality, performance, tests, communication, collaboration and learning new domains; AI permission varies by round | Strong counterexample to a blanket “all interviews allow AI” claim. |
| [Anthropic: candidate AI guidance](https://www.anthropic.com/candidate-ai-guidance) | Policy dated July 2025: take-homes and live interviews without AI unless explicitly permitted | Daily AI collaboration does not imply AI permission during assessment. The [careers page](https://www.anthropic.com/careers) separately emphasizes empirical iteration and fundamentals. |
| [Amazon: Ring Operations SWE](https://jobs.amazon.co.uk/en/jobs/10481487/software-development-engineer-ring-operations) | Role expects AI/agentic delivery alongside testing, deployment, reliability and ownership | Verified job expectation; no interview permission established. A single role cannot represent all Amazon hiring. |
| [Stripe: ML Engineer, Growth Platform](https://stripe.com/careers/listing/machine-learning-engineer-growth-platform/8224915) | Problem definition, evaluation, deployment, monitoring, data quality and quality/latency/cost decisions | Specialist ML profile. Use as a separate role track, not a mandatory general SWE checklist. |
| [Atlassian: engineering interview guide](https://www.atlassian.com/company/careers/resources/interviewing/engineering) | Learning, problem solving, design tradeoffs and communication | Supports job-relevant reasoning; does not establish AI permission. |
| [Google: DORA 2025](https://blog.google/innovation-and-ai/technology/developers-tools/dora-report-2025/) | Organization-level evidence of widespread AI adoption and uneven trust/outcomes | Organizational survey, not Google's hiring rubric. No verified company-wide AI interview policy in this review. |
| [Microsoft: 2026 Work Trend material](https://blogs.microsoft.com/blog/2026/05/05/how-frontier-firms-are-rebuilding-the-operating-model-for-the-age-of-ai/) | Broad AI-work research discusses human quality control and critical thinking | Not SWE-specific job evidence or a universal interview policy. A team-specific Reddit account is weaker evidence below. |
| [NVIDIA: coding-agent harness vacancy](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Software-Engineer--Coding-Agent-Harness-Engineering----New-College-Grad-2026_JR2023749) | Search-index description of agent systems/performance work; direct page did not expose usable text | Discovery only. Do not present as a verified currently open position or interview policy. |
| [Apple: iCloud GenAI/agentic vacancy](https://jobs.apple.com/en-us/details/200660280-3337/senior-icloud-efficiency-engineer-genai-agentic-systems?team=SFTWR) | Indexed description suggested operational tooling; direct page was no longer available | Historical/limited evidence, excluded from current-policy consensus. |
| [Netflix careers search](https://explore.jobs.netflix.net/careers?query=netflix.com%3D) | AI-related listings surfaced, but no sufficiently verified specific interview policy or role detail | Coverage gap, not evidence of a company-wide transition. |

The defensible conclusion is that some employers are adapting assessment to AI-assisted work, while others deliberately retain independent assessments. The scoring constructs converge more than their tool policies.

## Videos and practitioner accounts

1. **Shopify CTO Farhan Thawar, July 2025.** [Publisher excerpts and chapters](https://newsletter.pragmaticengineer.com/p/how-ai-is-changing-software-engineering); [recording at 42:07](https://www.youtube.com/watch?v=u-3IILWQPRM&t=2527s). The verified excerpt discusses AI-assisted interviews and whether candidates recognize problems in generated code, including when a small direct edit is preferable to repeated prompting. Evidence reviewed: publisher transcript excerpts; direct YouTube retrieval failed. Scoring inference: reward choosing an effective next action and inspecting output, not a prescribed tool ritual.
2. **Addy Osmani, November 2025.** [Zed's interview excerpts](https://zed.dev/blog/ai-70-problem-addy-osmani). Highlights the remaining integration, edge-case and ownership work after an impressive initial draft. The “70% problem” is a practitioner framing, not a measured universal percentage and not a basis for a 70-point correctness weight. Evidence reviewed: selected publisher excerpts.
3. **Addy Osmani, AI Engineer World's Fair 2026.** [Talk page with transcript](https://ai.engineer/talks/n97BCfyFIvw-engineer-future-is-person-who-is-able). Accessible transcript/talk material concerns problem choice, verification, comprehension and accountability. Evidence reviewed: page and selected transcript material, not independently watched video. Use to motivate ownership probes; no quantitative validation.
4. **Simon Willison, September 2024.** [Publisher episode notes](https://newsletter.pragmaticengineer.com/p/ai-tools-for-software-engineers-simon-willison). Useful context on experimenting with tools and understanding their behavior. Only notes/chapters were inspected; not used as a source of exact interview criteria.

## Reddit: useful behaviors, weak policy evidence

| Discussion | Evidence quality | What it adds |
|---|---|---|
| [ExperiencedDevs: what interviewers seek in an AI session](https://www.reddit.com/r/ExperiencedDevs/comments/1vivvyh/what_are_interviewers_actually_looking_for_in_a/) | Anonymous, mixed experiences and preferences | Planning, review and understanding recur; commenters disagree on plan modes and subagents. Do not turn personal preferences into grading rules. |
| [ExperiencedDevs: reviewing candidates for AI roles](https://www.reddit.com/r/ExperiencedDevs/comments/1wql3g2/interviewed_candidates_for_ai_engineer_roles_this/) | Small anonymous account; role definition ambiguous | Reviewing a generated PR can expose business-logic and ownership gaps. This motivates an exercise design, not a prevalence estimate. |
| [Shopify internship pairing question](https://www.reddit.com/r/csMajors/comments/1qer9j3/question_about_shopify_internship_pair/) | Candidate quotes invitation; asks for preparation advice | Corroborates encouragement in a particular invitation. It is not an observed scorecard or outcome. |
| [Microsoft SDE2 AI-assisted interview account](https://www.reddit.com/r/leetcode/comments/1sfgtu3/ai_assisted_coding_interview_experience_microsoft/) | Unverified individual team account | Describes an AI-enabled coding setup and load-balancer task. No company-wide extrapolation. |
| [Recruitinghell: unclear success criteria](https://www.reddit.com/r/recruitinghell/comments/1ul4uqb/ai_assisted_coding_interview_what_is_the_criteria/) | Anonymous candidate uncertainty | Publish criteria, tool rules and graded parts in advance. It does not establish which criteria predict performance. |
| [Meta AI interview discussion](https://www.reddit.com/r/leetcode/comments/1p2i6op/anyone_recently_taken_metas_aiassisted_coding/) | Deleted accounts and promotional contamination | Exact format claims were downweighted; ads/repeated claims are not independent corroboration. |
| [Canva backend interview preparation](https://www.reddit.com/r/cscareerquestionsOCE/comments/1mc4uqu/canva_ai_coding_interview_backend_engineer/) | Preparation question rather than completed interview evidence | Discovery only; do not infer tests or grading from questions about them. |

## Research bibliography and implications

Each entry separates the result from its use in our rubric. These are thirty sources examined at varying depths, not thirty fully read papers or thirty independent hiring validations.

### Productivity and human–AI workflow

**R01 — [The Impact of AI on Developer Productivity (2023)](https://arxiv.org/abs/2302.06590).** Abstract screened. A controlled JavaScript HTTP-server task reported 55.8% faster completion with Copilot. Narrow task and older tooling limit transfer. Implication: tool assistance can help, but time alone does not measure correctness, maintainability or ownership.

**R02 — [Three field experiments with software developers (2025)](https://www.microsoft.com/en-us/research/publication/the-effects-of-generative-ai-on-high-skilled-work-evidence-from-three-field-experiments-with-software-developers/).** Publisher research summary inspected. Across 4,867 developers, estimated completed-task output rose 26.08%, with substantial uncertainty and heterogeneous effects. Completion is a productivity proxy, not comprehensive software quality. Implication: allow realistic assistance; do not award points merely for use.

**R03 — [How much does AI impact development speed? (2024)](https://arxiv.org/html/2410.12944v1).** Selected methods/results inspected. Enterprise experiment with 96 engineers; an adjusted estimate suggested roughly 21% less time, but its uncertainty was large and adjusted p=.086. Do not portray that estimate as a universally established effect. Implication: calibrate task and level; speed should be contextual evidence.

**R04 — [Experienced open-source developers and early-2025 tools](https://arxiv.org/html/2507.09089v2).** Selected methods/results/limitations inspected. Sixteen developers completed 246 tasks in familiar repositories; AI access increased time by 19% despite optimistic perceptions. Small, specific setting and historical tools. The [February 2026 METR update](https://metr.org/blog/2026-02-24-uplift-update/) describes selection and timing difficulties in later measurement; it neither erases the original result nor proves current tools still slow everyone. Implication: score demonstrated work, not perceived acceleration.

**R05 — [How AI Impacts Skill Formation (2026)](https://arxiv.org/html/2601.20245v1).** Selected full-text sections and [author research summary](https://www.anthropic.com/research/AI-assistance-coding-skills) inspected. In the main 52-person unfamiliar-library study, mean quiz performance was approximately 50 versus 67: a 17-percentage-point gap. Debugging/comprehension suffered in some use patterns; interaction patterns were not randomized subgroups. Single library and chat-style assistance limit generalization. Implication: an announced short transfer/defense probe can add evidence absent from a passing artifact.

**R06 — [Grounded Copilot (2022/2023)](https://arxiv.org/abs/2206.15000).** Abstract screened. Qualitative study of twenty participants distinguishes acceleration and exploration modes. Neither is inherently the only good workflow. Implication: accept multiple effective strategies; grade context, decisions and review.

**R07 — [What software practitioners think about AI assistants (2023/2024)](https://arxiv.org/abs/2303.17125).** Abstract screened. Survey of 410 developers highlights requirements, control and verification concerns. Self-report and selection bias constrain causal conclusions. Implication: framing and output evaluation deserve explicit anchors.

**R08 — [Beginning programmers and code-generating LLMs (CHI 2024)](https://arxiv.org/abs/2401.15232).** Abstract and published study description inspected. Study of 120 beginners across three institutions examines difficulties specifying intent and revising prompts. Novice education differs from experienced hiring. Implication: score whether context is effective rather than rewarding prompt jargon.

### Security, comprehension and human judgment

**R09 — [Do Users Write More Insecure Code with AI Assistants? (CCS 2023)](https://arxiv.org/html/2211.03622v3).** Selected methods/results inspected. In studied security tasks, assisted participants produced less secure code and showed greater confidence. Older tooling and task selection matter. Implication: confidence is not evidence; use explicit security invariants where relevant.

**R10 — [Lost at C (USENIX Security 2023)](https://arxiv.org/abs/2208.09727).** Abstract screened. Fifty-eight student participants in a C task showed a more limited security impact than some other studies. Different contexts produce different outcomes. Implication: assess actual vulnerabilities rather than applying a blanket AI-use penalty.

**R11 — [We Have a Package for You (USENIX Security 2025)](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen).** Conference abstract and [author explanation](https://www.usenix.org/publications/loginonline/we-have-package-you-comprehensive-analysis-package-hallucinations-code) inspected. Package hallucinations create dependency and supply-chain risks. Model-level observations do not establish candidate failure rates. Implication: inspect generated dependencies, APIs and provenance when a task introduces them.

**R12 — [Generative AI and critical thinking (CHI 2025)](https://www.microsoft.com/en-us/research/publication/the-impact-of-generative-ai-on-critical-thinking-self-reported-reductions-in-cognitive-effort-and-confidence-effects-from-a-survey-of-knowledge-workers/).** PDF converted to Markdown; selected sections inspected. Survey of 319 knowledge workers and 936 examples concerns self-reported effort and confidence, not a measured permanent decline in ability. Implication: observe verification and stewardship directly; don't diagnose a candidate from AI use.

**R13 — [When combinations of humans and AI are useful (Nature Human Behaviour 2024)](https://www.nature.com/articles/s41562-024-02024-1).** PDF converted to Markdown; abstract/limitations inspected. Meta-analysis of 106 studies and 370 effects found average combined performance below the better standalone human or AI condition, with substantial heterogeneity. This does not mean AI always performs worse than humans. Implication: collaboration is not automatically synergy; measure the actual joint outcome.

### Measuring engineering and selecting people

**R14 — [SPACE of Developer Productivity (2021)](https://www.microsoft.com/en-us/research/publication/the-space-of-developer-productivity-theres-more-to-it-than-you-think/).** Primary research summary inspected. Productivity spans multiple dimensions; activity alone is inadequate. Organizational measurement framework, not an individual interview scorecard. Implication: do not grade token counts, keystrokes or generated lines.

**R15 — [Revisiting selection-system design (2023)](https://www.cambridge.org/core/journals/industrial-and-organizational-psychology/article/revisiting-the-design-of-selection-systems-in-light-of-new-findings-regarding-the-validity-of-widely-used-predictors/A20984B138319E3D432E643978BF026D).** Selected full-text sections inspected. Revised validity estimates and corrections affect how selection methods should be compared; structured, job-relevant evidence matters. Validity varies by context. Implication: standardize questions and anchors, then validate locally. Reviewer agreement alone does not prove job-performance prediction.

### Correctness and test strength

**R16 — [SWE-bench (ICLR 2024)](https://arxiv.org/abs/2310.06770), [benchmark design](https://www.swebench.com/original.html).** Abstract and project methodology inspected. Repository-level issues and fail-to-pass/pass-to-pass tests illustrate functional repair plus preservation. This is a model benchmark, not validation of human hiring decisions. Implication: verify the requested repair and unaffected behavior separately.

**R17 — [EvalPlus (NeurIPS 2023)](https://arxiv.org/abs/2305.01210).** Abstract screened. Expanded tests expose incorrect solutions accepted by smaller suites and can change rankings. Unit-function benchmark differs from repository work. Implication: private independent counterexamples and strong oracles matter more than raw test count.

**R18 — [STING (2026 preprint)](https://arxiv.org/html/2604.01518v1).** Selected methods/results inspected. Mutation-oriented evaluation finds surviving wrong variants in many examined instances. Preprint findings do not establish PromptCode's defect rate. Implication: seed plausible incorrect repairs and ensure tests reject them, rather than claiming completeness from a green suite.

### Maintenance, review and grader reliability

**R19 — [AI coding assistance and maintenance burden (2025 preprint)](https://arxiv.org/html/2510.10165v1).** Selected methods/results inspected. Observational open-source analysis connects increased assistance exposure with review/rework burden; exposure proxies and identification assumptions limit causality. Implication: distinguish apparent implementation output from maintainable integration.

**R20 — [Human–machine code-review collaboration (2025 manuscript)](https://arxiv.org/html/2501.02092v1).** Selected sections inspected. Twenty interviews explore context, trust and reviewing AI-supported work. Qualitative evidence does not yield numerical weights. Implication: assess review reasoning and context-specific risk.

**R21 — [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (2023)](https://arxiv.org/html/2306.05685v4).** Selected sections inspected. Position, verbosity and self-preference biases illustrate evaluator weaknesses. Agreement on these benchmarks does not validate engineering candidate scoring. Implication: use AI for evidence organization, with accountable human review of scores.

**R22 — [Four Years of Generative AI in computing education and hiring (2026 preprint)](https://arxiv.org/html/2607.24246v1).** Selected methods/results inspected. Includes 56 educators and 24 hiring professionals, recruited through nonrepresentative networks. Hiring respondents emphasize critical evaluation, responsible use, adaptation, communication and decomposition. Small convenience sample: reported percentages are not industry prevalence or proposed weights. Implication: useful direct triangulation of criteria, weak support for numerical precision.

### Broader literature maps and emerging cautions

**R23 — [In-IDE human–AI experience review (2025, revised 2026)](https://arxiv.org/abs/2503.06195).** Abstract screened. Authors synthesize ninety studies, including verification effort, user control and overreliance. Their included studies were not individually reviewed here. Implication: consider interaction quality and verification costs; no universal workflow prescription.

**R24 — [LLMs for software engineering: survey (2023)](https://arxiv.org/abs/2310.03533).** Abstract screened. Broad coverage across engineering tasks and the need to detect incorrect output. Implication: frame AI competence across the lifecycle, not only code generation. Background coverage, not hiring validation.

**R25 — [LLMs for software engineering: systematic review (2023/2024)](https://arxiv.org/abs/2312.15223).** Abstract screened. Authors cover 947 studies, 112 tasks and five lifecycle phases. This review did not read those 947 studies individually. Implication: the relevant domain is much wider than prompt syntax; survey scope cannot justify exact criterion weights.

**R26 — [Software testers using LLMs (2025 preprint)](https://arxiv.org/abs/2510.17164).** Abstract screened. Fifteen tester interviews describe objectives, iteration and evaluation. Preliminary qualitative study. Implication: judge test objectives and assertions, not the number of generated tests.

**R27 — [Software Testing with LLMs: Survey, Landscape, and Vision (2023/2024)](https://arxiv.org/abs/2307.07221).** Abstract screened; page identifies acceptance in IEEE Transactions on Software Engineering. Authors review 102 studies, particularly test preparation and program repair. Implication: LLMs can assist testing, but the survey does not establish that self-generated tests independently validate a solution.

**R28 — [Trustworthy AI-Assisted Software Engineering (2026 vision manuscript)](https://arxiv.org/abs/2602.06310).** Abstract screened. Proposes evidence-centered work, accountability, transparency and selective inspection. Vision, not empirical validation. Implication: risk-proportional review is preferable to demanding every line be manually authored.

**R29 — [Coding-tool pitfalls (2026 preprint)](https://arxiv.org/abs/2603.20847).** Abstract screened. Analysis of approximately 3,800 reported tool bugs includes functional and integration/configuration problems. These are tool reports, not candidate error frequencies. Implication: separate infrastructure failures from ability and provide consistent retry rules.

**R30 — [A Judge Should Know What Changed (2026 preprint)](https://arxiv.org/abs/2608.24419).** Abstract screened. Distinguishes invariance to irrelevant edits from sensitivity to actual changes in the evaluated construct. High agreement can coexist with weak construct sensitivity. Implication: audit graders using polished incorrect explanations, terse correct explanations and actual semantic changes; reliability alone is insufficient.

## Platform guidance: corroboration, not validation

[Karat's April 2026 rubric guidance](https://karat.com/resource/human-ai-technical-interview-rubrics/) distinguishes outcome and process, codebase navigation, ambiguity, implementation, AI judgment and communication. It is a provider-authored framework, not a published validation of our weights. [HelloInterview's Meta guide](https://www.hellointerview.com/blog/meta-ai-enabled-coding) and [Shopify guide](https://www.hellointerview.com/blog/shopify-ai-enabled-coding) provide candidate-synthesis descriptions of practical workflows. They are not official internal scorecards. Exact format and tool claims should be checked against each invitation.

A Codility work-analysis PDF URL redirected to a marketing homepage during conversion. It was not treated as a reviewed empirical study. Other indexed marketing announcements were insufficient to support scoring precision.

## What should drive scoring

| Construct | Observable evidence | Sources supporting the construct | What must not substitute for evidence |
|---|---|---|---|
| Correctness | Independent outcomes, invariants and preserved regressions | Canva, OpenAI, R16–R18 | Candidate confidence or plausible-looking code |
| Framing and investigation | Requirements, state model, scope, root cause and decomposition | Canva, Atlassian, R06–R08, R22 | Long narration or mandatory plan-mode use |
| Implementation quality | Fits repo, handles failures, appropriate complexity and maintainability | Amazon, OpenAI, R19–R20 | Cleverness or cosmetic cleanup |
| AI oversight | Effective context, bounded delegation, review, correction and tool choice | Shopify, Canva, R05–R11, R22 | Prompt count, model brand or agent count |
| Verification | Independent expectations, discriminating counterexamples, regression checks | R16–R18, R26–R27 | Green tests generated from the same mistaken assumption |
| Explanation and ownership | Accurate defense, limitations, ability to adapt to a stated change | Shopify, OpenAI, R05, R12 | Eloquence or unannounced trivia tests |

This mapping is an interpretation across sources. No paper directly establishes that these six dimensions with our weights predict job performance.

## Decisions and unanswered questions

Recommended: preserve the six existing dimensions, make their anchors specific, modestly increase verification emphasis, show the rubric to candidates, keep behavioral results separate from the human review, and pilot before claiming validation. The companion proposal specifies the mechanics and question-level evidence.

Still unresolved: real interview timing per question; inter-reviewer reliability; whether dimensions distinguish performance rather than repeat correctness; role/seniority differences; tool-access effects; fairness and accommodations; valid hiring thresholds; prediction of subsequent work quality. These require collected local data and responsible interpretation, not another borrowed percentage.
