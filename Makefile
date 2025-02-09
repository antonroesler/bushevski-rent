.PHONY: build deploy test clean layer

# Variables
STACK_NAME = bushevski-rental
STAGE ?= dev
REGION ?= eu-central-1
PROFILE ?= default

# Build the Lambda layer
layer:
	chmod +x ./build_layer.sh
	./build_layer.sh

# Build the application
build: layer
	sam build --use-container

# Deploy the application
deploy-guided: build
	source .env && sam deploy \
		--stack-name $(STACK_NAME)-$(STAGE) \
		--region $(REGION) \
		--profile $(PROFILE) \
		--parameter-overrides Stage=$(STAGE) \
		--capabilities CAPABILITY_IAM \
		--parameter-overrides StripeSecretKey=$(STRIPE_SECRET_KEY) \
		--guided

# Quick deploy without prompts (after initial deploy)
deploy: build
	source .env && sam deploy \
		--stack-name $(STACK_NAME)-$(STAGE) \
		--region $(REGION) \
		--profile $(PROFILE) \
		--parameter-overrides Stage=$(STAGE) \
		--capabilities CAPABILITY_IAM \
		--no-confirm-changeset \
		--parameter-overrides StripeSecretKey=$(STRIPE_SECRET_KEY) \
		--no-fail-on-empty-changeset

# Run tests
test:
	pytest tests/ -v

# Clean build artifacts
clean:
	rm -rf .aws-sam
	rm -f layer.zip
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Start API locally
local:
	sam local start-api \
		--env-vars local-env.json \
		--parameter-overrides Stage=local

# Generate requirements.txt
requirements:
	pip freeze > requirements.txt 