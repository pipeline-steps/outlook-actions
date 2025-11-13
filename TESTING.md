# Testing Guide for outlook-actions

This guide explains how to use the `run.sh` script to test the outlook-actions step locally.

## Prerequisites

1. **Docker** installed and running
2. **Azure AD credentials** configured in `config.json`:
   - tenantId
   - clientId
   - clientSecret
   - userId (email address to access)

## Quick Start

### 1. Setup Configuration

Copy the example config and fill in your credentials:

```bash
cp config.example.json config.json
# Edit config.json with your Azure AD credentials
```

### 2. Run Tests

The script supports several test modes:

#### Test Mode: Read (Default)
Read all emails from inbox using legacy config mode:

```bash
./run.sh
# or explicitly:
./run.sh -m read
```

#### Test Mode: Unread
Read only unread emails from inbox:

```bash
./run.sh -m unread
```

#### Test Mode: Recent
Read the 10 most recent emails:

```bash
./run.sh -m recent
```

#### Test Mode: Flag First
Read recent emails and flag the first (most recent) one:

```bash
./run.sh -m flag-first
```

This mode demonstrates:
- Reading emails to get IDs
- Using the state action to flag an email
- Combining multiple actions in one run

#### Test Mode: Action
Process custom actions from an input file:

```bash
# Create actions file
cat > my-actions.jsonl <<EOF
{"action":"read","folder":"inbox","top":5}
{"action":"read","folder":"sentitems","top":3}
EOF

# Run with actions
./run.sh -m action -i my-actions.jsonl
```

## Advanced Usage

### Use Different Config File

```bash
./run.sh -c config_prod.json -m unread
```

### Change Output Directory

```bash
./run.sh -o ./results -m recent
```

### Force Rebuild Docker Image

```bash
./run.sh -r
```

## Output

Results are written to `./output/` directory with different filenames based on mode:

- **read mode**: `output/emails.jsonl`
- **unread mode**: `output/unread-emails.jsonl`
- **recent mode**: `output/recent-emails.jsonl`
- **action mode**: `output/action-results.jsonl`

## Viewing Results

The script shows a preview after completion. To view all results:

```bash
# View all with jq formatting
cat output/emails.jsonl | jq

# View specific fields
cat output/emails.jsonl | jq -c '{subject, from: .from.address, date: .receivedDateTime}'

# View just subjects
cat output/emails.jsonl | jq -r '.subject'

# Count emails
wc -l output/emails.jsonl
```

## Example Actions File

Create `actions.jsonl` with multiple actions:

```jsonl
{"action":"read","folder":"inbox","top":10}
{"action":"read","folder":"inbox","filter":"isRead eq false"}
{"action":"read","folder":"sentitems","top":5}
```

Then run:

```bash
./run.sh -m action -i actions.jsonl
```

## Common Filters

When creating custom action files, use these OData filters:

- Unread emails: `"filter":"isRead eq false"`
- Emails with attachments: `"filter":"hasAttachments eq true"`
- High importance: `"filter":"importance eq 'high'"`
- From specific sender: `"filter":"from/emailAddress/address eq 'sender@example.com'"`
- After specific date: `"filter":"receivedDateTime ge 2024-01-01T00:00:00Z"`
- Combined: `"filter":"isRead eq false and hasAttachments eq true"`

## Troubleshooting

### Authentication Errors

If you see authentication errors:
- Verify your credentials in config.json
- Ensure the Azure AD app has proper permissions (Mail.Read)
- Check that admin consent has been granted

### Permission Errors

If you get permission denied errors:
- Verify the app has Application permissions (not Delegated)
- Ensure Mail.Read or Mail.ReadWrite is granted
- Check that admin consent is granted

### No Results

If no emails are returned:
- Check the userId is correct
- Verify the folder name is correct (use lowercase: "inbox", "sentitems")
- Check filter syntax if using filters

## Help

View all available options:

```bash
./run.sh --help
```
