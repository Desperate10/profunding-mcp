"""HTTP client for the ProFunding REST API."""

import httpx
from typing import Any, Optional

from .config import API_URL, API_KEY


class RequestTimeout(Exception):
    """No answer arrived — which is NOT the same as "it did not happen".

    httpx raises ReadTimeout with an EMPTY str(), so every caller doing
    `f"Trade failed: {e}"` printed a bare "Trade failed: " for an order that
    may well have executed. Observed 2026-08-17: two 01xyz closes reported
    "Close failed:" while the venue showed the position closed — one of them
    HAD gone through. Same class as the browser clients'
    FillConfirmationUnavailableError: unreadable must never read as didn't
    happen, least of all on a money path.
    """


# A write legitimately outruns a read here: an order now places AND reads its
# fill back (venue confirm ladders run to ~12s on the slowest), so the old
# flat 30s sat close enough to the real duration to time out SUCCEEDING
# orders. Reads stay tight so a hung read fails fast.
_READ_TIMEOUT_S = 30.0
_WRITE_TIMEOUT_S = 90.0


class ProFundingClient:
    """Thin wrapper around the ProFunding REST API."""

    def __init__(self):
        headers = {"Content-Type": "application/json"}
        if API_KEY:
            headers["X-API-Key"] = API_KEY
        self._client = httpx.AsyncClient(
            base_url=API_URL,
            headers=headers,
            timeout=_READ_TIMEOUT_S,
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

    @staticmethod
    def _timed_out(path: str, seconds: float, wrote: bool) -> "RequestTimeout":
        """Turn an empty-message timeout into something a caller can act on.
        A write says so explicitly — the whole point is that the caller must
        CHECK before retrying rather than assume nothing happened."""
        tail = (" The order MAY have been placed — check get_positions / "
                "get_open_orders before retrying." if wrote else "")
        return RequestTimeout(
            f"no answer from the API within {seconds:.0f}s ({path}).{tail}")

    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        """GET request to the API."""
        try:
            resp = await self._client.get(path, params=params)
        except httpx.TimeoutException as e:
            raise self._timed_out(path, _READ_TIMEOUT_S, wrote=False) from e
        self._raise_with_detail(resp)
        return resp.json()

    async def post(self, path: str, json: Optional[dict] = None) -> Any:
        """POST request to the API — the money path, on the write budget."""
        try:
            resp = await self._client.post(path, json=json,
                                           timeout=_WRITE_TIMEOUT_S)
        except httpx.TimeoutException as e:
            raise self._timed_out(path, _WRITE_TIMEOUT_S, wrote=True) from e
        self._raise_with_detail(resp)
        return resp.json()

    async def delete(self, path: str) -> Any:
        """DELETE request to the API (cancels — also a write)."""
        try:
            resp = await self._client.delete(path, timeout=_WRITE_TIMEOUT_S)
        except httpx.TimeoutException as e:
            raise self._timed_out(path, _WRITE_TIMEOUT_S, wrote=True) from e
        self._raise_with_detail(resp)
        return resp.json()

    async def patch(self, path: str, json: Optional[dict] = None) -> Any:
        """PATCH request to the API."""
        try:
            resp = await self._client.patch(path, json=json,
                                            timeout=_WRITE_TIMEOUT_S)
        except httpx.TimeoutException as e:
            raise self._timed_out(path, _WRITE_TIMEOUT_S, wrote=True) from e
        self._raise_with_detail(resp)
        return resp.json()

    async def close(self):
        await self._client.aclose()


# Singleton
client = ProFundingClient()
