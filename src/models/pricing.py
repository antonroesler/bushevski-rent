from datetime import date, datetime
from decimal import Decimal
from pydantic import Field, validator
from models.base import DynamoDBModel


class PricingRule(DynamoDBModel):
    """Pricing rule for specific dates"""

    start_date: date
    end_date: date
    nightly_rate: Decimal = Field(decimal_places=2, gt=0)
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def duration_days(self) -> int:
        """Get the duration of the rule in days"""
        return (self.end_date - self.start_date).days + 1

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: str,
            date: lambda d: d.isoformat(),
            datetime: lambda dt: dt.isoformat(),
        }

    @validator("end_date")
    def validate_end_date(cls, v, values):
        if "start_date" in values:
            if v < values["start_date"]:
                raise ValueError("end_date must be on or after start_date")
        return v

    def dict_for_dynamo(self) -> dict:
        data = super().dict_for_dynamo()
        data["start_date"] = self.start_date.isoformat()
        data["end_date"] = self.end_date.isoformat()
        data["nightly_rate"] = str(self.nightly_rate)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dynamo(cls, data: dict):
        if not data:
            return None
        if "start_date" in data:
            data["start_date"] = date.fromisoformat(data["start_date"])
        if "end_date" in data:
            data["end_date"] = date.fromisoformat(data["end_date"])
        if "nightly_rate" in data:
            data["nightly_rate"] = Decimal(data["nightly_rate"])
        if "created_at" in data:
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return super().from_dynamo(data)
