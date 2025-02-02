from datetime import date, datetime
from typing import Optional

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from models.common import BookingResponse, BookingStatus
from utils.dynamodb import BookingRepository, CustomerRepository, get_table
from utils.middleware import create_response, handle_errors, require_admin

logger = Logger()
tracer = Tracer()


@tracer.capture_lambda_handler
@handle_errors
@require_admin
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """List bookings with optional filters."""
    # Parse query parameters
    params = event.get("queryStringParameters", {}) or {}

    try:
        # Parse dates if provided
        start_date = (
            date.fromisoformat(params["start_date"]) if "start_date" in params else None
        )
        end_date = (
            date.fromisoformat(params["end_date"]) if "end_date" in params else None
        )

        # Parse status if provided
        status = BookingStatus(params["status"]) if "status" in params else None

    except (ValueError, TypeError):
        return create_response(
            400,
            {"error": "Invalid parameters", "message": "Invalid date format or status"},
        )

    # Get DynamoDB table
    table = get_table()

    # Initialize repositories
    booking_repo = BookingRepository(table)
    customer_repo = CustomerRepository(table)

    # If no date range provided, use current month
    if not start_date or not end_date:
        today = date.today()
        start_date = date(today.year, today.month, 1)
        # Use last day of current month
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1)
        else:
            end_date = date(today.year, today.month + 1, 1)

    # Get bookings
    bookings = booking_repo.get_by_date_range(start_date, end_date, status)

    # Get customers for all bookings
    customer_map = {}
    for booking in bookings:
        if booking.customer_id not in customer_map:
            customer = customer_repo.get(booking.customer_id)
            if customer:
                customer_map[booking.customer_id] = customer

    # Create response objects
    responses = []
    for booking in bookings:
        customer = customer_map.get(booking.customer_id)
        if customer:
            responses.append(BookingResponse(**booking.model_dump(), customer=customer))
        else:
            logger.error(
                f"Customer {booking.customer_id} not found for booking {booking.id}"
            )

    return create_response(
        200,
        {
            "bookings": [response.model_dump() for response in responses],
            "count": len(responses),
            "filters": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "status": status.value if status else None,
            },
        },
    )
