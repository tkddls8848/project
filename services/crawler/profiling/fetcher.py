"""Polite, bounded file retrieval for fileData download URLs."""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import aiohttp

from utils.url_guard import rejection_reason_async


@dataclass(frozen=True)
class FetchPolicy:
    """Network limits; sampling is deliberately the default."""

    sample_bytes: int = 1_048_576
    full_download: bool = False
    per_host_concurrency: int = 2
    request_delay: float = 1.0
    timeout: float = 30.0
    max_redirects: int = 5
    user_agent: str = "NaraPublicDataProfiler/1.0 (+polite metadata sampling)"
    robots_fail_closed: bool = True

    def __post_init__(self) -> None:
        if self.sample_bytes < 1:
            raise ValueError("sample_bytes must be positive")
        if self.per_host_concurrency < 1:
            raise ValueError("per_host_concurrency must be positive")
        if self.request_delay < 0 or self.timeout <= 0:
            raise ValueError("request_delay must be non-negative and timeout positive")


@dataclass
class FetchResult:
    name: str
    url: str
    status: str
    sample: bytes = field(default=b"", repr=False)
    final_url: Optional[str] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    filename: Optional[str] = None
    truncated: bool = False
    saved_path: Optional[str] = None
    robots_status: str = "unverified"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-safe metadata without embedding file bytes."""
        return {
            "name": self.name,
            "url": self.url,
            "status": self.status,
            "final_url": self.final_url,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "filename": self.filename,
            "sample_size": len(self.sample),
            "truncated": self.truncated,
            "saved_path": self.saved_path,
            "robots_status": self.robots_status,
            "error": self.error,
        }


@dataclass
class _HostState:
    semaphore: asyncio.Semaphore
    delay_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_request_at: float = 0.0


@dataclass(frozen=True)
class _RobotsDecision:
    allowed: bool
    status: str


class PoliteFileFetcher:
    """Fetch download URLs while enforcing limits independently per host."""

    def __init__(self, policy: Optional[FetchPolicy] = None) -> None:
        self.policy = policy or FetchPolicy()
        self._hosts: Dict[str, _HostState] = {}
        self._robots_tasks: Dict[str, "asyncio.Task[_RobotsDecision]"] = {}

    async def fetch_download_urls(
        self,
        download_urls: Mapping[str, str],
        *,
        output_dir: Optional[os.PathLike[str] | str] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> Dict[str, FetchResult]:
        """Fetch a fileData ``download_urls`` mapping.

        Full downloads are opt-in and require ``output_dir``. Sampling keeps only
        the leading ``sample_bytes`` in memory even when a server ignores Range.
        """
        if self.policy.full_download and output_dir is None:
            raise ValueError("output_dir is required when full_download=True")
        destination = Path(output_dir) if output_dir is not None else None
        if destination is not None and self.policy.full_download:
            destination.mkdir(parents=True, exist_ok=True)

        owns_session = session is None
        if session is None:
            timeout = aiohttp.ClientTimeout(total=self.policy.timeout)
            connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
            session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": self.policy.user_agent},
            )
        try:
            pairs = list(download_urls.items())
            fetched = await asyncio.gather(
                *(self._fetch_one(session, name, url, destination) for name, url in pairs)
            )
            return {name: result for (name, _), result in zip(pairs, fetched)}
        finally:
            if owns_session:
                await session.close()

    async def _fetch_one(
        self,
        session: aiohttp.ClientSession,
        name: str,
        url: str,
        output_dir: Optional[Path],
    ) -> FetchResult:
        result = FetchResult(name=name, url=url, status="error")
        current_url = url
        try:
            for redirect_number in range(self.policy.max_redirects + 1):
                # 홉마다 다시 본다. 처음만 확인하면 공개 호스트가 리다이렉트로
                # 내부망을 가리켜도 그대로 따라간다.
                blocked = await rejection_reason_async(current_url)
                if blocked is not None:
                    result.status = "blocked"
                    result.error = f"요청 대상이 아닙니다: {blocked}"
                    return result

                decision = await self._robots_allowed(session, current_url)
                result.robots_status = decision.status
                if not decision.allowed:
                    result.status = "robots_denied" if decision.status == "denied" else "unverified"
                    result.error = f"request blocked: robots.txt {decision.status}"
                    return result

                headers = {}
                if not self.policy.full_download:
                    headers["Range"] = f"bytes=0-{self.policy.sample_bytes - 1}"
                response = await self._request(session, "GET", current_url, headers=headers)
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    self._release_response(response)
                    if not location:
                        raise RuntimeError(f"HTTP {response.status} redirect without Location")
                    current_url = urljoin(current_url, location)
                    if redirect_number == self.policy.max_redirects:
                        raise RuntimeError("too many redirects")
                    continue
                if response.status not in {200, 206}:
                    status = response.status
                    self._release_response(response)
                    raise RuntimeError(f"HTTP {status}")

                result.final_url = str(response.url)
                result.content_type = response.headers.get("Content-Type")
                result.content_length = _parse_content_length(response.headers)
                result.filename = _response_filename(response.headers, result.final_url, name)
                if self.policy.full_download:
                    await self._save_full_response(response, result, output_dir)
                else:
                    try:
                        payload = await response.content.read(self.policy.sample_bytes + 1)
                    finally:
                        self._release_response(response, close=True)
                    result.sample = payload[: self.policy.sample_bytes]
                    result.truncated = len(payload) > self.policy.sample_bytes or _response_has_more(
                        response.headers, len(result.sample)
                    )
                result.status = "ok"
                return result
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError) as exc:
            result.error = str(exc)
            return result
        return result

    async def _save_full_response(
        self,
        response: aiohttp.ClientResponse,
        result: FetchResult,
        output_dir: Optional[Path],
    ) -> None:
        assert output_dir is not None
        filename = _safe_filename(result.filename or result.name)
        target = _unique_path(output_dir / filename)
        temporary = target.with_name(target.name + ".part")
        sample = bytearray()
        try:
            with temporary.open("wb") as stream:
                async for chunk in response.content.iter_chunked(64 * 1024):
                    stream.write(chunk)
                    if len(sample) < self.policy.sample_bytes:
                        sample.extend(chunk[: self.policy.sample_bytes - len(sample)])
            temporary.replace(target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            self._release_response(response)
        result.sample = bytes(sample)
        result.saved_path = str(target)
        result.truncated = False

    async def _robots_allowed(
        self, session: aiohttp.ClientSession, url: str
    ) -> _RobotsDecision:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
        task = self._robots_tasks.get(origin)
        if task is None:
            task = asyncio.create_task(self._load_robots(session, origin))
            self._robots_tasks[origin] = task
        base_decision = await task
        if base_decision.status != "verified":
            return base_decision
        parser = getattr(task, "_nara_robot_parser", None)
        if parser is None:
            return base_decision
        allowed = parser.can_fetch(self.policy.user_agent, url)
        return _RobotsDecision(allowed, "verified" if allowed else "denied")

    async def _load_robots(
        self, session: aiohttp.ClientSession, origin: str
    ) -> _RobotsDecision:
        robots_url = origin + "/robots.txt"
        try:
            for redirect_number in range(self.policy.max_redirects + 1):
                response = await self._request(session, "GET", robots_url)
                if response.status not in {301, 302, 303, 307, 308}:
                    break
                location = response.headers.get("Location")
                self._release_response(response)
                if not location or redirect_number == self.policy.max_redirects:
                    raise RuntimeError("invalid robots.txt redirect")
                robots_url = urljoin(robots_url, location)
            if response.status in {401, 403}:
                self._release_response(response)
                return _RobotsDecision(False, "denied")
            if response.status >= 400:
                self._release_response(response)
                return _RobotsDecision(True, "verified")
            try:
                body = await response.text(errors="replace")
            finally:
                self._release_response(response)
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(body.splitlines())
            task = asyncio.current_task()
            if task is not None:
                setattr(task, "_nara_robot_parser", parser)
            return _RobotsDecision(True, "verified")
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError):
            return _RobotsDecision(not self.policy.robots_fail_closed, "unverified")

    async def _request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
    ) -> aiohttp.ClientResponse:
        parsed = urlsplit(url)
        host_key = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
        state = self._hosts.setdefault(
            host_key,
            _HostState(asyncio.Semaphore(self.policy.per_host_concurrency)),
        )
        await state.semaphore.acquire()
        try:
            async with state.delay_lock:
                remaining = self.policy.request_delay - (time.monotonic() - state.last_request_at)
                if remaining > 0:
                    await asyncio.sleep(remaining)
                state.last_request_at = time.monotonic()
            response = await session.request(
                method,
                url,
                headers=dict(headers or {}),
                allow_redirects=False,
                timeout=self.policy.timeout,
            )
            setattr(response, "_nara_host_state", state)
            return response
        except BaseException:
            state.semaphore.release()
            raise

    @staticmethod
    def _release_response(response: aiohttp.ClientResponse, *, close: bool = False) -> None:
        state = getattr(response, "_nara_host_state", None)
        if state is not None:
            delattr(response, "_nara_host_state")
            state.semaphore.release()
        if close:
            response.close()
        else:
            response.release()


async def fetch_download_urls(
    download_urls: Mapping[str, str],
    *,
    policy: Optional[FetchPolicy] = None,
    output_dir: Optional[os.PathLike[str] | str] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> Dict[str, FetchResult]:
    """Convenience wrapper around :class:`PoliteFileFetcher`."""
    return await PoliteFileFetcher(policy).fetch_download_urls(
        download_urls, output_dir=output_dir, session=session
    )


def _parse_content_length(headers: Mapping[str, str]) -> Optional[int]:
    content_range = headers.get("Content-Range", "")
    match = re.search(r"/(\d+)$", content_range)
    value = match.group(1) if match else headers.get("Content-Length")
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _response_has_more(headers: Mapping[str, str], received: int) -> bool:
    total = _parse_content_length(headers)
    return total is not None and total > received


def _response_filename(headers: Mapping[str, str], url: str, fallback: str) -> str:
    disposition = headers.get("Content-Disposition", "")
    extended = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
    plain = re.search(r'filename\s*=\s*"?([^";]+)', disposition, re.I)
    if extended:
        return unquote(extended.group(1)).strip()
    if plain:
        return plain.group(1).strip()
    path_name = unquote(Path(urlsplit(url).path).name)
    return path_name or fallback


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(value).name).strip(" .")
    return cleaned or "download.bin"


def _unique_path(path: Path) -> Path:
    if not path.exists() and not path.with_name(path.name + ".part").exists():
        return path
    for number in range(2, 100_000):
        candidate = path.with_name(f"{path.stem}_{number}{path.suffix}")
        if not candidate.exists() and not candidate.with_name(candidate.name + ".part").exists():
            return candidate
    raise OSError(f"could not allocate unique filename for {path.name}")
