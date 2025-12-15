# Google API Credentials Setup

## Overview
This application requires Google API credentials to access Google Docs and Google Sheets. Follow these steps to set up your own credentials.

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID

## Step 2: Enable Required APIs

1. In the Google Cloud Console, go to "APIs & Services" > "Library"
2. Search for and enable:
   - **Google Docs API**
   - **Google Sheets API**

## Step 3: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Choose "Desktop application" as the application type
4. Give it a name (e.g., "Cantonese Anki Generator")
5. Download the JSON file

## Step 4: Set Up Your Credentials File

1. Rename the downloaded file to `credentials.json`
2. Place it in the root directory of this project
3. **NEVER commit this file to version control!**

## Step 5: First Run Authentication

1. Run the application for the first time
2. It will open a browser window for OAuth authentication
3. Grant the necessary permissions
4. A `token.json` file will be created automatically
5. **NEVER commit the token.json file to version control!**

## Security Notes

- ⚠️ **CRITICAL**: Never share your `credentials.json` or `token.json` files
- ⚠️ **CRITICAL**: Never commit these files to version control
- ⚠️ **CRITICAL**: If you accidentally expose these files, revoke the credentials immediately in Google Cloud Console

## Troubleshooting

### "File not found" error
- Ensure `credentials.json` is in the project root directory
- Check that the file is named exactly `credentials.json`

### Authentication fails
- Verify that the Google Docs API and Google Sheets API are enabled
- Check that your OAuth client is configured for "Desktop application"
- Try deleting `token.json` and re-authenticating

### Permission denied
- Ensure the Google Docs/Sheets you're trying to access are shared with your Google account
- Check that the documents have at least "Viewer" permissions