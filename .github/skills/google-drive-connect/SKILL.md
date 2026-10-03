---
name: google-drive-connect
description: 'Connect to Google Drive with OAuth2 or service accounts. Use when you need to list, upload, download, or search files in Drive from local scripts or automation workflows.'
argument-hint: 'Choose auth mode (oauth2|service-account) and task (list|upload|download|search)'
---

# Google Drive Connect

Use this skill to set up and run a reliable Google Drive connection for scripts and automations.

## When To Use
- You need to connect a local script to Google Drive.
- You want OAuth2 for user-owned Drive files.
- You want service account auth for shared automation workflows.
- You need a repeatable way to list, upload, download, or search Drive files.

## Prerequisites
- Google Cloud project with Drive API enabled.
- OAuth client credentials or service account key.
- Node.js 18+.

Setup details are in [OAuth and API setup](./references/oauth-and-api-setup.md).

## Procedure
1. Install dependencies:
   - `npm install googleapis @google-cloud/local-auth`
2. Save your Google credentials JSON file.
3. Run the sample script:
   - `node .github/skills/google-drive-connect/scripts/connect-drive.mjs --mode oauth2 --task list`
4. For service account mode:
   - `node .github/skills/google-drive-connect/scripts/connect-drive.mjs --mode service-account --task list`

## Script Arguments
- `--mode`: `oauth2` or `service-account`
- `--task`: `list`, `upload`, `download`, `search`
- `--credentials`: path to credentials JSON (default `./credentials.json`)
- `--token`: path to OAuth token cache (default `./token.json`)
- `--query`: Drive query for `search`
- `--file`: local file path for `upload`
- `--name`: destination filename for `upload`
- `--id`: Drive file ID for `download`
- `--out`: output path for `download`

## Notes
- OAuth2 is best when accessing a real user account's Drive.
- Service accounts need explicit access to target folders/files via sharing.
- Keep credential files out of source control.
