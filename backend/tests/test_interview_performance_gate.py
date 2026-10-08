import pytest

from scripts.run_interview_performance_gate import summarize


def observation(samples=None, baseline=None):
    return {'samples': [5] * 9 if samples is None else samples,
            'baseline_samples': [2] * 9 if baseline is None else baseline,
            'ids': list(range(10)), 'baseline_ids': list(range(10))}


def test_reference_benchmark_uses_tail_latency_and_calibrated_budget():
    report = summarize(observation([5] * 8 + [26]))
    assert not report['pass']
    assert report['measurement']['p50_ms'] == 5
    assert report['measurement']['p95_ms'] == 26
    assert report['limit_ms'] == 25
    assert report['candidate_grading'] is False


def test_slow_baseline_never_relaxes_the_published_absolute_budget():
    assert summarize(observation([201] * 9, [100] * 9))['pass'] is False
    assert summarize(observation([199] * 9, [100] * 9))['pass'] is True


def test_fast_wrong_ranking_cannot_pass():
    data = observation()
    data['ids'] = list(reversed(data['ids']))
    assert not summarize(data)['pass']


@pytest.mark.parametrize('samples', [[], [1] * 8, [float('nan')] * 9, [float('inf')] * 9, [-1] * 9, [True] * 9])
def test_invalid_samples_fail_closed(samples):
    with pytest.raises(ValueError):
        summarize(observation(samples))
