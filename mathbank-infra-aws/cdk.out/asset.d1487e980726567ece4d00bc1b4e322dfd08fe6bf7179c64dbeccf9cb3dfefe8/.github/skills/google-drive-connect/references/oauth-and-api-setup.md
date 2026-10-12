# OAuth And API Setup For Google Drive

## 1. Create A Google Cloud Project
1. Open Google Cloud Console.
2. Create a new project (or select existing).

## 2. Enable Google Drive API
1. Go to APIs & Services > Library.
2. Search for Google Drive API.
3. Click Enable.

## 3. Choose Authentication Mode

### OAuth2 (User Drive Access)
1. Go to APIs & Services > OAuth consent screen.
2. Configure app name, support email, and test users (for testing mode).
3. Go to Credentials > Create Credentials > OAuth client ID.
4. Choose Desktop app.
5. Download JSON and save as `credentials.json`.

### Service Account (Automation)
1. Go to IAM & Admin > Service Accounts.
2. Create a service account.
3. Add a JSON key and download it.
4. Save as `credentials.json`.
5. Share target Drive folder/files with the service account email.

## 4. Run The Script
- OAuth2 list files:
  - `node .github/skills/google-drive-connect/scripts/connect-drive.mjs --mode oauth2 --task list --credentials ./credentials.json --token ./token.json`
- Service account list files:
  - `node .github/skills/google-drive-connect/scripts/connect-drive.mjs --mode service-account --task list --credentials ./credentials.json`

## 5. Security Practices
- Do not commit credentials or token files.
- Add these to `.gitignore`:
  - `credentials.json`
  - `token.json`
- Rotate leaked keys immediately.
