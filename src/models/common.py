from datetime import date, time, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DeliveryDistance(int, Enum):
    NO_DELIVERY = 0
    KM_100 = 100
    KM_200 = 200
    KM_300 = 300

    @property
    def fee(self) -> Decimal:
        return {
            0: Decimal("0"),
            100: Decimal("20"),
            200: Decimal("40"),
            300: Decimal("60"),
        }[self.value]


class BlockedDateReason(str, Enum):
    MAINTENANCE = "maintenance"
    PRIVATE = "private"
    OTHER = "other"


class Address(BaseModel):
    street: str
    city: str
    postal_code: str
    country: str


class CustomerBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    address: Address


class Customer(CustomerBase):
    id: UUID
    drivers_license_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PricingRule(BaseModel):
    id: UUID
    start_date: date
    end_date: date
    base_price: Decimal
    min_stay: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class BlockedDate(BaseModel):
    id: UUID
    start_date: date
    end_date: date
    reason: BlockedDateReason
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    def get_dates(self) -> List[date]:
        """Get all dates in the blocked period."""
        dates = []
        current = self.start_date
        while current <= self.end_date:
            dates.append(current)
            current = date.fromordinal(current.toordinal() + 1)
        return dates


class BookingFees(BaseModel):
    nightly_rates: Decimal
    service_fee: Decimal = Field(default=Decimal("50"))
    early_pickup_fee: Optional[Decimal] = Field(default=Decimal("50"))
    late_return_fee: Optional[Decimal] = Field(default=Decimal("50"))
    parking_fee: Optional[Decimal] = None
    delivery_fee: Optional[Decimal] = None

    @validator("parking_fee", pre=True)
    def calculate_parking_fee(cls, v, values):
        if v is None:
            return None
        # €5 per night
        nights = values.get("nights", 0)
        return Decimal("5") * nights if nights > 0 else None


class BookingBase(BaseModel):
    start_date: date
    end_date: date
    pickup_time: time
    return_time: time
    use_parking: bool = False
    delivery_distance: DeliveryDistance = DeliveryDistance.NO_DELIVERY

    @validator("end_date")
    def end_date_after_start_date(cls, v, values):
        if "start_date" in values and v <= values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

    @property
    def nights(self) -> int:
        """Calculate number of nights. Return day is not counted."""
        return (self.end_date - self.start_date).days

    @property
    def has_early_pickup(self) -> bool:
        return self.pickup_time.hour < 12

    @property
    def has_late_return(self) -> bool:
        return self.return_time.hour >= 16

    def get_dates(self) -> List[date]:
        """Get all dates in the booking period."""
        dates = []
        current = self.start_date
        while current <= self.end_date:
            dates.append(current)
            current = date.fromordinal(current.toordinal() + 1)
        return dates


class Booking(BookingBase):
    id: UUID
    status: BookingStatus
    customer_id: UUID
    fees: BookingFees
    total_price: Decimal
    created_at: datetime
    updated_at: datetime


class CreateBookingRequest(BookingBase):
    customer: CustomerBase


class BookingResponse(Booking):
    customer: Customer
