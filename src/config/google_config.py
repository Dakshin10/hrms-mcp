import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Base paths resolved relative to this config file
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

def get_credentials_dir() -> Path:
    """Returns the absolute Path to the credentials directory."""
    return CREDENTIALS_DIR

def get_client_secret_path() -> Path:
    """Returns the absolute Path to the client_secret.json file."""
    return CLIENT_SECRET_PATH

def get_token_path() -> Path:
    """Returns the absolute Path to the token.json file."""
    return TOKEN_PATH

def load_google_credentials() -> dict:
    """
    Locates, validates, and loads the client_secret.json credentials file.
    Raises FileNotFoundError or ValueError with descriptive error messages.
    """
    if not CREDENTIALS_DIR.exists():
        raise FileNotFoundError(
            f"Credentials directory is missing at: {CREDENTIALS_DIR}. "
            "Please create the directory and place client_secret.json inside it."
        )
    if not CLIENT_SECRET_PATH.exists():
        raise FileNotFoundError(
            f"Google OAuth client_secret.json is missing at: {CLIENT_SECRET_PATH}. "
            "Please place your Google OAuth Client Secrets JSON file in the credentials directory."
        )
    
    try:
        with open(CLIENT_SECRET_PATH, "r") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse client_secret.json: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load client_secret.json: {e}")

def get_google_client_id() -> str:
    """
    Extracts the client ID from the Google credentials.
    """
    data = load_google_credentials()
    for key in ["installed", "web"]:
        if key in data and "client_id" in data[key]:
            return data[key]["client_id"]
    raise ValueError("client_id not found in client_secret.json under 'installed' or 'web' keys.")

def get_google_client_secret() -> str:
    """
    Extracts the client secret from the Google credentials.
    """
    data = load_google_credentials()
    for key in ["installed", "web"]:
        if key in data and "client_secret" in data[key]:
            return data[key]["client_secret"]
    raise ValueError("client_secret not found in client_secret.json under 'installed' or 'web' keys.")
