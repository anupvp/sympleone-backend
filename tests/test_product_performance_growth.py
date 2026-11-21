from app.services.product_performance.growth import compute_growth, growth_sort_key


def test_growth_new_product() -> None:
    result = compute_growth(100.0, 0.0)
    assert result.growth_display == "NEW"
    assert result.growth_percentage is None


def test_growth_both_zero() -> None:
    result = compute_growth(0.0, 0.0)
    assert result.growth_display == "0%"
    assert result.growth_percentage == 0.0


def test_growth_previous_positive_current_zero() -> None:
    result = compute_growth(0.0, 50.0)
    assert result.growth_display == "-100%"
    assert result.growth_percentage == -100.0


def test_growth_positive_percent() -> None:
    result = compute_growth(120.0, 100.0)
    assert result.growth_percentage == 20.0
    assert result.growth_display == "+20%"


def test_growth_sort_key_new_last() -> None:
    new = compute_growth(10.0, 0.0)
    low = compute_growth(50.0, 100.0)
    assert growth_sort_key(low) < growth_sort_key(new)