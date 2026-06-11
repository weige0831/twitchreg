import json
import httpx
from loguru import logger


class CDKApiClient:

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self._client = httpx.AsyncClient(
            timeout=30,
            headers={"Authorization": f"Bearer {api_token}"},
        )

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def upload_account(
        self,
        username: str,
        password: str,
        email: str,
        auth_token: str,
        cookies: list[dict],
    ) -> dict | None:
        if not self.enabled:
            logger.warning("CDK API base_url not configured, skipping upload")
            return None

        payload = {
            "username": username,
            "password": password,
            "email": email,
            "auth_token": auth_token,
            "cookies": json.dumps(cookies),
        }
        resp = await self._client.post(f"{self.base_url}/api/accounts/upload", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.success(f"Uploaded account {username} to CDK system")
        return data

    async def worker_heartbeat(self, worker_name: str, worker_type: str = "register") -> dict | None:
        if not self.enabled:
            return None

        payload = {"worker_name": worker_name, "worker_type": worker_type}
        resp = await self._client.post(f"{self.base_url}/api/workers/heartbeat", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()
