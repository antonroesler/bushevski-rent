import json
from uuid import UUID

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from utils.dynamodb import BookingRepository, CustomerRepository, get_table
from utils.middleware import create_response, handle_errors
from utils.storage import StorageService

logger = Logger()
tracer = Tracer()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}


@tracer.capture_lambda_handler
@handle_errors
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Upload driver's license for a booking."""
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
        file_content = body["file_content"]  # Base64 encoded file
        content_type = body["content_type"]
    except (json.JSONDecodeError, KeyError):
        return create_response(
            400,
            {
                "error": "Invalid request",
                "message": "Request must include file_content and content_type",
            },
        )

    # Validate content type
    if content_type not in ALLOWED_CONTENT_TYPES:
        return create_response(
            400,
            {
                "error": "Invalid content type",
                "message": f"Content type must be one of: {', '.join(ALLOWED_CONTENT_TYPES)}",
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

    # Upload file to S3
    storage = StorageService()
    try:
        key = storage.upload_drivers_license(
            booking_id=booking_id,
            customer_email=customer.email,
            file_content=file_content,
            file_type=content_type,
        )
    except ValueError as e:
        return create_response(400, {"error": "Upload failed", "message": str(e)})
    except Exception as e:
        logger.error(f"Failed to upload file: {e!s}")
        return create_response(
            500,
            {"error": "Upload failed", "message": "Failed to upload driver's license"},
        )

    # Update customer record with file URL
    customer_repo.update_drivers_license(customer.email, key)

    return create_response(
        200, {"message": "Driver's license uploaded successfully", "file_key": key}
    )
