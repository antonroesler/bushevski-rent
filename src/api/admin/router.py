from datetime import date
from decimal import Decimal
from typing import Optional
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import (
    UnauthorizedError,
    BadRequestError,
)
from aws_lambda_powertools import Logger, Tracer
from pydantic import BaseModel, Field, validator

from models import PricingRule, BlockedDates, BlockedReason, BookingStatus
from services import BlockedDatesService
from services.service_registry import ServiceRegistry


logger = Logger()
tracer = Tracer()
router = Router()


def require_api_key():
    """Decorator to check for valid API key"""
    api_key = router.current_event.get_header_value("x-api-key")
    if not api_key:
        logger.warning("No API key provided")
        raise UnauthorizedError("API key is required")

    # In API Gateway, the API key will be in the requestContext if it's valid
    request_context = router.current_event.raw_event.get("requestContext", {})
    identity = request_context.get("identity", {})
    api_key_id = identity.get("apiKey")

    if not api_key_id:
        logger.warning("Invalid API key")
        raise UnauthorizedError("Invalid API key")

    logger.info("API key validated successfully")


class PricingRuleRequest(BaseModel):
    """Request model for creating pricing rules"""

    start_date: date
    end_date: date
    nightly_rate: Decimal = Field(decimal_places=2, gt=0)
    notes: str | None = None

    @validator("start_date")
    def start_date_must_be_future(cls, v):
        if v < date.today():
            raise ValueError("start_date must be in the future")
        return v

    @validator("end_date")
    def end_date_must_be_valid(cls, v, values):
        if "start_date" in values:
            if v < values["start_date"]:
                raise ValueError("end_date must be on or after start_date")
        return v

    class Config:
        json_encoders = {Decimal: str}


class BlockedDatesRequest(BaseModel):
    start_date: date
    end_date: date
    reason: BlockedReason
    notes: Optional[str] = None


class BookingResponse(BaseModel):
    """Response model for bookings list"""

    id: str
    start_date: date
    end_date: date
    status: BookingStatus
    customer_name: str
    customer_email: str
    total_price: str

    class Config:
        json_encoders = {
            date: lambda d: d.isoformat()  # Convert dates to ISO format strings
        }


class UpdateBookingStatusRequest(BaseModel):
    status: BookingStatus


@router.get("/bookings")
@tracer.capture_method
def list_bookings():
    """List all bookings with optional filters"""
    require_api_key()

    try:
        # Get optional query parameters
        start_date = router.current_event.get_query_string_value("start_date")
        end_date = router.current_event.get_query_string_value("end_date")
        status = router.current_event.get_query_string_value("status")

        # Convert dates if provided
        if start_date:
            start_date = date.fromisoformat(start_date)
        if end_date:
            end_date = date.fromisoformat(end_date)

        # Convert status if provided
        if status:
            try:
                status = BookingStatus(status)
            except ValueError:
                raise BadRequestError(
                    f"Invalid status. Must be one of: {', '.join([s.value for s in BookingStatus])}"
                )

        # Get booking service from registry
        booking_service = ServiceRegistry.get("booking")

        # Get bookings with filters
        bookings = booking_service.list_bookings(
            start_date=start_date, end_date=end_date, status=status
        )

        # Convert to response format
        response_bookings = [
            {
                "id": booking.id,
                "start_date": booking.start_date.isoformat(),
                "end_date": booking.end_date.isoformat(),
                "status": booking.status.value,
                "customer": {
                    "name": booking.customer.full_name
                    if booking.customer
                    else "Unknown",
                    "email": booking.customer.email if booking.customer else "Unknown",
                    "phone": booking.customer.phone if booking.customer else None,
                },
                "schedule": {
                    "pickup_time": booking.pickup_time.isoformat(),
                    "return_time": booking.return_time.isoformat(),
                },
                "services": {
                    "parking": booking.parking,
                    "delivery_distance": booking.delivery_distance,
                },
                "pricing": {
                    "nightly_rates": {
                        "breakdown": {
                            date_str: str(rate)
                            for date_str, rate in booking.nightly_rates_breakdown.items()
                        },
                        "total": str(booking.nightly_rates_total),
                    },
                    "fees": {
                        "service_fee": str(booking.service_fee),
                        "parking_fee": str(booking.parking_fee)
                        if booking.parking_fee
                        else None,
                        "delivery_fee": str(booking.delivery_fee)
                        if booking.delivery_fee
                        else None,
                    },
                    "total_price": str(booking.total_price),
                },
            }
            for booking in bookings
        ]

        logger.info(f"Retrieved {len(response_bookings)} bookings")

        return {"bookings": response_bookings, "count": len(response_bookings)}

    except ValueError as e:
        raise BadRequestError(f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing bookings: {str(e)}")
        raise BadRequestError(f"Failed to list bookings: {str(e)}")


@router.put("/bookings/<booking_id>/status")
@tracer.capture_method
def update_booking_status(booking_id: str):
    """Update booking status"""
    require_api_key()

    try:
        # Validate request
        request = UpdateBookingStatusRequest.model_validate(
            router.current_event.json_body
        )

        # Get booking service from registry
        booking_service = ServiceRegistry.get("booking")

        # Get current booking to ensure it exists
        booking = booking_service.get_booking(booking_id)
        if not booking:
            raise BadRequestError(f"Booking {booking_id} not found")

        # Update the status
        updated_booking = booking_service.update_status(booking_id, request.status)

        logger.info(f"Updated booking {booking_id} status to {request.status}")

        return {
            "message": "Status updated successfully",
            "booking_id": booking_id,
            "status": updated_booking.status.value,
            "customer_name": updated_booking.customer.full_name
            if updated_booking.customer
            else "Unknown",
            "start_date": updated_booking.start_date.isoformat(),
            "end_date": updated_booking.end_date.isoformat(),
        }

    except ValueError as e:
        raise BadRequestError(f"Invalid status: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating booking status: {str(e)}")
        raise BadRequestError(f"Failed to update booking status: {str(e)}")


@router.post("/pricing-rules")
@tracer.capture_method
def create_pricing_rule():
    """Create a new pricing rule"""
    require_api_key()

    try:
        # Validate request
        rule_request = PricingRuleRequest.model_validate(router.current_event.json_body)

        # Create PricingRule model
        pricing_rule = PricingRule(
            start_date=rule_request.start_date,
            end_date=rule_request.end_date,
            nightly_rate=rule_request.nightly_rate,
            notes=rule_request.notes,
        )

        # Get pricing service and create rule
        pricing_service = ServiceRegistry.get("pricing")
        created_rule = pricing_service.create_pricing_rule(pricing_rule)

        logger.info(
            f"Created pricing rule {created_rule.id} "
            f"from {created_rule.start_date} to {created_rule.end_date} "
            f"with rate {created_rule.nightly_rate}"
        )

        return {
            "message": "Pricing rule created successfully",
            "id": created_rule.id,
            "start_date": created_rule.start_date.isoformat(),
            "end_date": created_rule.end_date.isoformat(),
            "nightly_rate": str(created_rule.nightly_rate),
            "notes": created_rule.notes,
        }

    except ValueError as e:
        raise BadRequestError(f"Invalid pricing rule: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating pricing rule: {str(e)}")
        raise BadRequestError(f"Failed to create pricing rule: {str(e)}")


@router.get("/pricing-rules")
@tracer.capture_method
def list_pricing_rules():
    """List all pricing rules"""
    require_api_key()

    try:
        # Get pricing service
        pricing_service = ServiceRegistry.get("pricing")

        # Get all rules
        rules = pricing_service.list_pricing_rules()

        # Sort rules by start date and duration
        rules.sort(key=lambda r: (r.start_date, r.duration_days))

        return {
            "rules": [
                {
                    "id": rule.id,
                    "start_date": rule.start_date.isoformat(),
                    "end_date": rule.end_date.isoformat(),
                    "nightly_rate": str(rule.nightly_rate),
                    "duration_days": rule.duration_days,
                    "notes": rule.notes,
                    "created_at": rule.created_at.isoformat(),
                }
                for rule in rules
            ],
            "count": len(rules),
        }

    except Exception as e:
        logger.error(f"Error listing pricing rules: {str(e)}")
        raise BadRequestError(f"Failed to list pricing rules: {str(e)}")


@router.post("/blocked-dates")
@tracer.capture_method
def create_blocked_dates():
    """Block dates from availability"""
    require_api_key()

    try:
        # Validate request
        blocked_request = BlockedDatesRequest.model_validate(
            router.current_event.json_body
        )

        # Create BlockedDates model
        blocked_dates = BlockedDates(
            start_date=blocked_request.start_date,
            end_date=blocked_request.end_date,
            reason=blocked_request.reason,
            notes=blocked_request.notes,
        )

        # Initialize service and create blocked period
        blocked_dates_service = BlockedDatesService()
        created = blocked_dates_service.create_blocked_period(blocked_dates)

        logger.info(
            f"Created blocked period {created.id} from {created.start_date} to {created.end_date}"
        )

        return {
            "message": "Dates blocked successfully",
            "id": created.id,
            "start_date": created.start_date.isoformat(),
            "end_date": created.end_date.isoformat(),
            "reason": created.reason.value,
        }

    except ValueError as e:
        raise BadRequestError(f"Invalid request: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating blocked dates: {str(e)}")
        raise BadRequestError(f"Failed to block dates: {str(e)}")


@router.get("/blocked-dates")
@tracer.capture_method
def list_blocked_dates():
    """List all blocked dates"""
    require_api_key()

    # TODO: Implement blocked dates listing
    return {"blocked_dates": []}


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

        if start >= end:
            raise BadRequestError("Start date must be before end date")

        # Get pricing service
        pricing_service = ServiceRegistry.get("pricing")

        # Get daily rates
        daily_rates = pricing_service.get_daily_rates(start, end)

        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily_rates": {
                date_str: str(rate) for date_str, rate in daily_rates.items()
            },
        }

    except ValueError as e:
        raise BadRequestError(f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting pricing: {str(e)}")
        raise BadRequestError(f"Failed to get pricing: {str(e)}")
