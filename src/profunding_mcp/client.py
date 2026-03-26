"""HTTP client for the ProFunding REST API."""

import httpx
from typing import Any, Optional

from .config import API_URL, API_KEY


class ProFundingClient:
    """Thin wrapper around the ProFunding REST API."""

    def __init__(self):
        headers = {"Content-Type": "application/json"}
        if API_KEY:
            headers["X-API-Key"] = API_KEY
        self._client = httpx.AsyncClient(
            base_url=API_URL,
            headers=headers,
            timeout=30.0,
        )
        self._tier: Optional[str] = None

    async def validate_key(self) -> dict:
        """Validate the API key at startup and cache the tier."""
        if not API_KEY:
            self._tier = "free"
            return {"valid": True, "tier": "free"}
        resp = await self._client.get("/mcp/validate")
        resp.raise_for_status()
        data = resp.json()
        self._tier = data.get("tier", "free")
        return data

    @property
    def tier(self) -> str:
        return self._tier or "free"

    def is_paid(self) -> bool:
        return self._tier == "paid"

    def _raise_with_detail(self, resp: httpx.Response) -> None:
        """Raise an httpx.HTTPStatusError with the response body in the message."""
        if resp.is_success:
            return
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise httpx.HTTPStatusError(
            f"{resp.status_code}: {detail}",
            request=resp.request,
            response=resp,
        )

    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        """GET request to the API."""
        resp = await self._client.get(path, params=params)
        self._raise_with_detail(resp)
        return resp.json()

    async def post(self, path: str, json: Optional[dict] = None) -> Any:
        """POST request to the API."""
        resp = await self._client.post(path, json=json)
        self._raise_with_detail(resp)
        return resp.json()

    async def delete(self, path: str) -> Any:
        """DELETE request to the API."""
        resp = await self._client.delete(path)
        self._raise_with_detail(resp)
        return resp.json()

    async def patch(self, path: str, json: Optional[dict] = None) -> Any:
        """PATCH request to the API."""
        resp = await self._client.patch(path, json=json)
        self._raise_with_detail(resp)
        return resp.json()

    async def close(self):
        await self._client.aclose()


# Singleton
client = ProFundingClient()
