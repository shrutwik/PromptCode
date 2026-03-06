# PromptCode - Claude Code Configuration

## Project Overview
LeetCode-style AI evaluation platform for scoring prompt engineering efficiency and LLM reliability.

## Ruflo Swarm Mode - REQUIRED ✅
**ALL future work must use Ruflo swarm orchestration.**

- **Swarm ID**: swarm-1772785751616
- **Topology**: Hierarchical
- **Max Agents**: 8
- **Strategy**: Specialized
- **Config**: `.swarm/state.json`

### Why Ruflo?
- Distributes tasks across 8 specialized agents for parallel processing
- Reduces redundant API calls through intelligent task coordination
- Optimizes token usage and cost via agent-level caching and deduplication
- Improves response quality through multi-perspective analysis

### Guidelines for Ruflo Usage

1. **Task Decomposition**: Always break complex tasks into sub-tasks that can be handled by specialized agents
   - Backend/API tasks → dedicated agent
   - Evaluation pipeline work → dedicated agent
   - Documentation/schema tasks → dedicated agent
   - Testing/validation → dedicated agent

2. **Agent Selection**: Leverage the hierarchical topology
   - Coordinator agent: manages task orchestration and dependency chains
   - Specialized agents: handle domain-specific work (backend, evaluation, SDK, Docker)
   - Parallel execution for independent tasks to minimize wall-clock time

3. **Token Optimization**
   - Reuse analysis results across agent conversations
   - Avoid redundant code reads when agents can share context
   - Use agent-level memory for persistent state (shared analysis, patterns)
   - Batch related operations within single agent sessions

4. **API Cost Control**
   - Prefer agent parallelization over sequential operations
   - Use agents with smaller context windows for focused tasks
   - Cache and reuse evaluation results across multiple agents
   - Avoid duplicate LLM calls across agents (coordinate via swarm)

## Project Structure
```
PromptCode/
├── backend/              # FastAPI + evaluation engine
├── sdk/                  # promptcode SDK
├── challenges/           # Challenge definitions
├── docker/               # Container setup
└── .swarm/               # Ruflo configuration (DO NOT EDIT)
```

## Key Commands
```bash
# Start development stack
docker-compose up -d

# Run background queue worker
cd backend && python -m scripts.run_queue_worker

# Seed first challenge
cd backend && python -m scripts.seed_challenge

# Run tests
cd backend && pytest -q
```

## Development Workflow
1. **For any task**: First check if it can be decomposed for parallel agent work
2. **For code analysis**: Use agents to review different subsystems simultaneously
3. **For testing/validation**: Run tests in parallel agents with different focus areas
4. **For documentation**: Use agents to document different architectural layers in parallel

## Before Starting Work
- Verify Ruflo swarm is active: `npx ruflo swarm status`
- Check agent availability: `npx ruflo swarm list-agents`
- Monitor token usage: agents report usage per task

## Important Notes
- **Never disable Ruflo** - it's the foundation for cost-efficient development
- **Always coordinate** - agents sync results to avoid duplication
- **Respect agent roles** - use each agent's specialization appropriately
- **Document decisions** - keep memory.md updated with architectural insights

## Contact / Review
For Ruflo optimization adjustments, review latest agent performance in `.swarm/state.json` and tune strategy if needed.
