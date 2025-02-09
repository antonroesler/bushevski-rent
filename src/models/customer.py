from pydantic import EmailStr, constr
from typing_extensions import Annotated
from models.base import DynamoDBModel


class Customer(DynamoDBModel):
    """Customer model for storing customer information"""

    first_name: str
    last_name: str
    email: EmailStr
    phone: Annotated[str, constr(pattern=r"^\+?[1-9]\d{1,14}$")]  # E.164 format
    street: str
    city: str
    postal_code: str
    country: str
    drivers_license_url: str | None = None

    class Config:
        from_attributes = True

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
