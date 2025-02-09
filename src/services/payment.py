import stripe
import os
from decimal import Decimal
from aws_lambda_powertools import Logger
from services.base import BaseService

logger = Logger()


class PaymentService(BaseService):
    """Service for handling payment operations"""

    def __init__(self):
        super().__init__()
        self.stripe = stripe
        self.stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

    def create_payment_intent(
        self,
        amount: Decimal,
        booking_id: str,
        customer_email: str,
        currency: str = "eur",
    ) -> dict:
        """Create a Stripe payment intent"""
        try:
            # Convert decimal amount to cents for Stripe
            amount_cents = int(amount * 100)

            # Create the payment intent
            intent = self.stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                automatic_payment_methods={"enabled": True},
                receipt_email=customer_email,
                metadata={
                    "booking_id": booking_id,
                    "environment": os.environ.get("STAGE", "dev"),
                },
            )

            logger.info(f"Created payment intent {intent.id} for booking {booking_id}")

            return {
                "client_secret": intent.client_secret,
                "id": intent.id,
                "amount": amount_cents,
                "currency": currency,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            raise
