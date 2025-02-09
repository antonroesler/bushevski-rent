from datetime import date, time, datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from aws_lambda_powertools import Logger, Tracer
from pydantic import BaseModel, validator
from enum import Enum
import os

from models import Booking, Customer, BookingStatus
from services.service_registry import ServiceRegistry
from services.pricing import (
    PARKING_FEE_PER_NIGHT,
    DELIVERY_FEE_PER_KM,
)

logger = Logger()
tracer = Tracer()


router = Router()


class BookingRequest(BaseModel):
    start_date: date
    end_date: date
    pickup_time: time
    return_time: time
    customer: Customer
    parking: bool = False
    delivery_distance: Optional[int] = None

    @validator("start_date")
    def start_date_must_be_future(cls, v):
        today = date.today()
        min_start_date = today + timedelta(days=5)

        if v <= today:
            raise ValueError("Start date must be in the future")
        if v < min_start_date:
            raise ValueError("Bookings must be made at least 5 days in advance")
        return v

    @validator("end_date")
    def end_date_must_be_after_start(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("End date must be after start date")
        return v

    @validator("pickup_time")
    def pickup_time_must_be_after_5am(cls, v):
        earliest_pickup = time(5, 0)  # 5:00 AM
        if v < earliest_pickup:
            raise ValueError("Pickup time must be after 5:00 AM")
        return v

    class Config:
        error_msg_templates = {
            "start_date_must_be_future": "Bookings must start in the future and be made at least 5 days in advance",
            "end_date_must_be_after_start": "End date must be after start date",
            "pickup_time_must_be_after_5am": "Pickup time must be after 5:00 AM",
        }


class BlockedReason(str, Enum):
    BOOKING = "booking"
    MAINTENANCE = "maintenance"
    PRIVATE = "private"
    OTHER = "other"


class BlockedDate(BaseModel):
    date: date
    reason: BlockedReason
    description: Optional[str] = None


class AvailabilityResponse(BaseModel):
    start_date: date
    end_date: date
    blocked_dates: Dict[str, BlockedReason]  # key: date in ISO format, value: reason


class PriceCalculationRequest(BaseModel):
    """Request model for price calculation"""

    start_date: date
    end_date: date
    pickup_time: time
    return_time: time
    parking: bool = False
    delivery_distance: Optional[int] = None

    @validator("start_date")
    def start_date_must_be_future(cls, v):
        if v <= date.today():
            raise ValueError("Start date must be in the future")
        return v

    @validator("end_date")
    def end_date_must_be_after_start(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("End date must be after start date")
        return v

    @validator("pickup_time")
    def validate_pickup_time(cls, v):
        earliest_pickup = time(5, 0)  # 5:00 AM
        if v < earliest_pickup:
            raise ValueError("Pickup time must be after 5:00 AM")
        return v


@router.get("/availability")
@tracer.capture_method
def get_availability():
    """Get availability for a date range"""
    try:
        # Get and validate date parameters
        start = date.fromisoformat(
            router.current_event.get_query_string_value("start_date")
        )
        end = date.fromisoformat(
            router.current_event.get_query_string_value("end_date")
        )

        if start > end:
            raise BadRequestError("Start date must be before end date")

        # Get services from registry
        booking_service = ServiceRegistry.get("booking")
        blocked_dates_service = ServiceRegistry.get("blocked_dates")

        # Get all blocked dates
        blocked_dates = {}

        # Get booked dates
        booked_dates = booking_service.get_booked_dates(start, end)
        for date_str in booked_dates:
            blocked_dates[date_str] = BlockedReason.BOOKING

        # Get admin blocked dates
        admin_blocked = blocked_dates_service.get_blocked_dates_map(start, end)
        blocked_dates.update(admin_blocked)

        return AvailabilityResponse(
            start_date=start, end_date=end, blocked_dates=blocked_dates
        )

    except ValueError as e:
        raise BadRequestError(f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        raise BadRequestError(f"Failed to check availability: {str(e)}")


@router.post("/")
@tracer.capture_method
def create_booking():
    """Create a new booking"""
    try:
        # Validate request
        booking_request = BookingRequest.model_validate(router.current_event.json_body)

        # Get service from registry
        booking_service = ServiceRegistry.get("booking")

        # Check availability
        is_available = booking_service.check_availability(
            booking_request.start_date, booking_request.end_date
        )

        if not is_available:
            raise BadRequestError("Selected dates are not available")

        # Create Booking object with initial empty pricing
        booking = Booking(
            start_date=booking_request.start_date,
            end_date=booking_request.end_date,
            pickup_time=booking_request.pickup_time,
            return_time=booking_request.return_time,
            customer=booking_request.customer,
            status=BookingStatus.PENDING,
            parking=booking_request.parking,
            delivery_distance=booking_request.delivery_distance,
            # Initialize with empty values - will be calculated by service
            nightly_rates_breakdown={},
            nightly_rates_total=Decimal("0"),
            service_fee=Decimal("0"),
            parking_fee=None,
            delivery_fee=None,
            total_price=Decimal("0"),
        )

        # Create booking in database (this will calculate and set the correct prices)
        created_booking = booking_service.create_booking(booking)

        logger.info(
            f"Created booking {created_booking.id} with total price {created_booking.total_price}"
        )

        return {
            "message": "Booking created successfully",
            "booking_id": created_booking.id,
            "status": created_booking.status.value,
            "total_price": str(created_booking.total_price),
            "price_breakdown": {
                "nightly_rates": {
                    "breakdown": {
                        date_str: str(rate)
                        for date_str, rate in created_booking.nightly_rates_breakdown.items()
                    },
                    "total": str(created_booking.nightly_rates_total),
                },
                "fees": {
                    "service_fee": str(created_booking.service_fee),
                    "parking_fee": str(created_booking.parking_fee)
                    if created_booking.parking_fee
                    else None,
                    "delivery_fee": str(created_booking.delivery_fee)
                    if created_booking.delivery_fee
                    else None,
                },
            },
        }

    except Exception as e:
        logger.error(f"Error creating booking: {str(e)}")
        raise BadRequestError(f"Failed to create booking: {str(e)}")


@router.put("/<booking_id>/drivers-license")
@tracer.capture_method
def upload_drivers_license(booking_id: str):
    """Upload driver's license for booking"""
    # TODO: Implement file upload to S3
    return {"message": "License uploaded successfully"}


@router.get("/pricing")
@tracer.capture_method
def get_pricing():
    """Get pricing for a date range"""
    try:
        # Get and validate date parameters
        start = date.fromisoformat(
            router.current_event.get_query_string_value("start_date")
        )
        end = date.fromisoformat(
            router.current_event.get_query_string_value("end_date")
        )

        if start > end:
            raise BadRequestError("Start date must be before end date")

        # Get pricing service from registry
        pricing_service = ServiceRegistry.get("pricing")

        # Get daily rates
        daily_rates = pricing_service.get_daily_rates(start, end)

        # Format response - only include nightly rates
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily_rates": {
                date_str: str(rate) for date_str, rate in daily_rates.items()
            },
            "fees": {
                "parking_fee_per_night": str(PARKING_FEE_PER_NIGHT),
                "delivery_fee_per_km": str(DELIVERY_FEE_PER_KM),
            },
        }

    except ValueError as e:
        raise BadRequestError(f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting pricing: {str(e)}")
        raise BadRequestError(f"Failed to get pricing: {str(e)}")


@router.post("/calculate-price")
@tracer.capture_method
def calculate_price():
    """Calculate price for a potential booking"""
    try:
        # Validate request
        request = PriceCalculationRequest.model_validate(router.current_event.json_body)

        # Get pricing service
        pricing_service = ServiceRegistry.get("pricing")

        # Calculate price
        price_calculation = pricing_service.calculate_price(
            start_date=request.start_date,
            end_date=request.end_date,
            pickup_time=request.pickup_time,
            return_time=request.return_time,
            parking=request.parking,
            delivery_distance=request.delivery_distance,
        )

        # Format response
        return {
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "pickup_time": request.pickup_time.isoformat(),
            "return_time": request.return_time.isoformat(),
            "nights": (request.end_date - request.start_date).days,
            "pricing": {
                "nightly_rates": {
                    "breakdown": {
                        date_str: str(rate)
                        for date_str, rate in price_calculation[
                            "daily_breakdown"
                        ].items()
                    },
                    "total": str(price_calculation["nightly_rates"]),
                },
                "fees": {
                    "service_fee": str(price_calculation["service_fee"]),
                    "parking_fee": str(price_calculation["parking_fee"])
                    if request.parking
                    else None,
                    "delivery_fee": str(price_calculation["delivery_fee"])
                    if request.delivery_distance
                    else None,
                    "time_fees": {
                        k: str(v) for k, v in price_calculation["time_fees"].items()
                    }
                    if price_calculation["time_fees"]
                    else None,
                },
                "total_price": str(price_calculation["total_price"]),
            },
        }

    except ValueError as e:
        raise BadRequestError(f"Invalid request: {str(e)}")
    except Exception as e:
        logger.error(f"Error calculating price: {str(e)}")
        raise BadRequestError(f"Failed to calculate price: {str(e)}")


@router.post("/<booking_id>/payment-intent")
@tracer.capture_method
def create_payment_intent(booking_id: str):
    """Create a payment intent for a booking"""
    try:
        # Get booking service and verify booking exists
        booking_service = ServiceRegistry.get("booking")
        booking = booking_service.get_booking(booking_id)
        if not booking:
            raise BadRequestError(f"Booking {booking_id} not found")

        # Verify booking is in pending status
        if booking.status != BookingStatus.PENDING:
            raise BadRequestError(
                f"Cannot create payment for booking in {booking.status} status"
            )

        # Get payment service
        payment_service = ServiceRegistry.get("payment")

        # Create payment intent
        payment_intent = payment_service.create_payment_intent(
            amount=booking.total_price,
            booking_id=booking_id,
            customer_email=booking.customer.email if booking.customer else None,
        )

        return {
            "booking_id": booking_id,
            "payment": {
                "client_secret": payment_intent["client_secret"],
                "amount": str(booking.total_price),
                "currency": "eur",
            },
        }

    except ValueError as e:
        raise BadRequestError(f"Invalid request: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating payment intent: {str(e)}")
        raise BadRequestError(f"Failed to create payment intent: {str(e)}")


@router.post("/<booking_id>/drivers-license/upload-url")
@tracer.capture_method
def get_license_upload_url(booking_id: str):
    """Get a presigned URL for uploading a driver's license"""
    try:
        # Get booking service and verify booking exists
        booking_service = ServiceRegistry.get("booking")
        booking = booking_service.get_booking(booking_id)
        if not booking:
            raise BadRequestError(f"Booking {booking_id} not found")

        # Get filename from request
        request = router.current_event.json_body
        filename = request.get("filename")
        if not filename:
            raise BadRequestError("Filename is required")

        # Generate S3 key
        file_extension = os.path.splitext(filename)[1].lower()
        if file_extension not in [".jpg", ".jpeg", ".png", ".pdf"]:
            raise BadRequestError("Invalid file type. Allowed: jpg, jpeg, png, pdf")

        s3_key = f"licenses/{booking_id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{file_extension}"

        # Get storage service and generate upload URL
        storage_service = ServiceRegistry.get("storage")
        upload_url = storage_service.generate_presigned_url(s3_key)

        # Update booking with pending upload info
        booking_service.update_license_info(booking_id, filename, s3_key)

        return {
            "upload_url": upload_url,
            "key": s3_key,
            "expires_in": 3600,  # 1 hour
        }

    except Exception as e:
        logger.error(f"Error generating upload URL: {str(e)}")
        raise BadRequestError(f"Failed to generate upload URL: {str(e)}")
