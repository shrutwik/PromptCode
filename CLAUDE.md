# PromptCode - Claude Code Configuration

## Project Overview
LeetCode-style AI evaluation platform for scoring prompt engineering efficiency and LLM reliability.

## Ruflo Swarm Mode - REQUIRED ✅
**ALL future work must use Ruflo swarm orchestration with FULL 64-AGENT CAPACITY.**

- **Swarm ID**: swarm-1772785990997
- **Topology**: Hierarchical
- **Max Agents**: 64 (Full Parallelization)
- **Strategy**: Specialized
- **Auto Scale**: Enabled
- **Config**: `.swarm/state.json`

### Why Ruflo with 64 Agents?
- **Massive Parallelization**: 64 specialized agents working simultaneously on different task aspects
- **Extreme Cost Efficiency**: Parallel execution reduces wall-clock time by 60x+ vs sequential work
- **Redundancy Elimination**: Agent coordination prevents duplicate API calls across the swarm
- **Token Optimization**: Agent-level caching, deduplication, and result reuse across all 64 workers
- **Multi-perspective Analysis**: 64 agents provide extensive coverage of problem space
- **Fault Tolerance**: If one agent fails, 63 others continue work seamlessly

### Guidelines for Ruflo Usage

1. **Task Decomposition**: Always break complex tasks into sub-tasks that can be handled by specialized agents
   - Backend/API tasks → dedicated agent
   - Evaluation pipeline work → dedicated agent
   - Documentation/schema tasks → dedicated agent
   - Testing/validation → dedicated agent

2. **Agent Allocation** (64-Agent Capacity):
   - **1 Coordinator Agent**: Task orchestration, dependency management, swarm synchronization
   - **10-15 Backend/API Agents**: Simultaneous work on different API routes and services
   - **10-15 Evaluation Agents**: Parallel evaluation pipeline components and scoring logic
   - **8-10 SDK/Integration Agents**: Concurrent SDK improvements and client implementations
   - **8-10 Testing Agents**: Parallel test execution across different test suites
   - **8-10 Documentation Agents**: Concurrent documentation of different subsystems
   - **5-8 DevOps/Docker Agents**: Parallel infrastructure and containerization work
   - Remaining agents: Buffer for dynamic task distribution based on workload

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
