# Quick Start Guide

## Prerequisites

1. Docker installed on your system
2. An Azure AD application with:
   - Application (client) ID
   - Directory (tenant) ID
   - Client secret
   - `Mail.Read` permission (application permission, admin consented)

## Setup

### 1. Create Configuration File

Copy the example configuration:

```bash
cp config.example.json config.json
```

### 2. Edit Configuration

Edit `config.json` with your actual values:

```json
{
  "tenantId": "your-tenant-id-here",
  "clientId": "your-client-id-here",
  "clientSecret": "your-client-secret-here",
  "userId": "user@yourcompany.com",
  "folder": "inbox",
  "top": 50,
  "filter": "isRead eq false"
}
```

### 3. Run

Execute the run script:

```bash
./run.sh
```

The script will:
- Build the Docker image (if not already built)
- Run the container with your config
- Output emails to `./output/emails.jsonl`

## View Results

View the raw JSON output:

```bash
cat output/emails.jsonl
```

Or pretty-print with jq (if installed):

```bash
cat output/emails.jsonl | jq
```

View just the subjects:

```bash
cat output/emails.jsonl | jq -r '.subject'
```

## Configuration Options

### Required
- `tenantId` - Your Azure AD tenant ID
- `clientId` - Your application (client) ID
- `clientSecret` - Your client secret value
- `userId` - Email address to fetch emails for

### Optional
- `folder` - Folder to read from (default: "inbox")
- `top` - Max emails to retrieve (default: 100)
- `filter` - OData filter query (e.g., "isRead eq false")
- `scopes` - OAuth scopes (default: ["https://graph.microsoft.com/.default"])

## Common Filters

Unread emails only:
```json
"filter": "isRead eq false"
```

Emails from the last 7 days:
```json
"filter": "receivedDateTime ge 2024-11-01T00:00:00Z"
```

Emails with attachments:
```json
"filter": "hasAttachments eq true"
```

Important unread emails:
```json
"filter": "isRead eq false and importance eq 'high'"
```

## Common Folders

- `inbox` - Main inbox
- `sentitems` - Sent items
- `drafts` - Drafts
- `deleteditems` - Trash
- `junkemail` - Spam/junk

## Troubleshooting

**Authentication errors:**
- Verify your tenantId, clientId, and clientSecret are correct
- Ensure admin consent has been granted for Mail.Read permission
- Check that the application is not expired in Azure AD

**Permission errors:**
- Verify the app has `Mail.Read` (Application permission, not Delegated)
- Ensure admin consent was granted
- Check the userId exists in your Azure AD

**No emails returned:**
- Check your filter is not too restrictive
- Verify the folder name is correct
- Try removing the filter to see all emails

## Advanced Usage

### Use custom config location:

```bash
CONFIG_FILE=/path/to/myconfig.json ./run.sh
```

### Use custom output directory:

```bash
OUTPUT_DIR=/path/to/output ./run.sh
```

### Run directly with Docker:

```bash
docker run --rm \
  -v ./config.json:/config.json:ro \
  -v ./output:/output \
  outlook-actions:test \
  --config /config.json \
  --output /output/emails.jsonl
```

## Next Steps

- See [README.md](README.md) for complete documentation
- Customize filters for your use case
- Integrate into your pipeline
