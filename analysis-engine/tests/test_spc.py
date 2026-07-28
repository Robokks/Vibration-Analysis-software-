import numpy as np
import pytest

from analysis_engine.spc.histogram import compute_histogram
from analysis_engine.spc.xchart import compute_xchart


def test_xchart_flags_outlier_beyond_3_sigma():
    rng = np.random.default_rng(0)
    values = list(rng.normal(10, 0.1, size=50))
    values[25] = 10 + 10.0  # extreme outlier

    result = compute_xchart(values)

    assert result.center_line == pytest.approx(np.mean(values), rel=0.2)
    assert 25 in result.out_of_control_indices


def test_xchart_no_outliers_for_tight_normal_data():
    # deterministic small oscillation around 5.0, well within 3 sigma - avoids
    # the inherent flakiness of relying on random normal samples staying under
    # a 3-sigma bound.
    values = [5.0 + 0.01 * ((-1) ** i) for i in range(30)]
    result = compute_xchart(values)
    assert result.out_of_control_indices == []


def test_xchart_requires_at_least_two_values():
    with pytest.raises(ValueError):
        compute_xchart([1.0])


def test_histogram_counts_sum_to_sample_size():
    values = np.random.default_rng(2).normal(0, 1, size=200)
    result = compute_histogram(values, n_bins=10)
    assert result.counts.sum() == 200
    assert len(result.bin_edges) == 11
