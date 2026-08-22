import pytest

from analytics.survival import km_closure_probability


def test_right_censoring_retains_open_requests_at_risk():
    probability = km_closure_probability([1, 3, 10, 10], [True, True, False, False], 7)
    assert probability == pytest.approx(0.5)


def test_events_after_horizon_do_not_count():
    assert km_closure_probability([8, 12], [True, True], 7) == 0


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        km_closure_probability([], [])
    with pytest.raises(ValueError):
        km_closure_probability([1], [True, False])
    with pytest.raises(ValueError):
        km_closure_probability([-1], [True])
