# outlook-actions

Perform actions on Microsoft Outlook emails using Microsoft Graph API

## Overview

This pipeline step connects to Microsoft Outlook via the Microsoft Graph API to perform various actions on emails. It supports:
- Reading emails from folders (with filtering and pagination)
- Moving emails between folders
- Updating email states (flagged, read status)

The step can operate in two modes:
1. **Action mode** (with input file): Process multiple actions from a JSONL input file
2. **Legacy mode** (config only): Read emails based on config parameters (backward compatible)

## Docker Image

This application is available as a Docker image on Docker Hub: `pipelining/outlook-actions`

### Usage

**Action mode** (with input file):
```bash
docker run -v /path/to/config.json:/config.json \
           -v /path/to/actions.jsonl:/input.jsonl \
           -v /path/to/output:/output \
           pipelining/outlook-actions:latest \
           --config /config.json \
           --input /input.jsonl \
           --output /output/results.jsonl
```

**Legacy mode** (config only):
```bash
docker run -v /path/to/config.json:/config.json \
           -v /path/to/output:/output \
           pipelining/outlook-actions:latest \
           --config /config.json \
           --output /output/emails.jsonl
```

To see this documentation, run without arguments:
```bash
docker run pipelining/outlook-actions:latest
```

## Authentication

This step uses **App-Only Authentication** (Client Credentials flow) to access user mailboxes. You need to:

1. Register an application in Azure AD
2. Grant the application the following API permissions:
   - `Mail.Read` (Application permission, requires admin consent)
   - Or `Mail.ReadBasic` for basic email access
3. Create a client secret for the application
4. Have an admin grant consent for the permissions

### Azure AD App Setup

1. Go to Azure Portal > Azure Active Directory > App registrations
2. Click "New registration"
3. Name your app and register it
4. Note the **Application (client) ID** and **Directory (tenant) ID**
5. Go to "Certificates & secrets" > Create a new client secret
6. Go to "API permissions" > Add permission > Microsoft Graph > Application permissions
7. Add `Mail.Read` and `Mail.ReadWrite` permissions (ReadWrite needed for move/state actions)
8. Click "Grant admin consent"

## Input Format (Action Mode)

When using an input file, each line should contain a JSON object with an `action` field specifying the action to perform.

### Read Action

Read emails from a folder:

```json
{"action": "read", "folder": "inbox"}
{"action": "read", "folder": "sentitems", "top": 50}
{"action": "read", "folder": "inbox", "filter": "isRead eq false"}
```

**Fields:**
- `action`: Must be "read"
- `folder`: Folder name or ID (default: "inbox")
- `top`: Maximum number of emails to retrieve (default: 100)
- `filter`: Optional OData filter query

**Output:** Returns list of email objects (see Output Format section)

### Move Action

Move an email to a different folder:

```json
{"action": "move", "mail": "AAMkAGI2...", "folder": "Archive"}
```

**Fields:**
- `action`: Must be "move"
- `mail`: Email ID (from the `id` field of an email object)
- `folder`: Target folder name or ID

**Output:** Returns success/failure status

### State Action

Update email state (flags, read status):

```json
{"action": "state", "mail": "AAMkAGI2...", "flagged": true, "isRead": false}
{"action": "state", "mail": "AAMkAGI2...", "flagged": false}
{"action": "state", "mail": "AAMkAGI2...", "isRead": true}
```

**Fields:**
- `action`: Must be "state"
- `mail`: Email ID (from the `id` field of an email object)
- `flagged`: Set flag status (true/false), optional
- `isRead`: Set read status (true/false), optional

**Output:** Returns success/failure status

### Input Example

```jsonl
{"action": "read", "folder": "inbox"}
{"action": "move", "mail": "AAMkAGI2THk0AAA=", "folder": "Archive"}
{"action": "state", "mail": "AAMkAGI2THk1AAA=", "flagged": true, "isRead": true}
```

## Configuration Parameters

| Name         | Required | Description                                                              |
|--------------|----------|--------------------------------------------------------------------------|
| tenantId     | X        | Azure AD tenant ID                                                       |
| clientId     | X        | Application (client) ID from Azure AD                                    |
| clientSecret | X        | Client secret value                                                      |
| userId       | X        | Email address or ID of the user whose mailbox to access                 |
| folder       |          | Folder to read from (default: "inbox")                                   |
| top          |          | Maximum number of emails to retrieve (default: 100)                      |
| filter       |          | OData filter query to filter emails                                     |
| scopes       |          | List of OAuth scopes (default: ["https://graph.microsoft.com/.default"]) |

**Notes:**
  * **tenantId**: Find this in Azure Portal > Azure Active Directory > Overview
  * **clientId**: The Application (client) ID from your app registration
  * **clientSecret**: The secret value (not the secret ID) from "Certificates & secrets"
  * **userId**: Can be the user's email address (e.g., "user@company.com") or their Azure AD object ID
  * **folder**: Common values are "inbox", "sentitems", "drafts", "deleteditems", or a folder ID
  * **top**: Maximum number of emails to retrieve. The API may return fewer if pagination limits are reached
  * **filter**: OData filter expression (e.g., "isRead eq false", "receivedDateTime ge 2024-01-01T00:00:00Z")
  * **scopes**: Usually the default scope is sufficient for app-only authentication

### Configuration Example

```json
{
  "tenantId": "12345678-1234-1234-1234-123456789abc",
  "clientId": "87654321-4321-4321-4321-abcdef123456",
  "clientSecret": "your-client-secret-value",
  "userId": "user@company.com",
  "folder": "inbox",
  "top": 50,
  "filter": "isRead eq false"
}
```

This configuration will retrieve up to 50 unread emails from the user's inbox.

## Output Format

The output JSONL file contains one JSON object per email with the following structure:

```json
{
  "id": "AAMkAGI2...",
  "subject": "Meeting tomorrow",
  "from": {
    "name": "John Doe",
    "address": "john@example.com"
  },
  "to": [
    {
      "name": "Jane Smith",
      "address": "jane@example.com"
    }
  ],
  "cc": [],
  "receivedDateTime": "2024-11-07T10:30:00Z",
  "sentDateTime": "2024-11-07T10:29:55Z",
  "hasAttachments": false,
  "importance": "normal",
  "isRead": false,
  "isDraft": false,
  "bodyPreview": "Hi Jane, Let's meet tomorrow at 2pm...",
  "body": {
    "contentType": "html",
    "content": "<html><body>Hi Jane,<br/>Let's meet tomorrow at 2pm...</body></html>"
  },
  "conversationId": "AAQkAGI2...",
  "internetMessageId": "<message-id@example.com>",
  "webLink": "https://outlook.office365.com/owa/?ItemID=..."
}
```

### Output Fields

- `id`: Unique message ID
- `subject`: Email subject line
- `from`: Sender information (name and email address)
- `to`: List of primary recipients
- `cc`: List of CC recipients
- `receivedDateTime`: When the email was received (ISO 8601 format)
- `sentDateTime`: When the email was sent (ISO 8601 format)
- `hasAttachments`: Whether the email has attachments
- `importance`: Email importance (low, normal, high)
- `isRead`: Whether the email has been read
- `isDraft`: Whether this is a draft message
- `bodyPreview`: Plain text preview of the email body
- `body`: Full email body with content type (html or text)
- `conversationId`: ID of the conversation thread
- `internetMessageId`: Standard email message ID header
- `webLink`: Link to view the email in Outlook Web

## Filter Examples

The `filter` parameter uses OData query syntax. Here are some common examples:

- Unread emails: `"isRead eq false"`
- Emails from specific sender: `"from/emailAddress/address eq 'sender@example.com'"`
- Emails received after a date: `"receivedDateTime ge 2024-01-01T00:00:00Z"`
- Emails with attachments: `"hasAttachments eq true"`
- Important emails: `"importance eq 'high'"`
- Combined filters: `"isRead eq false and hasAttachments eq true"`

## Folder Names

Common folder names you can use:
- `inbox` - Main inbox
- `sentitems` - Sent items
- `drafts` - Draft messages
- `deleteditems` - Deleted items (trash)
- `junkemail` - Junk/spam folder

You can also use a specific folder ID if you know it.

## Error Handling

- If authentication fails, the step will exit with an error
- If the user doesn't exist or permissions are insufficient, an error will be logged
- Network errors and API errors are caught and logged to stderr
- The step will exit with a non-zero code on failure

## Permissions Required

The Azure AD application needs the following **Application** permissions (not Delegated):
- `Mail.Read` - Required for reading emails
- `Mail.ReadWrite` - Required for moving emails and updating email states
- Or `Mail.ReadBasic` - For basic email reading only (excludes body content, move, and state actions)

**Note:** If you only need to read emails (legacy mode or read actions only), `Mail.Read` is sufficient. For move and state actions, `Mail.ReadWrite` is required.

An Azure AD administrator must grant consent for these permissions.

## Security Notes

- Store client secrets securely (use environment variables or secret management)
- Use the principle of least privilege - only grant necessary permissions
- Rotate client secrets regularly
- Monitor application usage through Azure AD audit logs
- Consider using certificate-based authentication instead of client secrets for production
