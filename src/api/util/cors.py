from aws_lambda_powertools.event_handler.api_gateway import CORSConfig

cors_config = CORSConfig(
    allow_origin="*",
    allow_headers=["Content-Type", "Authorization", "X-Api-Key"],
    max_age=3600,
)
