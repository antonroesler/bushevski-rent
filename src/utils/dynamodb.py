from datetime import date, datetime
from typing import Generic, TypeVar
from uuid import UUID

import boto3
from boto3.dynamodb.conditions import Attr, ConditionBase, Key
from mypy_boto3_dynamodb.service_resource import Table
from pydantic import BaseModel

from models.common import BlockedDate, Booking, BookingStatus, Customer, PricingRule

T = TypeVar("T", bound=BaseModel)


class DynamoDBRepository(Generic[T]):
    def __init__(self, table: Table):
        self.table = table

    def _format_date(self, d: date) -> str:
        return d.strftime("%Y-%m")


class BookingRepository(DynamoDBRepository[Booking]):
    def create(self, booking: Booking) -> None:
        booking_data = booking.model_dump()
        item = {
            "PK": f"BOOKING#{booking.id}",
            "SK": "METADATA",
            "GSI1PK": f"DATE#{self._format_date(booking.start_date)}",
            "GSI1SK": f"STATUS#{booking.status}",
            "Type": "Booking",
            **booking_data,
        }
        self.table.put_item(Item=item)

    def get(self, booking_id: UUID) -> Booking | None:
        response = self.table.get_item(Key={"PK": f"BOOKING#{booking_id}", "SK": "METADATA"})
        if "Item" not in response:
            return None
        return Booking.model_validate(response["Item"])

    def get_by_date_range(
        self, start_date: date, end_date: date, status: BookingStatus | None = None
    ) -> list[Booking]:
        # Convert dates to month format for GSI1PK
        start_month = self._format_date(start_date)
        end_month = self._format_date(end_date)

        # Query conditions
        key_condition: ConditionBase = Key("GSI1PK").between(
            f"DATE#{start_month}", f"DATE#{end_month}"
        )

        if status:
            key_condition = key_condition & Key("GSI1SK").eq(f"STATUS#{status}")

        response = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression=key_condition,
            FilterExpression=Attr("Type").eq("Booking"),
        )

        return [Booking.model_validate(item) for item in response["Items"]]

    def update_status(self, booking_id: UUID, status: BookingStatus) -> None:
        self.table.update_item(
            Key={"PK": f"BOOKING#{booking_id}", "SK": "METADATA"},
            UpdateExpression="SET #status = :status, GSI1SK = :gsi1sk, updated_at = :updated_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":gsi1sk": f"STATUS#{status}",
                ":updated_at": datetime.utcnow().isoformat(),
            },
        )


class CustomerRepository(DynamoDBRepository[Customer]):
    def create(self, customer: Customer) -> None:
        customer_data = customer.model_dump()
        item = {
            "PK": f"CUSTOMER#{customer.email}",
            "SK": "METADATA",
            "Type": "Customer",
            **customer_data,
        }
        self.table.put_item(Item=item)

    def get(self, email: str) -> Customer | None:
        response = self.table.get_item(Key={"PK": f"CUSTOMER#{email}", "SK": "METADATA"})
        if "Item" not in response:
            return None
        return Customer.model_validate(response["Item"])

    def update_drivers_license(self, email: str, drivers_license_url: str) -> None:
        self.table.update_item(
            Key={"PK": f"CUSTOMER#{email}", "SK": "METADATA"},
            UpdateExpression="SET drivers_license_url = :url, updated_at = :updated_at",
            ExpressionAttributeValues={
                ":url": drivers_license_url,
                ":updated_at": datetime.utcnow().isoformat(),
            },
        )


class PricingRuleRepository(DynamoDBRepository[PricingRule]):
    def create(self, rule: PricingRule) -> None:
        rule_data = rule.model_dump()
        item = {
            "PK": f"PRICING#{self._format_date(rule.start_date)}",
            "SK": f"RULE#{rule.id}",
            "Type": "PricingRule",
            **rule_data,
        }
        self.table.put_item(Item=item)

    def get_by_date_range(self, start_date: date, end_date: date) -> list[PricingRule]:
        start_month = self._format_date(start_date)
        end_month = self._format_date(end_date)

        response = self.table.query(
            KeyConditionExpression=Key("PK").between(
                f"PRICING#{start_month}", f"PRICING#{end_month}"
            )
        )

        return [PricingRule.model_validate(item) for item in response["Items"]]


class BlockedDateRepository(DynamoDBRepository[BlockedDate]):
    def create(self, blocked_date: BlockedDate) -> None:
        blocked_date_data = blocked_date.model_dump()
        item = {
            "PK": f"BLOCKED#{self._format_date(blocked_date.start_date)}",
            "SK": f"DATE#{blocked_date.start_date.isoformat()}",
            "Type": "BlockedDate",
            **blocked_date_data,
        }
        self.table.put_item(Item=item)

    def get_by_date_range(self, start_date: date, end_date: date) -> list[BlockedDate]:
        start_month = self._format_date(start_date)
        end_month = self._format_date(end_date)

        response = self.table.query(
            KeyConditionExpression=Key("PK").between(
                f"BLOCKED#{start_month}", f"BLOCKED#{end_month}"
            )
        )

        return [BlockedDate.model_validate(item) for item in response["Items"]]


def get_table() -> Table:
    """Get DynamoDB table instance."""
    dynamodb = boto3.resource("dynamodb")
    table_name = boto3.client("ssm").get_parameter(Name="/bushevski/dynamodb/table_name")[
        "Parameter"
    ]["Value"]
    return dynamodb.Table(table_name)
