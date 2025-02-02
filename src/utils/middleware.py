import functools
import json
from decimal import Decimal
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union
from uuid import UUID

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, ValidationError

logger = Logger()
tracer = Tracer()

T = TypeVar("T", bound=BaseModel)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


def handle_errors(func: Callable) -> Callable:
    """Decorator to handle errors and return appropriate API responses."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"Validation error: {str(e)}")
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "Validation Error", "details": e.errors()},
                    cls=DecimalEncoder,
                ),
            }
        except ValueError as e:
            logger.warning(f"Value error: {str(e)}")
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "Invalid Input", "message": str(e)}, cls=DecimalEncoder
                ),
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "error": "Internal Server Error",
                        "message": "An unexpected error occurred",
                    },
                    cls=DecimalEncoder,
                ),
            }

    return wrapper


def validate_admin_api_key(event: Dict[str, Any]) -> bool:
    """Validate admin API key from request headers."""
    headers = event.get("headers", {})
    api_key = headers.get("x-api-key")

    if not api_key:
        return False

    # Get API key from SSM Parameter Store
    ssm = boto3.client("ssm")
    stored_key = ssm.get_parameter(
        Name="/bushevski/admin/api_key", WithDecryption=True
    )["Parameter"]["Value"]

    return api_key == stored_key


def require_admin(func: Callable) -> Callable:
    """Decorator to require admin API key."""

    @functools.wraps(func)
    def wrapper(event: Dict[str, Any], context: LambdaContext):
        if not validate_admin_api_key(event):
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {"error": "Unauthorized", "message": "Invalid or missing API key"}
                ),
            }
        return func(event, context)

    return wrapper


def parse_body(model: Type[T]) -> Callable:
    """Decorator to parse and validate request body using Pydantic model."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: LambdaContext):
            try:
                body = json.loads(event.get("body", "{}"))
                parsed_body = model.model_validate(body)
                event["parsed_body"] = parsed_body
                return func(event, context)
            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {
                            "error": "Invalid JSON",
                            "message": "Request body must be valid JSON",
                        }
                    ),
                }
            except ValidationError as e:
                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {"error": "Validation Error", "details": e.errors()}
                    ),
                }

        return wrapper

    return decorator


def create_response(
    status_code: int,
    body: Union[Dict[str, Any], BaseModel, None] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create API Gateway response with consistent format."""
    response = {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", **(headers or {})},
    }

    if body is not None:
        if isinstance(body, BaseModel):
            response["body"] = json.dumps(body.model_dump(), cls=DecimalEncoder)
        else:
            response["body"] = json.dumps(body, cls=DecimalEncoder)

    return response
