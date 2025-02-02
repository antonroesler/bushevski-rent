from datetime import datetime
from uuid import uuid4

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from models.common import Booking, BookingResponse, BookingStatus, CreateBookingRequest, Customer
from utils.dynamodb import BookingRepository, CustomerRepository, PricingRuleRepository, get_table
from utils.email import EmailService
from utils.middleware import create_response, handle_errors, parse_body
from utils.pricing import PricingService

logger = Logger()
tracer = Tracer()


@tracer.capture_lambda_handler
@handle_errors
@parse_body(CreateBookingRequest)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Create a new booking."""
    # Get request data
    booking_request: CreateBookingRequest = event["parsed_body"]

    # Get DynamoDB table
    table = get_table()

    # Initialize repositories
    booking_repo = BookingRepository(table)
    customer_repo = CustomerRepository(table)
    pricing_repo = PricingRuleRepository(table)

    # Check for existing bookings in the date range
    existing_bookings = booking_repo.get_by_date_range(
        booking_request.start_date, booking_request.end_date, BookingStatus.CONFIRMED
    )

    if existing_bookings:
        return create_response(
            409,
            {"error": "Date conflict", "message": "Selected dates are not available"},
        )

    # Get pricing rules
    pricing_rules = pricing_repo.get_by_date_range(
        booking_request.start_date, booking_request.end_date
    )

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
        # Validate minimum stay
        pricing_service.validate_minimum_stay(
            booking_request.start_date, booking_request.end_date
        )

        # Calculate fees
        fees = pricing_service.calculate_fees(
            booking_request.start_date,
            booking_request.end_date,
            booking_request.pickup_time,
            booking_request.return_time,
            booking_request.use_parking,
            booking_request.delivery_distance,
        )

        # Calculate total price
        total_price = pricing_service.calculate_total_price(fees)

    except ValueError as e:
        return create_response(400, {"error": "Validation error", "message": str(e)})

    # Create or update customer
    customer = Customer(
        id=uuid4(),
        **booking_request.customer.model_dump(),
        drivers_license_url=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    customer_repo.create(customer)

    # Create booking
    booking = Booking(
        id=uuid4(),
        status=BookingStatus.PENDING,
        customer_id=customer.id,
        fees=fees,
        total_price=total_price,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        **booking_request.model_dump(exclude={"customer"}),
    )
    booking_repo.create(booking)

    # Send confirmation email
    email_service = EmailService()
    try:
        email_service.send_booking_confirmation(booking, customer)
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {str(e)}")
        # Don't fail the booking creation if email fails

    # Create response
    response = BookingResponse(**booking.model_dump(), customer=customer)

    return create_response(201, response)
