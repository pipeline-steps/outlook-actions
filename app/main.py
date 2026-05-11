import sys
import json
import os
from datetime import datetime, timezone
from msal import PublicClientApplication, SerializableTokenCache
import requests
from steputil import StepArgs, StepArgsBuilder


def get_access_token_delegated(tenant_id, client_id, scopes, token_cache_file=".token_cache.json"):
    """
    Authenticate using device code flow (delegated authentication).
    User signs in once, then tokens are cached for future use.

    The token cache stores only refresh tokens and account information,
    not access tokens. Access tokens are acquired on-demand using the
    cached refresh token.

    Args:
        tenant_id: Azure AD tenant ID
        client_id: Application (client) ID
        scopes: List of OAuth scopes
        token_cache_file: Path to store cached tokens (refresh tokens only)

    Returns:
        Access token string
    """
    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"

        # Create a custom token cache that excludes access tokens
        class RefreshTokenOnlyCache(SerializableTokenCache):
            def add(self, event, **kwargs):
                """Override to exclude access tokens from cache."""
                super().add(event, **kwargs)
                # After adding, remove any access tokens
                self._remove_access_tokens()

            def _remove_access_tokens(self):
                """Remove access tokens from cache, keeping only refresh tokens and accounts."""
                cache_data = json.loads(self.serialize()) if self.serialize() else {}
                if "AccessToken" in cache_data:
                    del cache_data["AccessToken"]
                    # Deserialize the modified cache back
                    super().deserialize(json.dumps(cache_data))

        # Create or load token cache
        cache = RefreshTokenOnlyCache()
        if os.path.exists(token_cache_file):
            with open(token_cache_file, 'r') as f:
                cache.deserialize(f.read())

        # Create public client application with token cache
        app = PublicClientApplication(
            client_id,
            authority=authority,
            token_cache=cache
        )

        # Try to get token from cache first
        accounts = app.get_accounts()
        if accounts:
            print("Using cached credentials...")
            result = app.acquire_token_silent(scopes, account=accounts[0])
            if result and "access_token" in result:
                # Save cache (will exclude access tokens via our custom cache)
                if cache.has_state_changed:
                    with open(token_cache_file, 'w') as f:
                        f.write(cache.serialize())
                return result["access_token"]

        # If no cached token, use device code flow (interactive)
        print("\nNo cached token found. Starting interactive sign-in...\n")
        flow = app.initiate_device_flow(scopes=scopes)

        if "user_code" not in flow:
            raise ValueError(f"Failed to create device flow: {flow.get('error_description', 'Unknown error')}")

        # Display instructions to user
        print("=" * 60)
        print(flow["message"])
        print("=" * 60)
        print("\nWaiting for you to complete sign-in in your browser...")

        # Wait for user to authenticate
        result = app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            # Save token cache to file (access tokens will be excluded)
            # Force save on initial authentication since custom cache operations
            # may reset the has_state_changed flag
            with open(token_cache_file, 'w') as f:
                f.write(cache.serialize())

            print(f"\nAuthentication successful! Token cached to {token_cache_file}")
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
        user_id: User's email address or ID (not used with delegated auth, uses /me/)
        folder: Folder to read from (e.g., 'inbox', 'sentitems', 'drafts')
        top: Maximum number of emails to retrieve
        filter_query: Optional OData filter query

    Returns:
        List of email messages
    """
    # With delegated permissions, use /me/ endpoint (automatically the signed-in user)
    if folder and folder.lower() != 'inbox':
        base_url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages"
    else:
        # Use direct messages endpoint for inbox
        base_url = f"https://graph.microsoft.com/v1.0/me/messages"

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
        user_id: User's email address or ID (not used with delegated auth)
        message_id: ID of the message to move
        target_folder: Target folder name or ID

    Returns:
        Result dictionary with success status
    """
    url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/move"

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
        user_id: User's email address or ID (not used with delegated auth)
        message_id: ID of the message to update
        flagged: Set flag status (True/False) or None to leave unchanged
        is_read: Set read status (True/False) or None to leave unchanged

    Returns:
        Result dictionary with success status
    """
    url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}"

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
    # Use delegated permissions with specific scopes
    # Note: offline_access is added automatically by MSAL, don't include it
    scopes = step.config.scopes if step.config.scopes else [
        "Mail.Read",
        "Mail.ReadWrite",
        "Mail.Send"
    ]

    access_token = get_access_token_delegated(tenant_id, client_id, scopes)
    print("Authentication successful")

    # With delegated auth, user_id is not required (uses signed-in user)
    # Keep for backward compatibility but it's not used
    user_id = step.config.userId if step.config.userId else "me"

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
    # clientSecret and userId are no longer required for delegated auth
    return True


if __name__ == "__main__":
    main(StepArgsBuilder()
         .input(optional=True)
         .output()
         .config("tenantId")
         .config("clientId")
         .config("clientSecret", optional=True)
         .config("userId", optional=True)
         .config("folder", optional=True)
         .config("top", optional=True)
         .config("filter", optional=True)
         .config("scopes", optional=True)
         .validate(validate_config)
         .build()
         )
