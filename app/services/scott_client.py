import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse

import httpx

from app.config import get_config


def _parse_bool_env(value: str) -> bool:
    return value.lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class ScottSettings:
    base_url: str = os.getenv("SCOTT_BASE_URL", "http://192.168.0.118:8000").rstrip("/")
    verify_tls: bool = os.getenv("SCOTT_VERIFY_TLS", "false").lower() in ("1", "true", "yes")
    timeout_seconds: float = float(os.getenv("SCOTT_TIMEOUT_SECONDS", "30"))

    @classmethod
    def from_config(cls) -> "ScottSettings":
        config = get_config()
        return cls(
            base_url=config.scott_base_url.rstrip("/"),
            verify_tls=os.getenv("SCOTT_VERIFY_TLS", "false").lower() in ("1", "true", "yes"),
            timeout_seconds=float(config.scott_timeout),
        )


class ScottClient:
    """
    Minimal client for BOS's SCOTT FastAPI server.
    Tries base_url first, then HTTPS :8443 and HTTP :8000 fallbacks.
    """

    def __init__(self, settings: Optional[ScottSettings] = None):
        self.s = settings or ScottSettings.from_config()

    def _candidates(self) -> list[str]:
        cands = [self.s.base_url]
        parsed = urlparse(self.s.base_url)
        host = parsed.hostname
        if host:
            fallbacks = [
                f"https://{host}:8443",
                f"http://{host}:8000",
            ]
            cands.extend(fallbacks)
        return list(dict.fromkeys(cands))

    async def _aget_json(self, path: str) -> Dict[str, Any]:
        last_err: Exception | None = None
        for base in self._candidates():
            url = f"{base}{path}"
            try:
                async with httpx.AsyncClient(
                    verify=self.s.verify_tls,
                    timeout=self.s.timeout_seconds,
                ) as client:
                    response = await client.get(url)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return {"status": "ok", "url": url, "text": response.text}
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"SCOTT unreachable or endpoint not found: {path}. Last error: {last_err}")

    def _get_json(self, path: str) -> Dict[str, Any]:
        last_err: Exception | None = None
        for base in self._candidates():
            url = f"{base}{path}"
            try:
                with httpx.Client(
                    verify=self.s.verify_tls,
                    timeout=self.s.timeout_seconds,
                ) as client:
                    response = client.get(url)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return {"status": "ok", "url": url, "text": response.text}
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"SCOTT unreachable or endpoint not found: {path}. Last error: {last_err}")

    async def ahealth(self) -> Dict[str, Any]:
        for path in ("/api/health", "/health"):
            try:
                return await self._aget_json(path)
            except Exception:
                continue
        raise RuntimeError("SCOTT health not reachable on /api/health or /health")

    def health(self) -> Dict[str, Any]:
        for path in ("/api/health", "/health"):
            try:
                return self._get_json(path)
            except Exception:
                continue
        raise RuntimeError("SCOTT health not reachable on /api/health or /health")

    async def atopics(self) -> Dict[str, Any]:
        try:
            return await self._aget_json("/api/topics")
        except Exception:
            return await self._aget_json("/topics")

    def topics(self) -> Dict[str, Any]:
        try:
            return self._get_json("/api/topics")
        except Exception:
            return self._get_json("/topics")

    async def anews(self, topic: str) -> Dict[str, Any]:
        encoded = quote(topic, safe="")
        try:
            return await self._aget_json(f"/api/news/{encoded}")
        except Exception:
            return await self._aget_json(f"/news/{encoded}")

    def news(self, topic: str) -> Dict[str, Any]:
        encoded = quote(topic, safe="")
        try:
            return self._get_json(f"/api/news/{encoded}")
        except Exception:
            return self._get_json(f"/news/{encoded}")
