from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, Field

from models.common import PricingRule
from utils.dynamodb import PricingRuleRepository, get_table
from utils.middleware import create_response, handle_errors, parse_body, require_admin

logger = Logger()
tracer = Tracer()


class CreatePricingRuleRequest(BaseModel):
    """Request model for creating a pricing rule."""

    start_date: str
    end_date: str
    base_price: str
    min_stay: int = Field(ge=1)


@tracer.capture_lambda_handler
@handle_errors
@require_admin
@parse_body(CreatePricingRuleRequest)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Create a new pricing rule."""
    # Get request data
    request: CreatePricingRuleRequest = event["parsed_body"]

    try:
        # Parse dates
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d").date()

        # Parse price
        base_price = Decimal(request.base_price)
        if base_price <= 0:
            raise ValueError("Base price must be greater than 0")

    except ValueError as e:
        return create_response(400, {"error": "Invalid input", "message": str(e)})

    # Validate date range
    if start_date >= end_date:
        return create_response(
            400,
            {
                "error": "Invalid date range",
                "message": "End date must be after start date",
            },
        )

    # Get DynamoDB table
    table = get_table()

    # Initialize repository
    pricing_repo = PricingRuleRepository(table)

    # Check for overlapping rules
    existing_rules = pricing_repo.get_by_date_range(start_date, end_date)
    if existing_rules:
        return create_response(
            409,
            {
                "error": "Date conflict",
                "message": "A pricing rule already exists for this date range",
            },
        )

    # Create pricing rule
    rule = PricingRule(
        id=uuid4(),
        start_date=start_date,
        end_date=end_date,
        base_price=base_price,
        min_stay=request.min_stay,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    pricing_repo.create(rule)

    return create_response(201, rule)
