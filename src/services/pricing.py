from datetime import date, time, timedelta
from decimal import Decimal
from typing import List, Optional, Dict
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from services.base import BaseService
from models import PricingRule

logger = Logger()

DEFAULT_NIGHTLY_RATE = Decimal("100.00")
SERVICE_FEE = Decimal("50.00")
PARKING_FEE_PER_NIGHT = Decimal("5.00")
DELIVERY_FEE_PER_KM = Decimal("0.20")

# New constants for time-based fees
EARLY_PICKUP_FEE = Decimal("50.00")
LATE_RETURN_FEE = Decimal("50.00")
EARLY_PICKUP_THRESHOLD = time(12, 0)  # 12:00 noon
LATE_RETURN_THRESHOLD = time(16, 0)  # 4:00 PM


class PricingService(BaseService):
    """Service for managing pricing rules and calculating booking costs"""

    def create_pricing_rule(self, rule: PricingRule) -> PricingRule:
        """Create a new pricing rule"""
        try:
            rule_data = rule.dict_for_dynamo()
            rule_data["PK"] = f"PRICING_RULE#{rule_data['id']}"
            rule_data["SK"] = f"PRICING_RULE#{rule_data['id']}"
            rule_data["GSI1PK"] = "PRICING_RULE"
            rule_data["GSI1SK"] = f"DATE#{rule.start_date.isoformat()}"

            self._create_item(rule_data)
            return rule
        except ClientError as e:
            logger.error(f"Error creating pricing rule: {str(e)}")
            raise

    def get_pricing_rule(self, rule_id: str) -> Optional[PricingRule]:
        """Get a pricing rule by ID"""
        try:
            item = self._get_item(
                {"PK": f"PRICING_RULE#{rule_id}", "SK": f"PRICING_RULE#{rule_id}"}
            )
            return PricingRule.from_dynamo(item) if item else None
        except ClientError as e:
            logger.error(f"Error getting pricing rule: {str(e)}")
            raise

    def list_pricing_rules(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[PricingRule]:
        """List pricing rules with optional date range filter"""
        try:
            expression_values = {":pk": "PRICING_RULE"}
            filter_expressions = []

            if start_date:
                expression_values[":start_date"] = start_date.isoformat()
                filter_expressions.append("start_date >= :start_date")

            if end_date:
                expression_values[":end_date"] = end_date.isoformat()
                filter_expressions.append("end_date <= :end_date")

            items = self._query(
                key_condition_expression="GSI1PK = :pk",
                expression_values=expression_values,
                index_name="GSI1",
                filter_expression=" AND ".join(filter_expressions)
                if filter_expressions
                else None,
            )

            return [PricingRule.from_dynamo(item) for item in items]
        except ClientError as e:
            logger.error(f"Error listing pricing rules: {str(e)}")
            raise

    def get_daily_rates(self, start_date: date, end_date: date) -> Dict[str, Decimal]:
        """Get nightly rates for each date in range"""
        try:
            # Get all pricing rules that overlap with the date range
            rules = self._query(
                key_condition_expression="GSI1PK = :pk",
                expression_values={
                    ":pk": "PRICING_RULE",
                    ":start": start_date.isoformat(),
                    ":end": end_date.isoformat(),
                },
                index_name="GSI1",
                filter_expression="start_date <= :end AND end_date >= :start",
            )

            # Convert to PricingRule objects
            rules = [PricingRule.from_dynamo(rule) for rule in rules]

            # Create a map of date -> price
            daily_rates = {}
            current_date = start_date

            while current_date < end_date:  # Note: < not <= since last day is checkout
                date_str = current_date.isoformat()

                # Find applicable rules for this date
                applicable_rules = [
                    rule
                    for rule in rules
                    if rule.start_date <= current_date <= rule.end_date
                ]

                if applicable_rules:
                    # Sort rules by duration and creation date
                    selected_rule = sorted(
                        applicable_rules,
                        key=lambda r: (r.duration_days, -r.created_at.timestamp()),
                    )[0]
                    daily_rates[date_str] = selected_rule.nightly_rate

                    # Add debug logging
                    logger.debug(
                        f"Selected rule for {date_str}: "
                        f"ID={selected_rule.id}, "
                        f"duration={selected_rule.duration_days} days, "
                        f"rate={selected_rule.nightly_rate}, "
                        f"created={selected_rule.created_at.isoformat()}"
                    )

                    if len(applicable_rules) > 1:
                        logger.debug(
                            f"Other applicable rules for {date_str}: "
                            + ", ".join(
                                [
                                    f"(ID={r.id}, duration={r.duration_days}, created={r.created_at.isoformat()})"
                                    for r in applicable_rules[1:]
                                ]
                            )
                        )
                else:
                    daily_rates[date_str] = DEFAULT_NIGHTLY_RATE
                    logger.debug(f"No rules found for {date_str}, using default rate")

                current_date += timedelta(days=1)

            return daily_rates

        except Exception as e:
            logger.error(f"Error getting daily rates: {str(e)}")
            raise

    def calculate_price(
        self,
        start_date: date,
        end_date: date,
        pickup_time: time,
        return_time: time,
        parking: bool = False,
        delivery_distance: Optional[int] = None,
    ) -> dict:
        """Calculate total price for a booking"""
        try:
            # Get nightly rates for the booking period
            daily_rates = self.get_daily_rates(start_date, end_date)

            # Sum up nightly rates (excluding last day which is checkout)
            base_price = sum(daily_rates[date_str] for date_str in daily_rates)

            # Calculate nights for additional fees
            nights = (end_date - start_date).days

            # Calculate time-based fees
            time_fees = Decimal("0")
            time_fees_breakdown = {}

            if pickup_time < EARLY_PICKUP_THRESHOLD:
                time_fees += EARLY_PICKUP_FEE
                time_fees_breakdown["early_pickup_fee"] = EARLY_PICKUP_FEE

            if return_time > LATE_RETURN_THRESHOLD:
                time_fees += LATE_RETURN_FEE
                time_fees_breakdown["late_return_fee"] = LATE_RETURN_FEE

            # Calculate other fees
            parking_fee = PARKING_FEE_PER_NIGHT * nights if parking else Decimal("0")
            delivery_fee = (
                DELIVERY_FEE_PER_KM * delivery_distance
                if delivery_distance
                else Decimal("0")
            )

            total_price = (
                base_price + parking_fee + delivery_fee + SERVICE_FEE + time_fees
            )

            return {
                "nightly_rates": base_price,
                "parking_fee": parking_fee,
                "delivery_fee": delivery_fee,
                "service_fee": SERVICE_FEE,
                "time_fees": time_fees_breakdown,
                "total_price": total_price,
                "daily_breakdown": daily_rates,
            }

        except Exception as e:
            logger.error(f"Error calculating price: {str(e)}")
            raise
