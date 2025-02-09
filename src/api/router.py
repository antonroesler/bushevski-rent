import sys
import os
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
    UnauthorizedError,
)
from api.bookings import router as bookings_router
from api.admin import router as admin_router
from api.util.cors import cors_config

logger = Logger()
tracer = Tracer()
app = APIGatewayRestResolver(cors=cors_config)


def debug_info():
    """Print debug information about the Python environment"""
    logger.info(
        {
            "python_path": sys.path,
            "current_dir": os.getcwd(),
            "dir_contents": os.listdir("."),
            "parent_dir_contents": os.listdir("..")
            if os.path.exists("..")
            else "No parent dir",
        }
    )


try:
    debug_info()
except ImportError as e:
    logger.error(f"Error: {str(e)}")

# Register routes
app.include_router(bookings_router.router, prefix="/bookings")
app.include_router(admin_router.router, prefix="/admin")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",  # Configure this appropriately
    "Access-Control-Allow-Headers": "Content-Type,X-Api-Key,X-Amz-Date,X-Amz-Security-Token,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Max-Age": "3600",
}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    """Main Lambda handler"""
    try:
        # Handle OPTIONS requests for CORS preflight
        if event.get("httpMethod") == "OPTIONS":
            return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

        # Normal request handling
        response = app.resolve(event, context)

        # Ensure CORS headers are in the response
        if isinstance(response, dict) and "headers" in response:
            response["headers"].update(CORS_HEADERS)

        return response

    except BadRequestError as e:
        return {"statusCode": 400, "headers": CORS_HEADERS, "body": {"message": str(e)}}
    except UnauthorizedError as e:
        return {"statusCode": 401, "headers": CORS_HEADERS, "body": {"message": str(e)}}
    except NotFoundError as e:
        return {"statusCode": 404, "headers": CORS_HEADERS, "body": {"message": str(e)}}
    except Exception:
        logger.exception("Unhandled exception")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": {"message": "Internal server error"},
        }
