from src.history_policy import MIN_YEARS_CAGR, MIN_YEARS_CONSISTENCY, MIN_YEARS_TREND, MAX_ANALYTICAL_YEARS, bounded_history, cagr_start_end, enough_history, valid_history


def test_history_uses_available_values_without_padding():
    assert valid_history([None, 10.0, None, 20.0]) == [10.0, 20.0]
    assert enough_history([None, 10.0, None, 20.0], MIN_YEARS_CAGR)


def test_history_does_not_require_ten_years():
    values = [2019, 2020, 2021, 2022, 2023, 2024]
    assert bounded_history(values) == values
    assert len(bounded_history(values)) < MAX_ANALYTICAL_YEARS


def test_bounded_history_keeps_latest_maximum_observations():
    values = list(range(15))
    assert bounded_history(values) == list(range(5, 15))


def test_cagr_uses_first_and_last_valid_observations():
    assert cagr_start_end([None, 100.0, None, 200.0]) == (100.0, 200.0, 1)
    assert cagr_start_end([100.0]) is None


def test_shared_minimums_are_explicit():
    assert MIN_YEARS_CAGR == 2
    assert MIN_YEARS_TREND == 3
    assert MIN_YEARS_CONSISTENCY == 3
