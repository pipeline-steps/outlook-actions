import sys
import json
from datetime import datetime, timezone
from msal import ConfidentialClientApplication
import requests
from steputil import StepArgs, StepArgsBuilder


def get_access_token(tenant_id, client_id, client_secret, scopes):
    """
    Authenticate using client credentials flow (app-only authentication).

    Args:
        tenant_id: Azure AD tenant ID
        client_id: Application (client) ID
        client_secret: Client secret value
        scopes: List of OAuth scopes

    Returns:
        Access token string
    """
    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret
        )

        result = app.acquire_token_for_client(scopes=scopes)

        if "access_token" in result:
            return result["access_token"]
        else:
            error_msg = result.get("error_description", result.get("error", "Unknown error"))
            print(f"Failed to acquire token: {error_msg}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error during authentication: {e}", file=sys.stderr)
        sys.exit(1)


def fetch_emails(access_token, user_id, folder, top=100, filter_query=None):
    """
    Fetch emails from a user's mailbox.

    Args:
        access_token: OAuth access token
        user_id: User's email address or ID
        folder: Folder to read from (e.g., 'inbox', 'sentitems', 'drafts')
        top: Maximum number of emails to retrieve
        filter_query: Optional OData filter query

    Returns:
        List of email messages
    """
    # Build the API URL - use messages endpoint directly instead of going through mailFolders
    # This works better with app-only permissions
    if folder and folder.lower() != 'inbox':
        base_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailFolders/{folder}/messages"
    else:
        # Use direct messages endpoint for inbox (more compatible with app permissions)
        base_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/messages"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    params = {
        '$top': top,
        '$orderby': 'receivedDateTime DESC'
    }

    if filter_query:
        params['$filter'] = filter_query

    messages = []
    url = base_url

    try:
        while url:
            response = requests.get(url, headers=headers, params=params if url == base_url else None)

            if response.status_code != 200:
                print(f"Error fetching emails: Status {response.status_code}", file=sys.stderr)
                print(f"Response headers: {dict(response.headers)}", file=sys.stderr)
                print(f"Response body: {response.text}", file=sys.stderr)
                try:
                    error_json = response.json()
                    if 'error' in error_json:
                        error_msg = error_json['error'].get('message', 'No message')
                        error_code = error_json['error'].get('code', 'Unknown')
                        print(f"Error code: {error_code}", file=sys.stderr)
                        print(f"Error message: {error_msg}", file=sys.stderr)
                except Exception as e:
                    print(f"Could not parse error JSON: {e}", file=sys.stderr)
                sys.exit(1)

            data = response.json()
            messages.extend(data.get('value', []))

            # Check for pagination
            url = data.get('@odata.nextLink')

            # Respect the top limit
            if len(messages) >= top:
                messages = messages[:top]
                break

        return messages

    except Exception as e:
        print(f"Error fetching emails: {e}", file=sys.stderr)
        sys.exit(1)


def move_email(access_token, user_id, message_id, target_folder):
    """
    Move an email to a different folder.

    Args:
        access_token: OAuth access token
        user_id: User's email address or ID
        message_id: ID of the message to move
        target_folder: Target folder name or ID

    Returns:
        Result dictionary with success status
    """
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/messages/{message_id}/move"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    body = {
        'destinationId': target_folder
    }

    try:
        response = requests.post(url, headers=headers, json=body)

        if response.status_code in [200, 201]:
            return {
                'success': True,
                'message': f"Email {message_id} moved to {target_folder}"
            }
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            return {
                'success': False,
                'message': f"Failed to move email {message_id}: {error_msg}"
            }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error moving email {message_id}: {str(e)}"
        }


def update_email_state(access_token, user_id, message_id, flagged=None, is_read=None):
    """
    Update email state (flagged, read status, etc.).

    Args:
        access_token: OAuth access token
        user_id: User's email address or ID
        message_id: ID of the message to update
        flagged: Set flag status (True/False) or None to leave unchanged
        is_read: Set read status (True/False) or None to leave unchanged

    Returns:
        Result dictionary with success status
    """
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/messages/{message_id}"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Build the update body
    body = {}
    if flagged is not None:
        body['flag'] = {
            'flagStatus': 'flagged' if flagged else 'notFlagged'
        }
    if is_read is not None:
        body['isRead'] = is_read

    if not body:
        return {
            'success': False,
            'message': f"No state changes specified for email {message_id}"
        }

    try:
        response = requests.patch(url, headers=headers, json=body)

        if response.status_code == 200:
            return {
                'success': True,
                'message': f"Email {message_id} state updated"
            }
        else:
            error_msg = f"Status {response.status_code}: {response.text}"
            return {
                'success': False,
                'message': f"Failed to update email {message_id}: {error_msg}"
            }
    except Exception as e:
        return {
            'success': False,
            'message': f"Error updating email {message_id}: {str(e)}"
        }


def parse_email(message):
    """
    Parse an email message into a simplified format.

    Args:
        message: Raw message from Graph API

    Returns:
        Parsed message dictionary
    """
    return {
        'id': message.get('id'),
        'subject': message.get('subject'),
        'from': {
            'name': message.get('from', {}).get('emailAddress', {}).get('name'),
            'address': message.get('from', {}).get('emailAddress', {}).get('address')
        },
        'to': [
            {
                'name': recipient.get('emailAddress', {}).get('name'),
                'address': recipient.get('emailAddress', {}).get('address')
            }
            for recipient in message.get('toRecipients', [])
        ],
        'cc': [
            {
                'name': recipient.get('emailAddress', {}).get('name'),
                'address': recipient.get('emailAddress', {}).get('address')
            }
            for recipient in message.get('ccRecipients', [])
        ],
        'receivedDateTime': message.get('receivedDateTime'),
        'sentDateTime': message.get('sentDateTime'),
        'hasAttachments': message.get('hasAttachments', False),
        'importance': message.get('importance'),
        'isRead': message.get('isRead', False),
        'isDraft': message.get('isDraft', False),
        'bodyPreview': message.get('bodyPreview'),
        'body': {
            'contentType': message.get('body', {}).get('contentType'),
            'content': message.get('body', {}).get('content')
        },
        'conversationId': message.get('conversationId'),
        'internetMessageId': message.get('internetMessageId'),
        'webLink': message.get('webLink')
    }


def process_action(action, access_token, user_id, step):
    """
    Process a single action from the input file.

    Args:
        action: Action dictionary with 'action' field and action-specific parameters
        access_token: OAuth access token
        user_id: User's email address or ID
        step: StepArgs object

    Returns:
        Result dictionary or list of results
    """
    action_type = action.get('action')

    if action_type == 'read':
        # Read emails from a folder
        folder = action.get('folder', 'inbox')
        top = action.get('top', 100)
        filter_query = action.get('filter')

        print(f"Reading emails from folder '{folder}'...")
        messages = fetch_emails(access_token, user_id, folder, top, filter_query)
        parsed_messages = [parse_email(msg) for msg in messages]
        print(f"Retrieved {len(parsed_messages)} emails")
        return parsed_messages

    elif action_type == 'move':
        # Move an email to a different folder
        message_id = action.get('mail')
        target_folder = action.get('folder')

        if not message_id or not target_folder:
            return {
                'success': False,
                'message': 'Move action requires both "mail" and "folder" fields'
            }

        print(f"Moving email {message_id} to folder '{target_folder}'...")
        result = move_email(access_token, user_id, message_id, target_folder)
        print(result['message'])
        return result

    elif action_type == 'state':
        # Update email state
        message_id = action.get('mail')
        flagged = action.get('flagged')
        is_read = action.get('isRead')

        if not message_id:
            return {
                'success': False,
                'message': 'State action requires "mail" field'
            }

        print(f"Updating state for email {message_id}...")
        result = update_email_state(access_token, user_id, message_id, flagged=flagged, is_read=is_read)
        print(result['message'])
        return result

    else:
        return {
            'success': False,
            'message': f'Unknown action type: {action_type}'
        }


def main(step: StepArgs):
    # Authentication
    print("Authenticating with Microsoft Graph API...")
    tenant_id = step.config.tenantId
    client_id = step.config.clientId
    client_secret = step.config.clientSecret
    scopes = step.config.scopes if step.config.scopes else ["https://graph.microsoft.com/.default"]

    access_token = get_access_token(tenant_id, client_id, client_secret, scopes)
    print("Authentication successful")

    user_id = step.config.userId

    # Check if input file is provided
    if step.input.path:
        # Process actions from input file
        actions = step.input.readJsons()
        print(f"Processing {len(actions)} actions from input file...")

        all_results = []
        for i, action in enumerate(actions):
            print(f"\nAction {i+1}/{len(actions)}: {action.get('action', 'unknown')}")
            result = process_action(action, access_token, user_id, step)

            # Handle different result types
            if isinstance(result, list):
                # For 'read' action, result is a list of emails
                all_results.extend(result)
            else:
                # For 'move' and 'state' actions, result is a single status dict
                all_results.append(result)

        # Write all results to output
        step.output.writeJsons(all_results)
        print(f"\nDone. Processed {len(actions)} actions, wrote {len(all_results)} results to output")

    else:
        # Use legacy config-based approach for backward compatibility
        folder = step.config.folder if step.config.folder else "inbox"
        top = step.config.top if step.config.top else 100
        filter_query = step.config.filter if step.config.filter else None

        print(f"Fetching emails for user {user_id} from folder '{folder}'...")
        if filter_query:
            print(f"Applying filter: {filter_query}")

        messages = fetch_emails(access_token, user_id, folder, top, filter_query)
        print(f"Retrieved {len(messages)} emails")

        # Parse and output emails
        parsed_messages = [parse_email(msg) for msg in messages]
        step.output.writeJsons(parsed_messages)

        print(f"Done. Exported {len(parsed_messages)} emails to output")


def validate_config(config):
    """Validation function that checks config rules."""
    if not config.tenantId:
        print("Parameter `tenantId` is required", file=sys.stderr)
        return False
    if not config.clientId:
        print("Parameter `clientId` is required", file=sys.stderr)
        return False
    if not config.clientSecret:
        print("Parameter `clientSecret` is required", file=sys.stderr)
        return False
    if not config.userId:
        print("Parameter `userId` is required", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    main(StepArgsBuilder()
         .input(optional=True)
         .output()
         .config("tenantId")
         .config("clientId")
         .config("clientSecret")
         .config("userId")
         .config("folder", optional=True)
         .config("top", optional=True)
         .config("filter", optional=True)
         .config("scopes", optional=True)
         .validate(validate_config)
         .build()
         )
