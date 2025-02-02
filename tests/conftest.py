from collections.abc import Generator
from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

import boto3
import pytest
from moto.dynamodb import mock_dynamodb2
from moto.s3 import mock_s3
from moto.ses import mock_ses
from moto.ssm import mock_ssm
from mypy_boto3_dynamodb.service_resource import Table

from models.common import (
    Address,
    BlockedDate,
    BlockedDateReason,
    Booking,
    BookingFees,
    BookingStatus,
    Customer,
    DeliveryDistance,
    PricingRule,
)


@pytest.fixture(scope="function")
def aws_credentials() -> None:
    """Mock AWS Credentials for moto."""
    import os

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"


@pytest.fixture(scope="function")
def dynamodb(aws_credentials: None) -> Generator:
    with mock_dynamodb2():
        yield boto3.resource("dynamodb")


@pytest.fixture(scope="function")
def s3(aws_credentials: None) -> Generator:
    with mock_s3():
        yield boto3.client("s3")


@pytest.fixture(scope="function")
def ses(aws_credentials: None) -> Generator:
    with mock_ses():
        yield boto3.client("ses")


@pytest.fixture(scope="function")
def ssm(aws_credentials: None) -> Generator:
    with mock_ssm():
        yield boto3.client("ssm")


@pytest.fixture(scope="function")
def dynamodb_table(dynamodb, ssm) -> Table:
    """Create a DynamoDB table for testing."""
    table_name = "bushevski-test"

    # Create table
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create SSM parameter
    ssm.put_parameter(Name="/bushevski/dynamodb/table_name", Value=table_name, Type="String")

    return table


@pytest.fixture(scope="function")
def s3_bucket(s3, ssm) -> str:
    """Create an S3 bucket for testing."""
    bucket_name = "bushevski-documents-test"

    # Create bucket
    s3.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "eu-central-1"},
    )

    # Create SSM parameter
    ssm.put_parameter(Name="/bushevski/s3/documents_bucket", Value=bucket_name, Type="String")

    return bucket_name


@pytest.fixture(scope="function")
def admin_api_key(ssm) -> str:
    """Create admin API key in SSM."""
    api_key = "test-admin-key"

    ssm.put_parameter(Name="/bushevski/admin/api_key", Value=api_key, Type="SecureString")

    return api_key


@pytest.fixture
def sample_customer() -> Customer:
    """Create a sample customer."""
    return Customer(
        id=uuid4(),
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        address=Address(
            street="123 Main St",
            city="Test City",
            postal_code="12345",
            country="Test Country",
        ),
        drivers_license_url=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_pricing_rule() -> PricingRule:
    """Create a sample pricing rule."""
    return PricingRule(
        id=uuid4(),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        base_price=Decimal("100"),
        min_stay=3,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_booking(sample_customer: Customer) -> Booking:
    """Create a sample booking."""
    return Booking(
        id=uuid4(),
        start_date=date(2024, 6, 1),
        end_date=date(2024, 6, 5),
        pickup_time=time(14, 0),
        return_time=time(12, 0),
        use_parking=True,
        delivery_distance=DeliveryDistance.NO_DELIVERY,
        status=BookingStatus.PENDING,
        customer_id=sample_customer.id,
        fees=BookingFees(
            nightly_rates=Decimal("400"),
            service_fee=Decimal("50"),
            parking_fee=Decimal("20"),
        ),
        total_price=Decimal("470"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_blocked_date() -> BlockedDate:
    """Create a sample blocked date."""
    return BlockedDate(
        id=uuid4(),
        start_date=date(2024, 7, 1),
        end_date=date(2024, 7, 5),
        reason=BlockedDateReason.MAINTENANCE,
        notes="Annual maintenance",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def api_gateway_event() -> dict:
    """Create a sample API Gateway event."""
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/path/to/resource",
        "rawQueryString": "",
        "headers": {"Content-Type": "application/json", "X-Api-Key": "test-api-key"},
        "queryStringParameters": {},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "domainName": "id.execute-api.us-east-1.amazonaws.com",
            "domainPrefix": "id",
            "http": {
                "method": "POST",
                "path": "/path/to/resource",
                "protocol": "HTTP/1.1",
                "sourceIp": "IP",
                "userAgent": "agent",
            },
            "requestId": "id",
            "routeKey": "$default",
            "stage": "$default",
            "time": "12/Mar/2020:19:03:58 +0000",
            "timeEpoch": 1583348638390,
        },
        "body": "{}",
        "isBase64Encoded": False,
    }
