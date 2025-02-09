from datetime import date
from enum import Enum
from typing import Optional
from pydantic import validator
from models.base import DynamoDBModel


class BlockedReason(str, Enum):
    MAINTENANCE = "maintenance"
    PRIVATE = "private"
    OTHER = "other"


class BlockedDates(DynamoDBModel):
    """Model for managing periods when the van is unavailable"""

    start_date: date
    end_date: date
    reason: BlockedReason
    notes: Optional[str] = None

    class Config:
        from_attributes = True

    @validator("end_date")
    def validate_end_date(cls, v, values):
        if "start_date" in values:
            # Allow end_date to be the same as start_date (single day block)
            if v < values["start_date"]:
                raise ValueError("end_date must be on or after start_date")
        return v

    def dict_for_dynamo(self) -> dict:
        """Convert model to DynamoDB-compatible dictionary"""
        data = super().dict_for_dynamo()
        # Convert dates to ISO format
        data["start_date"] = self.start_date.isoformat()
        data["end_date"] = self.end_date.isoformat()
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
        return super().from_dynamo(data)
