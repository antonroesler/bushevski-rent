import boto3
from aws_lambda_powertools import Logger

from models.common import Booking, Customer

logger = Logger()


class EmailService:
    def __init__(self):
        self.ses = boto3.client("ses")
        self.sender = "noreply@bushevski.com"  # Must be verified in SES

    def _format_price(self, amount: float) -> str:
        return f"€{amount:.2f}"

    def send_booking_confirmation(self, booking: Booking, customer: Customer) -> None:
        """Send booking confirmation email to customer."""
        subject = "Booking Confirmation - Bushevski Camper Rental"

        # Format fees
        fees = [
            ("Nightly Rates", booking.fees.nightly_rates),
            ("Service Fee", booking.fees.service_fee),
        ]

        if booking.fees.early_pickup_fee:
            fees.append(("Early Pickup Fee", booking.fees.early_pickup_fee))
        if booking.fees.late_return_fee:
            fees.append(("Late Return Fee", booking.fees.late_return_fee))
        if booking.fees.parking_fee:
            fees.append(("Parking Fee", booking.fees.parking_fee))
        if booking.fees.delivery_fee:
            fees.append(("Delivery Fee", booking.fees.delivery_fee))

        # Build email body
        body = f"""
Dear {customer.first_name} {customer.last_name},

Thank you for booking with Bushevski Camper Rental. Here are your booking details:

Booking Reference: {booking.id}
Status: {booking.status.value}

Dates:
- Pickup: {booking.start_date.strftime("%B %d, %Y")} at {booking.pickup_time.strftime("%H:%M")}
- Return: {booking.end_date.strftime("%B %d, %Y")} at {booking.return_time.strftime("%H:%M")}

Fees:
{chr(10).join(f"- {name}: {self._format_price(amount)}" for name, amount in fees)}

Total Price: {self._format_price(booking.total_price)}

Next Steps:
1. Please upload a copy of your driver's license through our website
2. Arrive at the pickup location at your scheduled time
3. Have your driver's license ready for verification

If you need to make any changes to your booking or have questions, please contact us.

Best regards,
Bushevski Camper Rental Team
"""

        try:
            self.ses.send_email(
                Source=self.sender,
                Destination={"ToAddresses": [customer.email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                },
            )
            logger.info(f"Sent booking confirmation email to {customer.email}")
        except Exception as e:
            logger.error(f"Failed to send booking confirmation email: {e!s}")
            raise

    def send_booking_status_update(
        self, booking: Booking, customer: Customer, old_status: str
    ) -> None:
        """Send booking status update email to customer."""
        subject = "Booking Status Update - Bushevski Camper Rental"

        body = f"""
Dear {customer.first_name} {customer.last_name},

Your booking status has been updated:

Booking Reference: {booking.id}
Previous Status: {old_status}
New Status: {booking.status.value}

Booking Details:
- Pickup: {booking.start_date.strftime("%B %d, %Y")} at {booking.pickup_time.strftime("%H:%M")}
- Return: {booking.end_date.strftime("%B %d, %Y")} at {booking.return_time.strftime("%H:%M")}

If you have any questions about this status change, please contact us.

Best regards,
Bushevski Camper Rental Team
"""

        try:
            self.ses.send_email(
                Source=self.sender,
                Destination={"ToAddresses": [customer.email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                },
            )
            logger.info(f"Sent status update email to {customer.email}")
        except Exception as e:
            logger.error(f"Failed to send status update email: {e!s}")
            raise
