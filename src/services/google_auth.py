import logging
import os
from pathlib import Path
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

def get_gspread_client() -> gspread.Client:
    """
    Authenticates against Google APIs using local token.json or client_secret.json,
    maintains token lifecycle, and returns an authorized gspread.Client instance.
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    token_path = project_root / "token.json"
    secret_path = project_root / "client_secret.json"

    creds = None

    # 1. Load token.json if it exists
    if token_path.exists():
        try:
            logger.info("Loading Google credentials from token.json")
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load credentials from token.json: {e}")
            creds = None

    # 2. Handle invalid/expired credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing expired Google credentials silently")
                creds.refresh(Request())
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                logger.warning(f"Silently refreshing token failed: {e}. Falling back to flow.")
                creds = None

        # 3. If still no valid credentials, run the local server flow
        if not creds or not creds.valid:
            if not secret_path.exists():
                raise FileNotFoundError(
                    f"Required client_secret.json file is missing from the project root at: {secret_path}. "
                    f"Please place your Google OAuth Client Secrets JSON file in the project root."
                )

            logger.info("Starting local OAuth2 authorization flow")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
                creds = flow.run_local_server(port=0)
                # Overwrite/save new token
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                logger.error(f"Failed to execute OAuth2 flow: {e}")
                raise

    # 4. Authorize gspread client
    logger.info("Authorizing gspread client with credentials")
    client = gspread.authorize(creds)
    return client
