# Delegated Authentication Setup (No PowerShell Required!)

This guide shows you how to set up Outlook Actions using **Delegated Permissions** instead of Application Permissions. This method does **NOT** require PowerShell or Application Access Policies.

## Benefits of Delegated Permissions

✅ **No PowerShell required** - All setup done in Azure Portal web UI
✅ **Automatic user scope** - Access automatically limited to signed-in user
✅ **No client secret needed** - More secure, no secrets to manage
✅ **Simple setup** - Fewer configuration steps

## Azure Portal Setup (Web UI Only)

### Step 1: Configure App Registration

1. Go to [Azure Portal](https://portal.azure.com) → **Azure Active Directory** → **App Registrations**
2. Select your app: `70041f03-3533-4d6e-9793-2688aa4484c4`

### Step 2: Update API Permissions

1. Go to **API Permissions**
2. **Remove** existing Application permissions if any:
   - Remove `Mail.Read` (Application)
   - Remove `Mail.ReadWrite` (Application)
3. **Add** Delegated permissions:
   - Click **Add a permission**
   - Select **Microsoft Graph**
   - Choose **Delegated permissions**
   - Search and add:
     - ✅ `Mail.Read`
     - ✅ `Mail.ReadWrite`
     - ✅ `Mail.Send`
     - ✅ `offline_access` (important for token caching!)
4. Click **Grant admin consent for [Your Organization]**

### Step 3: Enable Public Client Flow

1. Go to **Authentication** → **Advanced settings**
2. Set **Allow public client flows** to **Yes**
3. Click **Save**

## Configuration

Your `config.json` no longer needs `clientSecret` or `userId`:

```json
{
  "tenantId": "e491852e-b96f-41c3-8a30-e698fcf6103f",
  "clientId": "70041f03-3533-4d6e-9793-2688aa4484c4",
  "folder": "inbox",
  "top": 10
}
```

## First Run - Interactive Sign-In

The first time you run the application, you'll see:

```
Authenticating with Microsoft Graph API...

No cached token found. Starting interactive sign-in...

============================================================
To sign in, use a web browser to open the page https://microsoft.com/devicelogin
and enter the code ABC123XYZ to authenticate.
============================================================

Waiting for you to complete sign-in in your browser...
```

### What to do:

1. Open https://microsoft.com/devicelogin in your browser
2. Enter the code shown (e.g., `ABC123XYZ`)
3. Sign in with your Microsoft account (`testuser@gmbhkneissler.onmicrosoft.com`)
4. Grant permissions when prompted
5. Return to the terminal - authentication will complete automatically

## Subsequent Runs - Automatic

After the first sign-in, tokens are cached and authentication is automatic:

```
Authenticating with Microsoft Graph API...
Using cached credentials...
Authentication successful
```

No more sign-in required until the token expires (tokens are automatically refreshed).

## Running the Application

```bash
# Read emails
python3 app/main.py --config config.json --output output/emails.jsonl

# With actions file
python3 app/main.py --config config.json --input actions.jsonl --output output/results.jsonl
```

## Token Caching & Refresh Token Backup

The application uses two files for token management:

1. **`.token_cache.json`** - Full token cache (access tokens, refresh tokens, account info)
   - Managed automatically by MSAL
   - Regenerated as needed

2. **`.refresh_token`** - Backup of just the refresh token
   - Created after successful authentication
   - Used to restore session if `.token_cache.json` is deleted
   - Enables automatic re-authentication without user interaction

### How It Works

**Normal flow:**
- Access token valid for ~1 hour
- Refresh token automatically renews access token
- Both stored in `.token_cache.json`

**Recovery flow (when `.token_cache.json` is deleted):**
1. App checks for `.refresh_token` file
2. Reconstructs minimal token cache from refresh token
3. Gets new access token automatically (no user interaction!)
4. Rebuilds full `.token_cache.json`

**Result:** Even if you delete `.token_cache.json`, the app can restore your session from `.refresh_token` for up to 90 days without requiring you to sign in again.

### Important Security Notes

- **Both files contain sensitive credentials** - Never commit to git
- Both are automatically excluded in `.gitignore`
- Tokens are cached locally (MSAL handles this securely)
- Access is automatically limited to the signed-in user's mailbox
- No client secrets to manage or rotate
- Tokens can be revoked in Azure Portal if needed
- Refresh tokens expire after ~90 days of inactivity

## Troubleshooting

**"Device code expired"**
- You took too long to enter the code. Run again and complete within 15 minutes.

**"Permission denied"**
- Make sure admin consent was granted in Step 2 of Azure setup.

**"Public client flow not allowed"**
- Enable public client flows in Step 3 of Azure setup.

## Comparison: Application vs Delegated

| Feature | Application Permissions | Delegated Permissions |
|---------|------------------------|----------------------|
| Setup | Azure + PowerShell | Azure Web UI only |
| Client Secret | Required | Not needed |
| User Scope | Requires PowerShell policy | Automatic |
| User Interaction | None | First run only |
| Security | High (with proper policy) | High (inherent) |
| Token Caching | N/A | Automatic |
