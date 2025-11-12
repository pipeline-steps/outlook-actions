#!/bin/bash

# Run script for outlook-actions step
# This script runs the Docker container with local config and output

set -e

# Configuration
IMAGE_NAME="outlook-actions:test"
CONFIG_FILE="${CONFIG_FILE:-./config.json}"
OUTPUT_DIR="${OUTPUT_DIR:-./output}"
OUTPUT_FILE="emails.jsonl"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Outlook Actions Step ===${NC}"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    echo ""
    echo "Please create a config.json file with your Azure AD credentials."
    echo "You can copy config.example.json as a starting point:"
    echo ""
    echo "  cp config.example.json config.json"
    echo ""
    echo "Then edit config.json with your actual values:"
    echo "  - tenantId: Your Azure AD tenant ID"
    echo "  - clientId: Your application (client) ID"
    echo "  - clientSecret: Your client secret value"
    echo "  - userId: Email address of the user to fetch emails for"
    echo ""
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Config file: $CONFIG_FILE"
echo "  Output dir:  $OUTPUT_DIR"
echo "  Output file: $OUTPUT_FILE"
echo ""

# Check if Docker image exists
if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo -e "${YELLOW}Docker image '$IMAGE_NAME' not found. Building...${NC}"
    docker build -t "$IMAGE_NAME" .
    echo ""
fi

# Run the container
echo -e "${GREEN}Running outlook-actions...${NC}"
echo ""

docker run --rm \
    -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
    -v "$(pwd)/$OUTPUT_DIR:/output" \
    "$IMAGE_NAME" \
    --config /config.json \
    --output "/output/$OUTPUT_FILE"

echo ""
echo -e "${GREEN}=== Done ===${NC}"
echo ""
echo "Output written to: $OUTPUT_DIR/$OUTPUT_FILE"
echo ""
echo "To view the results:"
echo "  cat $OUTPUT_DIR/$OUTPUT_FILE | jq"
echo ""
