"""Calibrated release QA of a reviewed reference; never grades candidate timings."""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.services.interview.registry import get_runner_config
from app.services.interview.trusted_evaluator import (
    _probe_command,
    _run_probe_container,
)

SLUG = 'catalog-suggest-latency'
PROBE = """import {suggest} from './src/suggest';import {buildCatalog} from './src/catalog';import {scoreProduct,compareRank} from './src/rank';import {performance} from 'node:perf_hooks';
const rows=buildCatalog(10000);
const baseline=()=>rows.map(product=>({product,score:scoreProduct(['electronics','item'],product)})).filter(r=>r.score>0).sort(compareRank).slice(0,10).map(r=>r.product.id);
const run=()=>suggest(rows,'electronics item',{limit:10}).map(r=>r.id);
for(let i=0;i<3;i++){baseline();run();}
const samples=[],baselineSamples=[];
for(let i=0;i<9;i++){let t=performance.now();baseline();baselineSamples.push(performance.now()-t);t=performance.now();run();samples.push(performance.now()-t);}
return {samples,baseline_samples:baselineSamples,ids:run(),baseline_ids:baseline(),runtime:{node:process.version,platform:process.platform,arch:process.arch}};"""


def summarize(observation: dict[str, Any]) -> dict[str, Any]:
    def distribution(key: str) -> dict[str, Any]:
        values = observation[key]
        if (not isinstance(values, list) or len(values) != 9
                or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values)):
            raise ValueError('Invalid benchmark samples')
        ordered = sorted(values)
        return {'samples_ms': values, 'p50_ms': ordered[4], 'p95_ms': ordered[8]}

    measured, baseline = distribution('samples'), distribution('baseline_samples')
    calibrated_limit = min(200.0, max(25.0, baseline['p95_ms'] * 4))
    ids = observation.get('ids')
    correct = isinstance(ids, list) and len(ids) == 10 and ids == observation.get('baseline_ids')
    return {'pass': correct and measured['p95_ms'] <= calibrated_limit,
            'kind': 'reviewed_reference_release_qa', 'candidate_grading': False,
            'catalog_size': 10000, 'warmup_runs': 3, 'sample_runs': 9,
            'measurement': measured, 'baseline': baseline, 'limit_ms': calibrated_limit,
            'ranking_matches': correct, 'runtime': observation.get('runtime', {})}


def run_gate() -> dict[str, Any]:
    # Test-only reviewed repair. Production code never imports reference fixtures.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
    from trusted_reference_fixtures import reference_snapshot

    image = get_runner_config(SLUG)['image']
    with tempfile.TemporaryDirectory(prefix='pc-reference-performance-') as temp:
        source = reference_snapshot(SLUG, Path(temp) / 'source')
        code, raw = _run_probe_container(source, _probe_command(SLUG, PROBE), image=image)
        if code != 0:
            return {'pass': False, 'error': 'reference_execution_failed', 'exit_code': code}
        report = summarize(json.loads(raw))
    import docker
    client = docker.from_env()
    try:
        report['image_id'] = client.images.get(image).id
    finally:
        client.close()
    report['limits'] = {'cpu': 1.5, 'memory_mb': 768, 'network': 'none'}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = run_gate()
    except Exception as error:
        report = {'pass': False, 'error': type(error).__name__}
    rendered = json.dumps(report, indent=2, allow_nan=False)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + '\n')
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
