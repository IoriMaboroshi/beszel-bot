"""Beszel PocketBase API client."""
import time
import aiohttp
from typing import Optional


class BeszelAPI:
    def __init__(self, base_url: str, user: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self._token: Optional[str] = None
        self._token_expires: float = 0
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _auth(self) -> str:
        """Authenticate and get JWT token."""
        now = time.time()
        if self._token and now < self._token_expires:
            return self._token

        session = await self._get_session()
        async with session.post(
            f"{self.base_url}/api/collections/users/auth-with-password",
            json={"identity": self.user, "password": self.password},
        ) as resp:
            data = await resp.json()
            self._token = data["token"]
            self._token_expires = now + 6000
            return self._token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        token = await self._auth()
        session = await self._get_session()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        async with session.request(
            method, f"{self.base_url}{path}", headers=headers, **kwargs
        ) as resp:
            return await resp.json()

    async def get_systems(self) -> list[dict]:
        """Get all monitored systems."""
        data = await self._request("GET", "/api/collections/systems/records?perPage=100")
        return data.get("items", [])

    async def get_system(self, system_id: str) -> dict:
        """Get a single system by ID."""
        return await self._request("GET", f"/api/collections/systems/records/{system_id}")

    async def get_alerts(self, page: int = 1, per_page: int = 20) -> dict:
        """Get alert history."""
        return await self._request(
            "GET",
            f"/api/collections/alerts/records?page={page}&perPage={per_page}&sort=-created",
        )

    async def get_system_stats(self, system_id: str, hours: int = 1) -> list[dict]:
        """Get historical stats for a system."""
        data = await self._request(
            "GET",
            f"/api/collections/stats/records?filter=system='{system_id}'&sort=-created&perPage=200",
        )
        return data.get("items", [])

    async def get_container_stats(
        self, system_id: str = None, stat_type: str = "1m", per_page: int = 500
    ) -> list[dict]:
        """Get container historical statistics from container_stats collection.

        Each record has: {type, system, created, stats: [{n, c, m, b:[in,out]}]}
        """
        filters = [f"type='{stat_type}'"]
        if system_id:
            filters.append(f"system='{system_id}'")
        filter_str = " && ".join(filters)
        data = await self._request(
            "GET",
            f"/api/collections/container_stats/records?filter={filter_str}&sort=-created&perPage={per_page}",
        )
        return data.get("items", [])

    async def get_containers(self, system_id: str = None) -> list[dict]:
        """Get Docker containers, optionally filtered by system."""
        url = "/api/collections/containers/records?perPage=100"
        if system_id:
            url += f"&filter=system='{system_id}'"
        data = await self._request("GET", url)
        return data.get("items", [])
