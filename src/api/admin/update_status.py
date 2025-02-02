import json
from uuid import UUID

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from models.common import BookingResponse, BookingStatus
from utils.dynamodb import BookingRepository, CustomerRepository, get_table
from utils.email import EmailService
from utils.middleware import create_response, handle_errors, require_admin

logger = Logger()
tracer = Tracer()


@tracer.capture_lambda_handler
@handle_errors
@require_admin
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Update booking status."""
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

    # Parse request body
    try:
        body = json.loads(event["body"])
        new_status = BookingStatus(body["status"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return create_response(
            400,
            {
                "error": "Invalid request",
                "message": "Request must include valid status",
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

    # Store old status for email notification
    old_status = booking.status

    # Update booking status
    booking_repo.update_status(booking_id, new_status)
    booking.status = new_status

    # Send email notification
    email_service = EmailService()
    try:
        email_service.send_booking_status_update(booking, customer, old_status.value)
    except Exception as e:
        logger.error(f"Failed to send status update email: {e!s}")
        # Don't fail the status update if email fails

    # Create response
    response = BookingResponse(**booking.model_dump(), customer=customer)

    return create_response(200, response)
