#!/bin/bash

# Exit on error
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create a temporary directory for the build
BUILD_DIR="$(mktemp -d)"
echo "Building in $BUILD_DIR"

# Create the Python directory structure
mkdir -p "$BUILD_DIR/python"

# Install dependencies into the layer directory
pip3 install \
    --platform manylinux2014_x86_64 \
    --target="$BUILD_DIR/python" \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    aws-lambda-powertools[all] \
    boto3 \
    pydantic[email] \
    python-jose[cryptography] \
    stripe \
    email-validator

# Create the deployment package
cd "$BUILD_DIR"
zip -r9 "$SCRIPT_DIR/layer.zip" .

# Cleanup
cd -
rm -rf "$BUILD_DIR"

echo "Layer has been built at $SCRIPT_DIR/layer.zip" 