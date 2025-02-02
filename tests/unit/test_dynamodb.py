from datetime import date, datetime
from decimal import Decimal

import pytest
from mypy_boto3_dynamodb.service_resource import Table

from models.common import (
    BlockedDate,
    BlockedDateReason,
    Booking,
    BookingStatus,
    Customer,
    PricingRule,
)
from utils.dynamodb import (
    BlockedDateRepository,
    BookingRepository,
    CustomerRepository,
    PricingRuleRepository,
)


def test_booking_repository(
    dynamodb_table: Table, sample_booking: Booking, sample_customer: Customer
):
    """Test BookingRepository CRUD operations."""
    repo = BookingRepository(dynamodb_table)

    # Test create
    repo.create(sample_booking)

    # Test get
    retrieved = repo.get(sample_booking.id)
    assert retrieved is not None
    assert retrieved.id == sample_booking.id
    assert retrieved.customer_id == sample_customer.id
    assert retrieved.status == BookingStatus.PENDING

    # Test get by date range
    bookings = repo.get_by_date_range(
        date(2024, 6, 1), date(2024, 6, 30), BookingStatus.PENDING
    )
    assert len(bookings) == 1
    assert bookings[0].id == sample_booking.id

    # Test update status
    repo.update_status(sample_booking.id, BookingStatus.CONFIRMED)
    updated = repo.get(sample_booking.id)
    assert updated is not None
    assert updated.status == BookingStatus.CONFIRMED


def test_customer_repository(dynamodb_table: Table, sample_customer: Customer):
    """Test CustomerRepository CRUD operations."""
    repo = CustomerRepository(dynamodb_table)

    # Test create
    repo.create(sample_customer)

    # Test get
    retrieved = repo.get(sample_customer.email)
    assert retrieved is not None
    assert retrieved.id == sample_customer.id
    assert retrieved.email == sample_customer.email
    assert retrieved.drivers_license_url is None

    # Test update driver's license
    license_url = "s3://bucket/license.pdf"
    repo.update_drivers_license(sample_customer.email, license_url)
    updated = repo.get(sample_customer.email)
    assert updated is not None
    assert updated.drivers_license_url == license_url


def test_pricing_rule_repository(
    dynamodb_table: Table, sample_pricing_rule: PricingRule
):
    """Test PricingRuleRepository CRUD operations."""
    repo = PricingRuleRepository(dynamodb_table)

    # Test create
    repo.create(sample_pricing_rule)

    # Test get by date range
    rules = repo.get_by_date_range(date(2024, 1, 1), date(2024, 12, 31))
    assert len(rules) == 1
    assert rules[0].id == sample_pricing_rule.id
    assert rules[0].base_price == sample_pricing_rule.base_price

    # Test no rules found
    rules = repo.get_by_date_range(date(2025, 1, 1), date(2025, 12, 31))
    assert len(rules) == 0


def test_blocked_date_repository(
    dynamodb_table: Table, sample_blocked_date: BlockedDate
):
    """Test BlockedDateRepository CRUD operations."""
    repo = BlockedDateRepository(dynamodb_table)

    # Test create
    repo.create(sample_blocked_date)

    # Test get by date range
    blocked_dates = repo.get_by_date_range(date(2024, 7, 1), date(2024, 7, 31))
    assert len(blocked_dates) == 1
    assert blocked_dates[0].id == sample_blocked_date.id
    assert blocked_dates[0].reason == BlockedDateReason.MAINTENANCE

    # Test no blocked dates found
    blocked_dates = repo.get_by_date_range(date(2024, 8, 1), date(2024, 8, 31))
    assert len(blocked_dates) == 0
