import pytest
from botocore.exceptions import ClientError

from utils.email import EmailService


def test_send_booking_confirmation(ses, sample_booking, sample_customer):
    """Test sending booking confirmation email."""
    service = EmailService()

    # Test successful send
    service.send_booking_confirmation(sample_booking, sample_customer)

    # Verify email was sent
    sent_emails = ses.list_identities()
    assert sample_customer.email in sent_emails.get("Identities", [])


def test_send_booking_status_update(ses, sample_booking, sample_customer):
    """Test sending booking status update email."""
    service = EmailService()

    # Test successful send
    service.send_booking_status_update(sample_booking, sample_customer, "pending")

    # Verify email was sent
    sent_emails = ses.list_identities()
    assert sample_customer.email in sent_emails.get("Identities", [])


def test_email_service_error_handling(ses, sample_booking, sample_customer):
    """Test email service error handling."""
    service = EmailService()

    # Mock SES to raise an error
    ses.send_email.side_effect = ClientError(
        {"Error": {"Code": "MessageRejected", "Message": "Email address not verified"}},
        "SendEmail",
    )

    # Test error handling in confirmation email
    with pytest.raises(ClientError):
        service.send_booking_confirmation(sample_booking, sample_customer)

    # Test error handling in status update email
    with pytest.raises(ClientError):
        service.send_booking_status_update(sample_booking, sample_customer, "pending")
