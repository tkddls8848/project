"""Rate-limited, robots-aware HTTP transport for institutional sites."""

import asyncio
import time
from dataclasses import dataclass
from email.message import Message
from typing import Dict, Mapping, Optional
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import aiohttp

from utils.url_guard import rejection_reason_async


@dataclass(frozen=True)
class TransportConfig:
    per_host_concurrency: int = 1
    request_delay: float = 0.5
    timeout: float = 10.0
    user_agent: str = "NaraPortalHarvester/1.0 (+public-data-research)"
    max_body_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        if self.per_host_concurrency not in (1, 2):
            raise ValueError("per_host_concurrency must be 1 or 2")
        if self.request_delay < 0:
            raise ValueError("request_delay must be non-negative")
        if self.timeout <= 0 or self.max_body_bytes <= 0:
            raise ValueError("timeout and max_body_bytes must be positive")


@dataclass
class HttpResponse:
    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def text(self) -> str:
        message = Message()
        content_type = self.headers.get("Content-Type", "")
        if content_type:
            message["content-type"] = content_type
        charset = message.get_content_charset() or "utf-8"
        return self.body.decode(charset, errors="replace")


@dataclass
class RobotsDecision:
    allowed: bool
    reason: str
    sitemaps: tuple[str, ...] = ()


class SafeHttpTransport:
    """HTTP client enforcing all external-site safety invariants.

    Robots files and GET responses are cached per run. Redirects are disabled so
    a permitted host cannot silently redirect a probe onto a different host.
    """

    def __init__(self, config: Optional[TransportConfig] = None, session: Optional[aiohttp.ClientSession] = None):
        self.config = config or TransportConfig()
        self._session = session
        self._owns_session = session is None
        self._limiters: Dict[str, asyncio.Semaphore] = {}
        self._request_locks: Dict[str, asyncio.Lock] = {}
        self._last_request: Dict[str, float] = {}
        self._robots: Dict[str, RobotsDecision] = {}
        self._robot_parsers: Dict[str, RobotFileParser] = {}
        self._robots_locks: Dict[str, asyncio.Lock] = {}
        self._cache: Dict[str, HttpResponse] = {}

    async def __aenter__(self) -> "SafeHttpTransport":
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            connector = aiohttp.TCPConnector(limit_per_host=self.config.per_host_concurrency)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": self.config.user_agent},
            )
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlsplit(url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    async def robots_decision(self, url: str) -> RobotsDecision:
        origin = self._origin(url)
        # robots.txt를 받는 것부터가 요청이다. 대상 확인은 그보다 먼저 해야 한다.
        # robots는 SSRF 방어가 아니며, robots가 없는 호스트는 오히려 허용된다.
        blocked = await rejection_reason_async(url)
        if blocked is not None:
            decision = RobotsDecision(False, f"blocked_target:{blocked}")
            self._robots[origin] = decision
            return decision

        cached = self._robots.get(origin)
        if cached is not None:
            return self._decision_for_url(origin, url, cached)

        lock = self._robots_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            cached = self._robots.get(origin)
            if cached is not None:
                return self._decision_for_url(origin, url, cached)
            robots_url = urljoin(origin + "/", "robots.txt")
            try:
                response = await self._raw_get(robots_url)
                if response.status in (401, 403):
                    decision = RobotsDecision(False, f"robots_http_{response.status}")
                elif 400 <= response.status < 500:
                    # RFC 9309 "unavailable": absence of a robots file permits access.
                    decision = RobotsDecision(True, f"robots_unavailable_http_{response.status}")
                elif 200 <= response.status < 300:
                    parser = RobotFileParser()
                    parser.set_url(robots_url)
                    parser.parse(response.text.splitlines())
                    sitemaps = tuple(parser.site_maps() or ())
                    allowed = parser.can_fetch(self.config.user_agent, url)
                    decision = RobotsDecision(allowed, "robots_allowed" if allowed else "robots_disallowed", sitemaps)
                    self._robot_parsers[origin] = parser
                else:
                    # Redirects and server failures are not silently interpreted as permission.
                    decision = RobotsDecision(False, f"robots_indeterminate_http_{response.status}")
            except Exception as exc:
                # Fail closed: if policy cannot be checked, do not probe the institution.
                decision = RobotsDecision(False, f"robots_fetch_error:{type(exc).__name__}:{exc}")
            self._robots[origin] = decision
            return self._decision_for_url(origin, url, decision)

    def _decision_for_url(self, origin: str, url: str, decision: RobotsDecision) -> RobotsDecision:
        parser = self._robot_parsers.get(origin)
        if parser is None:
            return decision
        allowed = parser.can_fetch(self.config.user_agent, url)
        return RobotsDecision(allowed, "robots_allowed" if allowed else "robots_disallowed", decision.sitemaps)

    async def get(self, url: str) -> HttpResponse:
        decision = await self.robots_decision(url)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        if url not in self._cache:
            self._cache[url] = await self._raw_get(url)
        return self._cache[url]

    async def _raw_get(self, url: str) -> HttpResponse:
        if self._session is None:
            raise RuntimeError("SafeHttpTransport must be used as an async context manager")
        host = (urlsplit(url).hostname or "").lower()
        limiter = self._limiters.setdefault(host, asyncio.Semaphore(self.config.per_host_concurrency))
        lock = self._request_locks.setdefault(host, asyncio.Lock())
        async with limiter:
            async with lock:
                remaining = self.config.request_delay - (time.monotonic() - self._last_request.get(host, 0.0))
                if remaining > 0:
                    await asyncio.sleep(remaining)
                self._last_request[host] = time.monotonic()
            async with self._session.get(url, allow_redirects=False) as response:
                # Reading from ``response.content`` hands back the raw payload,
                # so a gzip-encoded page arrives still compressed and every
                # downstream HTML parse silently sees nothing. ``response.read()``
                # applies the transfer decoding. Guard the size beforehand via
                # Content-Length so the cap still holds without buffering first.
                declared = response.headers.get("Content-Length")
                if declared and declared.isdigit() and int(declared) > self.config.max_body_bytes:
                    raise ValueError(f"response exceeds {self.config.max_body_bytes} bytes")
                body = await response.read()
                if len(body) > self.config.max_body_bytes:
                    raise ValueError(f"response exceeds {self.config.max_body_bytes} bytes")
                return HttpResponse(str(response.url), response.status, dict(response.headers), body)
