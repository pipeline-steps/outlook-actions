#!/bin/bash

# Run script for outlook-actions step
# This script runs the Docker container with local config and output

set -e

# Configuration
IMAGE_NAME="outlook-actions:test"
CONFIG_FILE="${CONFIG_FILE:-./config.json}"
OUTPUT_DIR="${OUTPUT_DIR:-./output}"
INPUT_FILE=""
MODE=""
REBUILD=0

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -c, --config FILE      Path to config file (default: ./config.json)"
    echo "  -o, --output DIR       Output directory (default: ./output)"
    echo "  -i, --input FILE       Input file for action mode"
    echo "  -m, --mode MODE        Test mode: read|unread|recent|flag-first|move-first|action"
    echo "  -r, --rebuild          Force rebuild Docker image"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Test Modes:"
    echo "  read       - Read all emails from inbox (legacy mode)"
    echo "  unread     - Read only unread emails from inbox"
    echo "  recent     - Read 10 most recent emails"
    echo "  flag-first - Read recent emails and flag the first one"
    echo "  move-first - Read recent emails and move the first one to Archive"
    echo "  action     - Use action mode with input file (-i required)"
    echo ""
    echo "Examples:"
    echo "  $0                           # Read all emails (default)"
    echo "  $0 -m unread                 # Read only unread emails"
    echo "  $0 -m recent                 # Read 10 most recent emails"
    echo "  $0 -m flag-first             # Flag the most recent email"
    echo "  $0 -m move-first             # Move the most recent email to Archive"
    echo "  $0 -m action -i actions.jsonl  # Process actions from file"
    echo "  $0 -c config_other.json      # Use different config file"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -i|--input)
            INPUT_FILE="$2"
            shift 2
            ;;
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -r|--rebuild)
            REBUILD=1
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
done

# Set default mode
if [ -z "$MODE" ]; then
    MODE="read"
fi

echo -e "${GREEN}=== Outlook Actions Test Runner ===${NC}"
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

# Validate mode
case $MODE in
    read|unread|recent|flag-first|move-first|action)
        ;;
    *)
        echo -e "${RED}Error: Invalid mode: $MODE${NC}"
        echo "Valid modes: read, unread, recent, flag-first, move-first, action"
        exit 1
        ;;
esac

# Check for action mode requirements
if [ "$MODE" = "action" ] && [ -z "$INPUT_FILE" ]; then
    echo -e "${RED}Error: Action mode requires an input file (-i)${NC}"
    exit 1
fi

if [ "$MODE" = "action" ] && [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}Error: Input file not found: $INPUT_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}Test Configuration:${NC}"
echo "  Mode:        ${BLUE}$MODE${NC}"
echo "  Config file: $CONFIG_FILE"
echo "  Output dir:  $OUTPUT_DIR"
if [ -n "$INPUT_FILE" ]; then
    echo "  Input file:  $INPUT_FILE"
fi
echo ""

# Build or rebuild Docker image
if [ $REBUILD -eq 1 ] || ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo -e "${YELLOW}Building Docker image '$IMAGE_NAME'...${NC}"
    docker build -t "$IMAGE_NAME" .
    echo ""
fi

# Prepare test configuration based on mode
case $MODE in
    read)
        OUTPUT_FILE="emails.jsonl"
        echo -e "${GREEN}Running test: Read all emails from inbox${NC}"
        echo ""

        docker run --rm \
            -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
            -v "$(pwd)/$OUTPUT_DIR:/output" \
            "$IMAGE_NAME" \
            --config /config.json \
            --output "/output/$OUTPUT_FILE"
        ;;

    unread)
        OUTPUT_FILE="unread-emails.jsonl"
        echo -e "${GREEN}Running test: Read unread emails from inbox${NC}"
        echo ""

        # Create temporary input file for unread emails
        TMP_INPUT=$(mktemp)
        echo '{"action":"read","folder":"inbox","filter":"isRead eq false"}' > "$TMP_INPUT"

        docker run --rm \
            -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
            -v "$TMP_INPUT:/input.jsonl:ro" \
            -v "$(pwd)/$OUTPUT_DIR:/output" \
            "$IMAGE_NAME" \
            --config /config.json \
            --input /input.jsonl \
            --output "/output/$OUTPUT_FILE"

        rm "$TMP_INPUT"
        ;;

    recent)
        OUTPUT_FILE="recent-emails.jsonl"
        echo -e "${GREEN}Running test: Read 10 most recent emails${NC}"
        echo ""

        # Create temporary input file for recent emails
        TMP_INPUT=$(mktemp)
        echo '{"action":"read","folder":"inbox","top":10}' > "$TMP_INPUT"

        docker run --rm \
            -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
            -v "$TMP_INPUT:/input.jsonl:ro" \
            -v "$(pwd)/$OUTPUT_DIR:/output" \
            "$IMAGE_NAME" \
            --config /config.json \
            --input /input.jsonl \
            --output "/output/$OUTPUT_FILE"

        rm "$TMP_INPUT"
        ;;

    flag-first)
        OUTPUT_FILE="flag-first-result.jsonl"
        echo -e "${GREEN}Running test: Flag the first email${NC}"
        echo ""

        # Step 1: Read recent emails to get the first email ID
        echo "Step 1: Reading recent emails to get first email ID..."
        TMP_INPUT=$(mktemp)
        TMP_OUTPUT=$(mktemp)
        echo '{"action":"read","folder":"inbox","top":5}' > "$TMP_INPUT"

        docker run --rm \
            -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
            -v "$TMP_INPUT:/input.jsonl:ro" \
            -v "$(dirname $TMP_OUTPUT):/tmpoutput" \
            "$IMAGE_NAME" \
            --config /config.json \
            --input /input.jsonl \
            --output "/tmpoutput/$(basename $TMP_OUTPUT)"

        # Extract the first email ID
        FIRST_EMAIL_ID=$(head -1 "$TMP_OUTPUT" | jq -r '.id' 2>/dev/null)

        if [ -z "$FIRST_EMAIL_ID" ] || [ "$FIRST_EMAIL_ID" = "null" ]; then
            echo -e "${RED}Error: Could not find any emails to flag${NC}"
            rm "$TMP_INPUT" "$TMP_OUTPUT"
            exit 1
        fi

        echo "Found first email ID: $FIRST_EMAIL_ID"
        FIRST_EMAIL_SUBJECT=$(head -1 "$TMP_OUTPUT" | jq -r '.subject' 2>/dev/null)
        echo "Email subject: $FIRST_EMAIL_SUBJECT"
        echo ""

        # Step 2: Create action to flag this email
        echo "Step 2: Flagging the email..."
        echo "{\"action\":\"read\",\"folder\":\"inbox\",\"top\":5}" > "$TMP_INPUT"
        echo "{\"action\":\"state\",\"mail\":\"$FIRST_EMAIL_ID\",\"flagged\":true}" >> "$TMP_INPUT"

        docker run --rm \
            -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
            -v "$TMP_INPUT:/input.jsonl:ro" \
            -v "$(pwd)/$OUTPUT_DIR:/output" \
            "$IMAGE_NAME" \
            --config /config.json \
            --input /input.jsonl \
            --output "/output/$OUTPUT_FILE"

        rm "$TMP_INPUT" "$TMP_OUTPUT"
        ;;

    move-first)
        OUTPUT_FILE="move-first-result.jsonl"
        echo -e "${GREEN}Running test: Move the first email to Archive${NC}"
        echo ""

        # Step 1: Read recent emails to get the first email ID
        echo "Step 1: Reading recent emails to get first email ID..."
        TMP_INPUT=$(mktemp)
        TMP_OUTPUT=$(mktemp)
        echo '{"action":"read","folder":"inbox","top":5}' > "$TMP_INPUT"

        docker run --rm \
            -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
            -v "$TMP_INPUT:/input.jsonl:ro" \
            -v "$(dirname $TMP_OUTPUT):/tmpoutput" \
            "$IMAGE_NAME" \
            --config /config.json \
            --input /input.jsonl \
            --output "/tmpoutput/$(basename $TMP_OUTPUT)"

        # Extract the first email ID
        FIRST_EMAIL_ID=$(head -1 "$TMP_OUTPUT" | jq -r '.id' 2>/dev/null)

        if [ -z "$FIRST_EMAIL_ID" ] || [ "$FIRST_EMAIL_ID" = "null" ]; then
            echo -e "${RED}Error: Could not find any emails to move${NC}"
            rm "$TMP_INPUT" "$TMP_OUTPUT"
            exit 1
        fi

        echo "Found first email ID: $FIRST_EMAIL_ID"
        FIRST_EMAIL_SUBJECT=$(head -1 "$TMP_OUTPUT" | jq -r '.subject' 2>/dev/null)
        echo "Email subject: $FIRST_EMAIL_SUBJECT"
        echo ""

        # Step 2: Create action to move this email to Archive
        echo "Step 2: Moving the email to Archive folder..."
        echo "{\"action\":\"read\",\"folder\":\"inbox\",\"top\":5}" > "$TMP_INPUT"
        echo "{\"action\":\"move\",\"mail\":\"$FIRST_EMAIL_ID\",\"folder\":\"archive\"}" >> "$TMP_INPUT"

        docker run --rm \
            -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
            -v "$TMP_INPUT:/input.jsonl:ro" \
            -v "$(pwd)/$OUTPUT_DIR:/output" \
            "$IMAGE_NAME" \
            --config /config.json \
            --input /input.jsonl \
            --output "/output/$OUTPUT_FILE"

        rm "$TMP_INPUT" "$TMP_OUTPUT"
        ;;

    action)
        OUTPUT_FILE="action-results.jsonl"
        echo -e "${GREEN}Running test: Process actions from input file${NC}"
        echo ""

        docker run --rm \
            -v "$(pwd)/$CONFIG_FILE:/config.json:ro" \
            -v "$(pwd)/$INPUT_FILE:/input.jsonl:ro" \
            -v "$(pwd)/$OUTPUT_DIR:/output" \
            "$IMAGE_NAME" \
            --config /config.json \
            --input /input.jsonl \
            --output "/output/$OUTPUT_FILE"
        ;;
esac

echo ""
echo -e "${GREEN}=== Test Complete ===${NC}"
echo ""
echo "Output written to: ${BLUE}$OUTPUT_DIR/$OUTPUT_FILE${NC}"
echo ""

# Count results
if [ -f "$OUTPUT_DIR/$OUTPUT_FILE" ]; then
    LINE_COUNT=$(wc -l < "$OUTPUT_DIR/$OUTPUT_FILE" | tr -d ' ')
    echo "Results: ${GREEN}$LINE_COUNT${NC} records"
    echo ""

    # Show preview of results
    echo -e "${YELLOW}Preview (first 3 results):${NC}"
    head -3 "$OUTPUT_DIR/$OUTPUT_FILE" | jq -c '{subject: .subject, from: .from.address, receivedDateTime: .receivedDateTime, isRead: .isRead}' 2>/dev/null || head -3 "$OUTPUT_DIR/$OUTPUT_FILE"
    echo ""
fi

echo "To view all results:"
echo "  cat $OUTPUT_DIR/$OUTPUT_FILE | jq"
echo ""
echo "To view subjects only:"
echo "  cat $OUTPUT_DIR/$OUTPUT_FILE | jq -r '.subject'"
echo ""
