from datetime import date, time
from decimal import Decimal

import pytest

from models.common import DeliveryDistance, PricingRule
from utils.pricing import PricingService


def test_calculate_nightly_rates(sample_pricing_rule: PricingRule):
    """Test calculation of nightly rates."""
    service = PricingService([sample_pricing_rule])

    # Test regular weekday rates
    rates = service.calculate_nightly_rates(
        date(2024, 6, 3),  # Monday
        date(2024, 6, 5),  # Wednesday
    )
    assert rates == Decimal("200")  # 2 nights at base price

    # Test weekend rates (20% higher)
    rates = service.calculate_nightly_rates(
        date(2024, 6, 7),  # Friday
        date(2024, 6, 9),  # Sunday
    )
    assert rates == Decimal("240")  # 2 nights at weekend price (120 each)

    # Test mixed rates
    rates = service.calculate_nightly_rates(
        date(2024, 6, 6),  # Thursday
        date(2024, 6, 9),  # Sunday
    )
    assert rates == Decimal("340")  # 1 regular night (100) + 2 weekend nights (240)


def test_validate_minimum_stay(sample_pricing_rule: PricingRule):
    """Test minimum stay validation."""
    service = PricingService([sample_pricing_rule])

    # Test valid stay duration
    service.validate_minimum_stay(
        date(2024, 6, 1),
        date(2024, 6, 5),  # 4 nights
    )

    # Test invalid stay duration
    with pytest.raises(ValueError, match="Minimum stay requirement not met"):
        service.validate_minimum_stay(
            date(2024, 6, 1),
            date(2024, 6, 3),  # 2 nights
        )


def test_calculate_fees(sample_pricing_rule: PricingRule):
    """Test calculation of all fees."""
    service = PricingService([sample_pricing_rule])

    # Test basic booking without extras
    fees = service.calculate_fees(
        start_date=date(2024, 6, 3),
        end_date=date(2024, 6, 6),
        pickup_time=time(14, 0),
        return_time=time(12, 0),
    )
    assert fees.nightly_rates == Decimal("300")  # 3 nights at base price
    assert fees.service_fee == Decimal("50")
    assert fees.early_pickup_fee is None
    assert fees.late_return_fee is None
    assert fees.parking_fee is None
    assert fees.delivery_fee is None

    # Test booking with all extras
    fees = service.calculate_fees(
        start_date=date(2024, 6, 3),
        end_date=date(2024, 6, 6),
        pickup_time=time(10, 0),  # Early pickup
        return_time=time(17, 0),  # Late return
        use_parking=True,
        delivery_distance=DeliveryDistance.KM_100,
    )
    assert fees.nightly_rates == Decimal("300")  # 3 nights at base price
    assert fees.service_fee == Decimal("50")
    assert fees.early_pickup_fee == Decimal("50")
    assert fees.late_return_fee == Decimal("50")
    assert fees.parking_fee == Decimal("15")  # €5 per night
    assert fees.delivery_fee == Decimal("20")  # 100km delivery


def test_calculate_total_price(sample_pricing_rule: PricingRule):
    """Test calculation of total price."""
    service = PricingService([sample_pricing_rule])

    # Calculate fees first
    fees = service.calculate_fees(
        start_date=date(2024, 6, 3),
        end_date=date(2024, 6, 6),
        pickup_time=time(10, 0),
        return_time=time(17, 0),
        use_parking=True,
        delivery_distance=DeliveryDistance.KM_100,
    )

    # Calculate total price
    total = service.calculate_total_price(fees)
    expected_total = (
        Decimal("300")  # Nightly rates
        + Decimal("50")  # Service fee
        + Decimal("50")  # Early pickup
        + Decimal("50")  # Late return
        + Decimal("15")  # Parking
        + Decimal("20")  # Delivery
    )
    assert total == expected_total


def test_no_pricing_rule():
    """Test behavior when no pricing rule is found."""
    service = PricingService([])

    with pytest.raises(ValueError, match="No pricing rule found for date"):
        service.calculate_nightly_rates(date(2024, 6, 1), date(2024, 6, 3))
