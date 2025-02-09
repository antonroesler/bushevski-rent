import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DynamoDBModel(BaseModel):
    """Base model with DynamoDB functionality"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Convert UUID to string
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None

    def dict_for_dynamo(self) -> dict:
        """Convert model to DynamoDB-compatible dictionary"""
        data = self.model_dump(exclude_none=True)
        # Ensure id is string
        if "id" in data:
            data["id"] = str(data["id"])
        return data

    @classmethod
    def from_dynamo(cls, data: dict):
        """Create model instance from DynamoDB data"""
        if not data:
            return None
        return cls(**data)
