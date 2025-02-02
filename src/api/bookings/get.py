from uuid import UUID

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from models.common import BookingResponse
from utils.dynamodb import BookingRepository, CustomerRepository, get_table
from utils.middleware import create_response, handle_errors

logger = Logger()
tracer = Tracer()


@tracer.capture_lambda_handler
@handle_errors
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Get booking details by ID."""
    # Get booking ID from path parameters
    try:
        booking_id = UUID(event["pathParameters"]["id"])
    except (KeyError, ValueError, TypeError):
        return create_response(
            400,
            {
                "error": "Invalid booking ID",
                "message": "Booking ID must be a valid UUID",
            },
        )

    # Get DynamoDB table
    table = get_table()

    # Initialize repositories
    booking_repo = BookingRepository(table)
    customer_repo = CustomerRepository(table)

    # Get booking
    booking = booking_repo.get(booking_id)
    if not booking:
        return create_response(404, {"error": "Not found", "message": "Booking not found"})

    # Get customer
    customer = customer_repo.get(booking.customer_id)
    if not customer:
        logger.error(f"Customer {booking.customer_id} not found for booking {booking_id}")
        return create_response(
            500,
            {"error": "Internal server error", "message": "Customer data not found"},
        )

    # Create response
    response = BookingResponse(**booking.model_dump(), customer=customer)

    return create_response(200, response)
