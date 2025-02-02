from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from utils.middleware import (
    DecimalEncoder,
    create_response,
    handle_errors,
    parse_body,
    require_admin,
    validate_admin_api_key,
)


class TestModel(BaseModel):
    """Test model for request body parsing."""

    name: str
    age: int


def test_decimal_encoder():
    """Test JSON encoding of Decimal and UUID values."""
    encoder = DecimalEncoder()

    # Test Decimal encoding
    assert encoder.default(Decimal("10.50")) == "10.50"

    # Test UUID encoding
    uuid = UUID("12345678-1234-5678-1234-567812345678")
    assert encoder.default(uuid) == str(uuid)

    # Test unsupported type
    with pytest.raises(TypeError):
        encoder.default(complex(1, 2))


def test_handle_errors():
    """Test error handling decorator."""

    @handle_errors
    def test_func(error_type: str) -> dict:
        if error_type == "validation":
            raise ValidationError([], TestModel)
        elif error_type == "value":
            raise ValueError("Test error")
        elif error_type == "other":
            raise Exception("Unexpected error")
        return {"success": True}

    # Test successful execution
    result = test_func("none")
    assert result == {"success": True}

    # Test validation error
    result = test_func("validation")
    assert result["statusCode"] == 400
    assert "Validation Error" in result["body"]

    # Test value error
    result = test_func("value")
    assert result["statusCode"] == 400
    assert "Invalid Input" in result["body"]

    # Test unexpected error
    result = test_func("other")
    assert result["statusCode"] == 500
    assert "Internal Server Error" in result["body"]


def test_validate_admin_api_key(ssm, admin_api_key: str):
    """Test admin API key validation."""
    # Test valid API key
    event = {"headers": {"x-api-key": admin_api_key}}
    assert validate_admin_api_key(event) is True

    # Test invalid API key
    event = {"headers": {"x-api-key": "invalid-key"}}
    assert validate_admin_api_key(event) is False

    # Test missing API key
    event = {"headers": {}}
    assert validate_admin_api_key(event) is False


def test_require_admin(ssm, admin_api_key: str):
    """Test admin requirement decorator."""

    @require_admin
    def test_func(event: dict[str, Any], context: Any) -> dict:
        return {"success": True}

    # Test with valid API key
    event = {"headers": {"x-api-key": admin_api_key}}
    result = test_func(event, None)
    assert result == {"success": True}

    # Test with invalid API key
    event = {"headers": {"x-api-key": "invalid-key"}}
    result = test_func(event, None)
    assert result["statusCode"] == 401
    assert "Unauthorized" in result["body"]


def test_parse_body():
    """Test request body parsing decorator."""

    @parse_body(TestModel)
    def test_func(event: dict[str, Any], context: Any) -> dict:
        parsed_body = event["parsed_body"]
        return {
            "statusCode": 200,
            "body": {"name": parsed_body.name, "age": parsed_body.age},
        }

    # Test valid body
    event = {"body": '{"name": "John", "age": 30}'}
    result = test_func(event, None)
    assert result["statusCode"] == 200
    assert "John" in str(result["body"])

    # Test invalid JSON
    event = {"body": "invalid json"}
    result = test_func(event, None)
    assert result["statusCode"] == 400
    assert "Invalid JSON" in result["body"]

    # Test validation error
    event = {"body": '{"name": "John", "age": "invalid"}'}
    result = test_func(event, None)
    assert result["statusCode"] == 400
    assert "Validation Error" in result["body"]


def test_create_response():
    """Test response creation utility."""
    # Test basic response
    response = create_response(200, {"message": "Success"})
    assert response["statusCode"] == 200
    assert "Success" in response["body"]
    assert response["headers"]["Content-Type"] == "application/json"

    # Test response with Pydantic model
    model = TestModel(name="John", age=30)
    response = create_response(201, model)
    assert response["statusCode"] == 201
    assert "John" in response["body"]

    # Test response with custom headers
    response = create_response(200, {"message": "Success"}, {"Custom-Header": "Value"})
    assert response["headers"]["Custom-Header"] == "Value"

    # Test response without body
    response = create_response(204)
    assert response["statusCode"] == 204
    assert "body" not in response
