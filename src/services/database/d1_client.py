import asyncio
import httpx
from src.core.config.settings import settings
from src.core.logging.logger import logger
from src.core.exceptions.errors import D1Error


class D1Client:
    def __init__(self):
        self.account_id = settings.d1_account_id
        self.database_id = settings.d1_database_id
        self.api_token = settings.d1_api_token

        self.base_url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/d1/database/{self.database_id}/query"
        )

    async def execute(self, sql: str, params=None):
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "sql": sql,
            "params": params or []
        }

        max_retries = 3
        backoff = 1.0

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        self.base_url,
                        headers=headers,
                        json=payload
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    if not data.get("success"):
                        errors = data.get("errors", [])
                        err_msg = errors[0].get("message") if errors else "Unknown D1 error"
                        raise D1Error(f"D1 Query Failed: {err_msg} (Response: {data})")
                        
                    return data["result"][0]
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                # Do not retry on client errors (4xx) except 429 Too Many Requests
                if status_code < 500 and status_code != 429:
                    logger.error(f"D1 Client Error ({status_code}): {e.response.text}")
                    raise D1Error(f"D1 client error: {e.response.text}") from e
                
                if attempt == max_retries:
                    logger.error(f"D1 Request failed after {max_retries} retries: {e}")
                    raise D1Error(f"D1 connection failed: {e}") from e
                
                logger.warning(f"D1 Request failed with status {status_code}, retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff *= 2.0
            except httpx.RequestError as e:
                if attempt == max_retries:
                    logger.error(f"D1 Request failed after {max_retries} retries: {e}")
                    raise D1Error(f"D1 connection failed: {e}") from e
                
                logger.warning(f"D1 connection failed, retrying in {backoff}s... Error: {e}")
                await asyncio.sleep(backoff)
                backoff *= 2.0
            except D1Error as e:
                # Do not retry syntax or query runtime errors
                logger.error(f"D1 execution error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in D1 execution: {e}")
                raise D1Error(f"Unexpected D1 error: {e}") from e