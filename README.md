# Bushevski Camper Rental Backend

[![CI](https://github.com/antonroesler/bushevski-rent/actions/workflows/ci.yml/badge.svg)](https://github.com/antonroesler/bushevski-rent/actions/workflows/ci.yml)
[![CD](https://github.com/antonroesler/bushevski-rent/actions/workflows/cd.yml/badge.svg)](https://github.com/antonroesler/bushevski-rent/actions/workflows/cd.yml)

Serverless backend for the Bushevski Camper Rental service built with AWS SAM, Lambda, and DynamoDB.

## Prerequisites

- Python 3.12
- AWS SAM CLI
- AWS CLI configured with appropriate credentials
- Docker (for local testing)

## Project Structure

```
bushevski-rent/
├── src/
│   ├── api/           # Lambda function handlers
│   ├── models/        # Pydantic models
│   ├── utils/         # Shared utilities
│   └── layers/        # Lambda layers
├── tests/            # Test files
└── template.yaml     # SAM template
```

## Setup

1. Install AWS SAM CLI:

   ```bash
   brew install aws-sam-cli
   ```

2. Install development dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r src/layers/common_layer/requirements.txt
   pip install -r requirements-dev.txt
   ```

3. Configure AWS credentials:
   ```bash
   aws configure
   ```

## Local Development

1. Start local API:

   ```bash
   sam local start-api
   ```

2. Run tests:
   ```bash
   pytest
   ```

## Deployment

1. Build the application:

   ```bash
   sam build
   ```

2. Deploy to AWS:

   ```bash
   sam deploy --guided
   ```

   For subsequent deployments:

   ```bash
   sam deploy
   ```

## Security

- Admin routes are protected by API Key authentication
- All data is encrypted at rest
- S3 bucket has strict access controls
- DynamoDB uses server-side encryption
- API Gateway has rate limiting enabled

## DynamoDB Schema

Single-table design with the following access patterns:

1. Bookings

   - PK: BOOKING#<id>
   - SK: METADATA
   - GSI1PK: DATE#<yyyy-mm>
   - GSI1SK: STATUS#<status>

2. Customers

   - PK: CUSTOMER#<email>
   - SK: METADATA
   - GSI1PK: BOOKING#<id>
   - GSI1SK: CUSTOMER#<email>

3. Pricing Rules

   - PK: PRICING#<yyyy-mm>
   - SK: RULE#<id>

4. Blocked Dates
   - PK: BLOCKED#<yyyy-mm>
   - SK: DATE#<yyyy-mm-dd>

## API Routes

### Public Routes

- GET /availability
- GET /pricing
- POST /bookings
- GET /bookings/{id}
- PUT /bookings/{id}/drivers-license

### Admin Routes (Protected)

- GET /admin/bookings
- PUT /admin/bookings/{id}/status
- POST /admin/pricing-rules
- POST /admin/blocked-dates

## Monitoring

- CloudWatch Logs enabled for all Lambda functions
- Custom metrics using Lambda Powertools
- X-Ray tracing for request flows
- Error tracking and alerting

## Contributing

1. Create a feature branch
2. Make changes
3. Run tests
4. Submit pull request

## License

Proprietary - All rights reserved

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment:

### CI Pipeline

- Runs on every push and pull request
- Executes all tests
- Performs code linting and formatting checks
- Generates code coverage reports

### CD Pipeline

- Automatically deploys to development environment on push to main
- Manual deployment to production via workflow dispatch
- Uses OpenID Connect for secure AWS authentication
- Manages infrastructure using AWS SAM
