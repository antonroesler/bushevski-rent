from datetime import date, time
from decimal import Decimal
from typing import List, Optional

from models.common import BookingFees, DeliveryDistance, PricingRule


class PricingService:
    def __init__(self, pricing_rules: List[PricingRule]):
        self.pricing_rules = pricing_rules

    def calculate_nightly_rates(self, start_date: date, end_date: date) -> Decimal:
        """Calculate total nightly rates for the booking period.
        Note: The return day (end_date) is not counted in the price."""
        total = Decimal("0")
        current_date = start_date

        while current_date < end_date:  # Don't include end_date
            # Find applicable pricing rule
            rule = next(
                (
                    r
                    for r in self.pricing_rules
                    if r.start_date <= current_date <= r.end_date
                ),
                None,
            )

            if not rule:
                raise ValueError(f"No pricing rule found for date {current_date}")

            # Apply weekend rate (20% higher) for Friday and Saturday stays
            if current_date.weekday() in [4, 5]:  # Friday = 4, Saturday = 5
                total += rule.base_price * Decimal("1.2")
            else:
                total += rule.base_price

            current_date = date.fromordinal(current_date.toordinal() + 1)

        return total

    def validate_minimum_stay(self, start_date: date, end_date: date) -> None:
        """Validate minimum stay requirements based on season."""
        nights = (end_date - start_date).days

        # Find applicable pricing rule
        rule = next(
            (r for r in self.pricing_rules if r.start_date <= start_date <= r.end_date),
            None,
        )

        if not rule:
            raise ValueError(f"No pricing rule found for date {start_date}")

        if nights < rule.min_stay:
            raise ValueError(
                f"Minimum stay requirement not met. Required: {rule.min_stay} nights"
            )

    def calculate_fees(
        self,
        start_date: date,
        end_date: date,
        pickup_time: time,
        return_time: time,
        use_parking: bool = False,
        delivery_distance: DeliveryDistance = DeliveryDistance.NO_DELIVERY,
    ) -> BookingFees:
        """Calculate all fees for a booking."""
        # Calculate number of nights (excluding return day)
        nights = (end_date - start_date).days

        # Calculate nightly rates
        nightly_rates = self.calculate_nightly_rates(start_date, end_date)

        # Initialize fees with service fee
        fees = BookingFees(
            nightly_rates=nightly_rates,
            service_fee=Decimal("50"),  # Fixed service fee
        )

        # Early pickup fee (before 12:00)
        if pickup_time.hour < 12:
            fees.early_pickup_fee = Decimal("50")
        else:
            fees.early_pickup_fee = None

        # Late return fee (after 16:00)
        if return_time.hour >= 16:
            fees.late_return_fee = Decimal("50")
        else:
            fees.late_return_fee = None

        # Parking fee (€5 per night)
        if use_parking:
            fees.parking_fee = Decimal("5") * nights
        else:
            fees.parking_fee = None

        # Delivery fee
        if delivery_distance != DeliveryDistance.NO_DELIVERY:
            fees.delivery_fee = delivery_distance.fee
        else:
            fees.delivery_fee = None

        return fees

    def calculate_total_price(self, fees: BookingFees) -> Decimal:
        """Calculate total price from all fees."""
        total = fees.nightly_rates + fees.service_fee

        if fees.early_pickup_fee:
            total += fees.early_pickup_fee
        if fees.late_return_fee:
            total += fees.late_return_fee
        if fees.parking_fee:
            total += fees.parking_fee
        if fees.delivery_fee:
            total += fees.delivery_fee

        return total
