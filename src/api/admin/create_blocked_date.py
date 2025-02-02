from datetime import datetime
from uuid import uuid4

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel

from models.common import BlockedDate, BlockedDateReason
from utils.dynamodb import BlockedDateRepository, BookingRepository, get_table
from utils.middleware import create_response, handle_errors, parse_body, require_admin

logger = Logger()
tracer = Tracer()


class CreateBlockedDateRequest(BaseModel):
    """Request model for creating a blocked date."""

    start_date: str
    end_date: str
    reason: BlockedDateReason
    notes: str = None


@tracer.capture_lambda_handler
@handle_errors
@require_admin
@parse_body(CreateBlockedDateRequest)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Create a new blocked date period."""
    # Get request data
    request: CreateBlockedDateRequest = event["parsed_body"]

    try:
        # Parse dates
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d").date()
    except ValueError as e:
        return create_response(
            400,
            {
                "error": "Invalid date format",
                "message": "Dates must be in YYYY-MM-DD format",
            },
        )

    # Validate date range
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
    blocked_repo = BlockedDateRepository(table)
    booking_repo = BookingRepository(table)

    # Check for existing bookings in the date range
    existing_bookings = booking_repo.get_by_date_range(start_date, end_date)
    if existing_bookings:
        return create_response(
            409,
            {
                "error": "Date conflict",
                "message": "There are existing bookings in this date range",
            },
        )

    # Check for overlapping blocked dates
    existing_blocked = blocked_repo.get_by_date_range(start_date, end_date)
    if existing_blocked:
        return create_response(
            409,
            {
                "error": "Date conflict",
                "message": "This date range overlaps with existing blocked dates",
            },
        )

    # Create blocked date
    blocked_date = BlockedDate(
        id=uuid4(),
        start_date=start_date,
        end_date=end_date,
        reason=request.reason,
        notes=request.notes,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    blocked_repo.create(blocked_date)

    return create_response(201, blocked_date)
