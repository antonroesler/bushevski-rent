from datetime import date

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from models.common import BookingStatus
from utils.dynamodb import (
    BlockedDateRepository,
    BookingRepository,
    PricingRuleRepository,
    get_table,
)
from utils.middleware import create_response, handle_errors
from utils.pricing import PricingService

logger = Logger()
tracer = Tracer()


@tracer.capture_lambda_handler
@handle_errors
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Check availability and pricing for a date range."""
    # Parse query parameters
    params = event.get("queryStringParameters", {}) or {}
    try:
        start_date = date.fromisoformat(params.get("start_date", ""))
        end_date = date.fromisoformat(params.get("end_date", ""))
    except (ValueError, TypeError):
        return create_response(
            400,
            {
                "error": "Invalid date format",
                "message": "Dates must be in YYYY-MM-DD format",
            },
        )

    if start_date >= end_date:
        return create_response(
            400,
            {
                "error": "Invalid date range",
                "message": "End date must be after start date",
            },
        )

    # Get DynamoDB table
    table = get_table()

    # Initialize repositories
    booking_repo = BookingRepository(table)
    blocked_repo = BlockedDateRepository(table)
    pricing_repo = PricingRuleRepository(table)

    # Get existing bookings
    existing_bookings = booking_repo.get_by_date_range(
        start_date, end_date, BookingStatus.CONFIRMED
    )

    # Get blocked dates
    blocked_dates = blocked_repo.get_by_date_range(start_date, end_date)

    # Get pricing rules
    pricing_rules = pricing_repo.get_by_date_range(start_date, end_date)

    if not pricing_rules:
        return create_response(
            400,
            {
                "error": "No pricing available",
                "message": "No pricing rules found for the selected dates",
            },
        )

    # Initialize pricing service
    pricing_service = PricingService(pricing_rules)

    try:
        # Check minimum stay requirement
        pricing_service.validate_minimum_stay(start_date, end_date)
    except ValueError as e:
        return create_response(400, {"error": "Invalid stay duration", "message": str(e)})

    # Calculate base price
    try:
        nightly_rates = pricing_service.calculate_nightly_rates(start_date, end_date)
    except ValueError as e:
        return create_response(400, {"error": "Pricing error", "message": str(e)})

    # Check availability
    is_available = True
    unavailable_dates = []

    # Check existing bookings
    for booking in existing_bookings:
        if (start_date <= booking.end_date and end_date >= booking.start_date) or (
            booking.start_date <= end_date and booking.end_date >= start_date
        ):
            is_available = False
            unavailable_dates.extend(
                [d.isoformat() for d in booking.get_dates() if start_date <= d <= end_date]
            )

    # Check blocked dates
    for blocked in blocked_dates:
        if (start_date <= blocked.end_date and end_date >= blocked.start_date) or (
            blocked.start_date <= end_date and blocked.end_date >= start_date
        ):
            is_available = False
            unavailable_dates.extend(
                [d.isoformat() for d in blocked.get_dates() if start_date <= d <= end_date]
            )

    return create_response(
        200,
        {
            "is_available": is_available,
            "unavailable_dates": sorted(set(unavailable_dates)),
            "nightly_rates": str(nightly_rates),
            "service_fee": "50.00",
            "minimum_stay": pricing_rules[0].min_stay,
            "pricing_rules": [
                {
                    "start_date": rule.start_date.isoformat(),
                    "end_date": rule.end_date.isoformat(),
                    "base_price": str(rule.base_price),
                    "min_stay": rule.min_stay,
                }
                for rule in pricing_rules
            ],
        },
    )
