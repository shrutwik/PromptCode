# AI Leverage Evaluation Research Notes (Mar 2026)

This note captures external references used to strengthen PromptCode's AI-usage evaluation model.

## Primary Sources

1. OpenAI docs: Evaluation best practices  
   https://platform.openai.com/docs/guides/evaluation-best-practices
2. OpenAI docs: Graders  
   https://platform.openai.com/docs/guides/graders
3. OpenAI docs: Trace grading  
   https://platform.openai.com/docs/guides/trace-grading
4. NIST AI RMF 1.0: GenAI profile (NIST AI 600-1)  
   https://doi.org/10.6028/NIST.AI.600-1
5. ArXiv: Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity (2507.09089)  
   https://arxiv.org/abs/2507.09089
6. ArXiv: The Impact of AI on Developer Productivity: Evidence from GitHub Copilot (2410.12944)  
   https://arxiv.org/abs/2410.12944
7. ArXiv: AI-enhanced productivity is not a shortcut to competence (2601.20245)  
   https://arxiv.org/abs/2601.20245
8. ArXiv: Saving SWE-Bench from Obsolescence through Test Case Mutation (2510.08996)  
   https://arxiv.org/abs/2510.08996

## Key Takeaways Applied in PromptCode

- Evals should be task-specific, regression-oriented, and continuously maintained.
- Grading should support structured/partial credit and track process quality, not only final output.
- Trustworthiness requires TEVV discipline: pre-deployment testing, measurable uncertainty, and incident-minded rigor.
- AI productivity effects are context-dependent; score systems must avoid assuming "more AI use = better".
- Full delegation can hurt skill formation; systems should reward verified, intentional AI usage.
- Benchmarks drift over time; hidden/perturbed/adversarial variation and mutation-style realism checks are essential.

## Implementation Mapping

- Existing in PromptCode:
  - Counterfactual baseline and leverage gain.
  - Clean/perturbed/adversarial/hidden run plan.
  - Confidence and credibility scoring.
  - Usage frontier and reliance calibration metrics.

- Added in this pass:
  - `future_feedback_v1` in evaluator worker:
    - behavior scores: `verification_discipline`, `efficient_leverage`, `adaptation_speed`, `evaluation_rigor`
    - `readiness_score` + `readiness_band`
    - `delegation_mode` (`over_delegating` / `balanced` / `under_leveraging`)
    - prioritized, measurable 7-day action plan
    - explicit next-eval protocol checklist
  - UI surfacing in submission report:
    - readiness + delegation visibility
    - future-plan items merged into candidate action tips

## Why This Matters

PromptCode now judges not only outcome quality, but the candidate's AI working style:
- Are they verifying outputs?
- Are they improving signal-to-cost leverage?
- Are they learning effectively across iterations?
- Are they using a publish-grade evaluation protocol?

That is closer to real-world AI engineering performance than single-shot scorecards.
