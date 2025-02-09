from datetime import date, datetime, timedelta
from typing import List, Optional
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from services.base import BaseService
from models import Booking, Customer, BookingStatus
from services.service_registry import ServiceRegistry

logger = Logger()


class BookingService(BaseService):
    """Service for handling booking operations"""

    def __init__(self):
        super().__init__()
        # Don't load services in constructor to avoid circular imports

    def _get_blocked_dates_service(self):
        """Get blocked dates service lazily"""
        return ServiceRegistry.get("blocked_dates")

    def create_booking(self, booking: Booking) -> Booking:
        """Create a new booking"""
        try:
            # Calculate correct pricing using PricingService
            pricing_service = ServiceRegistry.get("pricing")
            price_calculation = pricing_service.calculate_price(
                start_date=booking.start_date,
                end_date=booking.end_date,
                pickup_time=booking.pickup_time,
                return_time=booking.return_time,
                parking=booking.parking,
                delivery_distance=booking.delivery_distance,
            )

            # Update booking with calculated prices
            booking.nightly_rates_breakdown = price_calculation["daily_breakdown"]
            booking.nightly_rates_total = price_calculation["nightly_rates"]
            booking.service_fee = price_calculation["service_fee"]
            booking.parking_fee = (
                price_calculation["parking_fee"] if booking.parking else None
            )
            booking.delivery_fee = (
                price_calculation["delivery_fee"] if booking.delivery_distance else None
            )
            booking.total_price = price_calculation["total_price"]

            # First create the customer
            customer_data = booking.customer.dict_for_dynamo()
            customer_data["PK"] = f"CUSTOMER#{customer_data['id']}"
            customer_data["SK"] = f"PROFILE#{customer_data['id']}"
            customer_data["GSI1PK"] = "CUSTOMER"
            customer_data["GSI1SK"] = f"EMAIL#{booking.customer.email}"
            self._create_item(customer_data)

            # Then create the booking
            booking_data = booking.dict_for_dynamo()
            booking_data["PK"] = f"BOOKING#{booking_data['id']}"
            booking_data["SK"] = f"BOOKING#{booking_data['id']}"
            booking_data["GSI1PK"] = "BOOKING"
            booking_data["GSI1SK"] = f"DATE#{booking.start_date.isoformat()}"
            booking_data["customer_id"] = customer_data["id"]
            self._create_item(booking_data)

            return booking

        except Exception as e:
            logger.error(f"Error creating booking: {str(e)}")
            raise

    def get_booking(self, booking_id: str) -> Optional[Booking]:
        """Get a booking by ID"""
        try:
            item = self._get_item(
                {"PK": f"BOOKING#{booking_id}", "SK": f"BOOKING#{booking_id}"}
            )
            if not item:
                return None

            # Get the customer data
            customer_item = self._get_item(
                {
                    "PK": f"CUSTOMER#{item['customer_id']}",
                    "SK": f"PROFILE#{item['customer_id']}",
                }
            )

            if customer_item:
                item["customer"] = Customer.from_dynamo(customer_item)

            return Booking.from_dynamo(item)
        except ClientError as e:
            logger.error(f"Error getting booking: {str(e)}")
            raise

    def update_booking_status(self, booking_id: str, status: BookingStatus) -> Booking:
        """Update booking status"""
        try:
            updated = self._update_item(
                key={"PK": f"BOOKING#{booking_id}", "SK": f"BOOKING#{booking_id}"},
                update_expression="SET #status = :status, updated_at = :updated_at",
                expression_values={
                    ":status": status.value,
                    ":updated_at": datetime.utcnow().isoformat(),
                },
                condition_expression="attribute_exists(PK)",
            )
            return Booking.from_dynamo(updated)
        except ClientError as e:
            logger.error(f"Error updating booking status: {str(e)}")
            raise

    def list_bookings(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[BookingStatus] = None,
    ) -> List[Booking]:
        """List bookings with optional filters"""
        try:
            # Query by date range if provided
            if start_date:
                expression_values = {":pk": "BOOKING"}
                filter_expressions = []

                if start_date:
                    expression_values[":start_date"] = start_date.isoformat()
                    filter_expressions.append("start_date >= :start_date")

                if end_date:
                    expression_values[":end_date"] = end_date.isoformat()
                    filter_expressions.append("end_date <= :end_date")

                if status:
                    expression_values[":status"] = status.value
                    filter_expressions.append("#status = :status")

                items = self._query(
                    key_condition_expression="GSI1PK = :pk",
                    expression_values=expression_values,
                    index_name="GSI1",
                    filter_expression=" AND ".join(filter_expressions)
                    if filter_expressions
                    else None,
                )
            else:
                # If no date range, query all bookings
                items = self._query(
                    key_condition_expression="GSI1PK = :pk",
                    expression_values={":pk": "BOOKING"},
                    index_name="GSI1",
                )

            # Convert items to Booking objects
            bookings = []
            for item in items:
                # Get customer data for each booking
                customer_item = self._get_item(
                    {
                        "PK": f"CUSTOMER#{item['customer_id']}",
                        "SK": f"PROFILE#{item['customer_id']}",
                    }
                )
                if customer_item:
                    item["customer"] = Customer.from_dynamo(customer_item)
                bookings.append(Booking.from_dynamo(item))

            return bookings
        except ClientError as e:
            logger.error(f"Error listing bookings: {str(e)}")
            raise

    def check_availability(self, start_date: date, end_date: date) -> bool:
        """Check if dates are available for booking"""
        try:
            # Check for any overlapping bookings
            # A booking overlaps if:
            # - it starts before our end date AND
            # - it ends after our start date
            booking_items = self._query(
                key_condition_expression="GSI1PK = :pk",
                expression_values={
                    ":pk": "BOOKING",
                    ":cancelled": BookingStatus.CANCELLED.value,
                    ":start_date": start_date.isoformat(),
                    ":end_date": end_date.isoformat(),
                },
                index_name="GSI1",
                filter_expression=(
                    "(attribute_not_exists(#status) OR #status <> :cancelled) AND "
                    "start_date <= :end_date AND end_date >= :start_date"
                ),
                expression_attribute_names={"#status": "status"},
            )

            if len(booking_items) > 0:
                logger.info("Dates not available - existing booking found")
                return False

            # Check blocked dates
            blocked_dates_service = self._get_blocked_dates_service()
            blocked_dates = blocked_dates_service.get_blocked_dates(
                start_date, end_date
            )

            if blocked_dates:
                logger.info(
                    f"Dates not available - blocked dates found: {[b.reason for b in blocked_dates]}"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            raise

    def get_booked_dates(self, start_date: date, end_date: date) -> List[str]:
        """Get all booked dates within a date range"""
        try:
            # Query bookings in the date range
            items = self._query(
                key_condition_expression="GSI1PK = :pk AND GSI1SK BETWEEN :start AND :end",
                expression_values={
                    ":pk": "BOOKING",
                    ":start": f"DATE#{start_date.isoformat()}",
                    ":end": f"DATE#{end_date.isoformat()}",
                    ":cancelled": BookingStatus.CANCELLED.value,
                },
                index_name="GSI1",
                filter_expression="attribute_not_exists(#status) OR #status <> :cancelled",
                expression_attribute_names={"#status": "status"},
            )

            # For each booking, get all dates between start and end
            booked_dates = set()  # Using set to avoid duplicates
            for item in items:
                booking_start = date.fromisoformat(item["start_date"])
                booking_end = date.fromisoformat(item["end_date"])

                # Add each date in the booking range
                current_date = booking_start
                while current_date <= booking_end:
                    booked_dates.add(current_date.isoformat())
                    current_date += timedelta(days=1)

            return sorted(list(booked_dates))  # Convert to sorted list before returning

        except Exception as e:
            logger.error(f"Error getting booked dates: {str(e)}")
            raise

    def update_status(self, booking_id: str, new_status: BookingStatus) -> Booking:
        """Update a booking's status"""
        try:
            # Get current booking
            booking = self.get_booking(booking_id)
            if not booking:
                raise ValueError(f"Booking {booking_id} not found")

            # Update the status using expression attribute name for reserved word 'status'
            update_expression = "SET #s = :status, updated_at = :updated_at"
            expression_values = {
                ":status": new_status.value,
                ":updated_at": datetime.utcnow().isoformat(),
            }
            expression_attribute_names = {"#s": "status"}

            self._update_item(
                key={"PK": f"BOOKING#{booking_id}", "SK": f"BOOKING#{booking_id}"},
                update_expression=update_expression,
                expression_values=expression_values,
                expression_attribute_names=expression_attribute_names,
            )

            # Get and return updated booking
            return self.get_booking(booking_id)

        except Exception as e:
            logger.error(f"Error updating booking status: {str(e)}")
            raise

    def update_license_info(
        self, booking_id: str, filename: str, s3_key: str
    ) -> Booking:
        """Update booking with driver's license info"""
        try:
            # Update the booking with license info
            update_expression = """
                SET drivers_license_key = :key,
                    drivers_license_filename = :filename,
                    drivers_license_uploaded_at = :uploaded_at,
                    updated_at = :updated_at
            """
            expression_values = {
                ":key": s3_key,
                ":filename": filename,
                ":uploaded_at": datetime.utcnow().isoformat(),
                ":updated_at": datetime.utcnow().isoformat(),
            }

            self._update_item(
                key={"PK": f"BOOKING#{booking_id}", "SK": f"BOOKING#{booking_id}"},
                update_expression=update_expression,
                expression_values=expression_values,
            )

            return self.get_booking(booking_id)
        except Exception as e:
            logger.error(f"Error updating license info: {str(e)}")
            raise
