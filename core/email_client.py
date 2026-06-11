import asyncio
import re
import httpx
from loguru import logger


class TempMailClient:

    def __init__(self, base_url: str, poll_interval: int = 5, poll_timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self._client = httpx.AsyncClient(timeout=30)

    async def create_address(self) -> dict:
        resp = await self._client.post(f"{self.base_url}/api/v1/addresses")
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Created temp email: {data['email']}")
        return data

    async def list_emails(self, token: str) -> list:
        resp = await self._client.get(f"{self.base_url}/api/v1/{token}/emails")
        resp.raise_for_status()
        return resp.json().get("emails", [])

    async def get_email(self, token: str, email_id: str) -> dict:
        resp = await self._client.get(f"{self.base_url}/api/v1/{token}/emails/{email_id}")
        resp.raise_for_status()
        return resp.json()

    async def wait_for_verification_code(self, token: str) -> str:
        elapsed = 0
        while elapsed < self.poll_timeout:
            emails = await self.list_emails(token)
            for mail in emails:
                subject = mail.get("subject", "")
                match = re.match(r"^\s*(\d{6})", subject)
                if match:
                    code = match.group(1)
                    logger.success(f"Got verification code: {code}")
                    return code

                detail = await self.get_email(token, mail["id"])
                for body_field in ("text_body", "html_body", "body", "text", "html"):
                    body = detail.get(body_field, "") or ""
                    match = re.search(r"\b(\d{6})\b", body)
                    if match:
                        code = match.group(1)
                        logger.success(f"Got verification code from body: {code}")
                        return code

            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

        raise TimeoutError(f"No verification email received within {self.poll_timeout}s")

    async def close(self):
        await self._client.aclose()
