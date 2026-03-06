# PromptCode Fixes: Week 1-3 Implementation Plan

## WEEK 1-2: PARALLELIZE EVALUATION ENGINE

### Current Problem
- Sequential evaluation loop (line 283-306 in engine.py)
- Each submission runs 8 times sequentially: 1 clean + 5 perturbed + 2 adversarial
- Each run blocked by Docker container (120s timeout)
- **Impact:** 100 submissions = 26.7 hours

### Solution
1. Convert `evaluate_submission()` to async
2. Use `asyncio.to_thread()` to run blocking `run_in_sandbox()` calls in thread pool
3. Use `asyncio.gather()` to parallelize all runs
4. Expected speedup: **8x** (all runs in parallel)

### Implementation Steps

**Step 1: Backup current code**
- Copy `engine.py` to `engine.py.backup`

**Step 2: Create async evaluation function**
- Refactor `evaluate_submission()` → `async def evaluate_submission_parallel()`
- Keep old function for fallback

**Step 3: Add parallel run execution**
```python
async def _run_all_in_parallel(run_plan, code, entrypoint, challenge_config):
    tasks = []
    for spec in run_plan:
        task = asyncio.to_thread(
            run_in_sandbox,
            code,
            entrypoint,
            challenge_config,
            input_overrides=spec["inputs"]
        )
        tasks.append((spec, task))

    results = await asyncio.gather(*[task for _, task in tasks])
    return list(zip([spec for spec, _ in tasks], results))
```

**Step 4: Update callers**
- Find all calls to `evaluate_submission()`
- Convert to `await evaluate_submission_parallel()`
- Check: worker loop, API routes

**Step 5: Test with small run**
- Verify no errors
- Measure timing improvement

---

## WEEK 3: ASYNC + E2E TEST SUITE

### Current Problem
- Zero async tests despite 100% async backend
- No E2E tests (submission → evaluate → report flow)
- Evaluation engine untested

### Solution
1. Add pytest-asyncio for async test support
2. Create E2E test for full submission flow
3. Test parallel evaluation timing

### Implementation Steps

**Step 1: Add test dependencies**
- Add `pytest-asyncio` to requirements-dev.txt

**Step 2: Create async test base**
```python
@pytest.mark.asyncio
async def test_evaluate_submission_parallel():
    """Test parallel evaluation speedup"""
```

**Step 3: E2E test (submission → evaluation → report)**
```python
@pytest.mark.asyncio
async def test_full_submission_flow():
    # Create submission
    # Enqueue evaluation
    # Poll until complete
    # Verify report structure
```

---

## CHECKPOINTS

**After Step 1 (Backup):**
- ✅ Original code safe
- ✅ Ready to modify

**After Step 2 (Create async function):**
- ✅ New function exists alongside old
- ✅ Old function still works (fallback)
- ✅ No breaking changes

**After Step 3 (Parallel execution):**
- ✅ Parallel version ready
- ✅ Local testing OK

**After Step 4 (Update callers):**
- ✅ All calls updated
- ✅ Linting passes
- ✅ Type checking passes

**After Step 5 (Test with small run):**
- ✅ No errors
- ✅ Timing improved (ideally ~8x faster)
- ✅ Results identical to sequential version

**Week 3 Complete:**
- ✅ Async tests pass
- ✅ E2E tests pass
- ✅ Coverage improved

---

## VALIDATION

After each step, run:
```bash
cd backend
python -m py_compile app/services/evaluation/engine.py  # Check syntax
mypy app/services/evaluation/engine.py --ignore-missing-imports  # Type check
pytest -xvs backend/tests/test_engine_policy.py  # Existing tests still pass
```

---

## ROLLBACK PLAN

If anything breaks:
1. `cp backend/app/services/evaluation/engine.py.backup backend/app/services/evaluation/engine.py`
2. Revert to sequential version
3. Debug and try again

