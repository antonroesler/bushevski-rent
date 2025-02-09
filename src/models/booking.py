from datetime import date, time, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict
from pydantic import Field, validator
from models.base import DynamoDBModel
from models.customer import Customer


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Booking(DynamoDBModel):
    """Booking model for storing booking information"""

    # Dates and times
    start_date: date
    end_date: date
    pickup_time: time
    return_time: time

    # Status
    status: BookingStatus = BookingStatus.PENDING

    # Detailed pricing components
    nightly_rates_breakdown: Dict[str, Decimal]  # date -> rate mapping
    nightly_rates_total: Decimal = Field(decimal_places=2)  # Sum of nightly rates
    service_fee: Decimal = Field(default=Decimal("50.00"), decimal_places=2)
    parking_fee: Optional[Decimal] = Field(default=None, decimal_places=2)
    delivery_fee: Optional[Decimal] = Field(default=None, decimal_places=2)
    total_price: Decimal = Field(decimal_places=2)  # Sum of all components

    # Service options
    parking: bool = False
    delivery_distance: Optional[int] = None

    # Customer reference (will be populated from junction table)
    customer_id: Optional[str] = None
    customer: Optional[Customer] = None

    # Driver's license info
    drivers_license_key: Optional[str] = None  # S3 key
    drivers_license_uploaded_at: Optional[datetime] = None
    drivers_license_filename: Optional[str] = None

    class Config:
        from_attributes = True
        json_encoders = {Decimal: str}

    @validator("end_date")
    def end_date_must_be_after_start_date(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

    def dict_for_dynamo(self) -> dict:
        """Convert model to DynamoDB-compatible dictionary"""
        data = super().dict_for_dynamo()
        # Convert dates to ISO format
        data["start_date"] = self.start_date.isoformat()
        data["end_date"] = self.end_date.isoformat()
        # Convert times to string
        data["pickup_time"] = self.pickup_time.isoformat()
        data["return_time"] = self.return_time.isoformat()
        # Convert pricing decimals to strings
        data["nightly_rates_total"] = str(self.nightly_rates_total)
        data["nightly_rates_breakdown"] = {
            date_str: str(rate)
            for date_str, rate in self.nightly_rates_breakdown.items()
        }
        data["service_fee"] = str(self.service_fee)
        if self.parking_fee:
            data["parking_fee"] = str(self.parking_fee)
        if self.delivery_fee:
            data["delivery_fee"] = str(self.delivery_fee)
        data["total_price"] = str(self.total_price)
        return data

    @classmethod
    def from_dynamo(cls, data: dict):
        """Create model instance from DynamoDB data"""
        if not data:
            return None
        # Convert ISO format to dates
        if "start_date" in data:
            data["start_date"] = date.fromisoformat(data["start_date"])
        if "end_date" in data:
            data["end_date"] = date.fromisoformat(data["end_date"])
        # Convert strings to times
        if "pickup_time" in data:
            data["pickup_time"] = time.fromisoformat(data["pickup_time"])
        if "return_time" in data:
            data["return_time"] = time.fromisoformat(data["return_time"])
        # Convert pricing strings to decimals
        if "nightly_rates_total" in data:
            data["nightly_rates_total"] = Decimal(data["nightly_rates_total"])
        if "nightly_rates_breakdown" in data:
            data["nightly_rates_breakdown"] = {
                date_str: Decimal(rate)
                for date_str, rate in data["nightly_rates_breakdown"].items()
            }
        if "service_fee" in data:
            data["service_fee"] = Decimal(data["service_fee"])
        if "parking_fee" in data:
            data["parking_fee"] = Decimal(data["parking_fee"])
        if "delivery_fee" in data:
            data["delivery_fee"] = Decimal(data["delivery_fee"])
        if "total_price" in data:
            data["total_price"] = Decimal(data["total_price"])
        return super().from_dynamo(data)
