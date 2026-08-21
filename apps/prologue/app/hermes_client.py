"""Authenticated client for the Hermes Gateway Runs API."""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from .config import Settings


TERMINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled"}
RunEventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class HermesGatewayError(RuntimeError):
    """The Gateway could not accept, execute, or return a run."""


@dataclass(frozen=True)
class HermesRunResult:
    run_id: str
    status: str
    output: str = ""
    session_id: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[str] = field(default_factory=list)


class HermesGatewayClient:
    """Small async client that owns create/events/status/stop for one Gateway."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._owns_client = client is None
        self._headers = {"Authorization": f"Bearer {settings.hermes_api_key}"}
        self._client = client or httpx.AsyncClient(
            base_url=settings.hermes_api_url,
            timeout=httpx.Timeout(30.0, read=None),
        )

    async def __aenter__(self) -> "HermesGatewayClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._client.get("/health/detailed", headers=self._headers)
        except httpx.HTTPError as exc:
            raise HermesGatewayError(f"Hermes Gateway에 연결할 수 없습니다: {exc}") from exc
        self._raise_for_status(response, "Hermes readiness 확인 실패")
        return response.json()

    async def create_run(
        self,
        input_text: str,
        instructions: str,
        session_id: str,
    ) -> str:
        try:
            response = await self._client.post(
                "/v1/runs",
                headers=self._headers,
                json={
                    "input": input_text,
                    "instructions": instructions,
                    "session_id": session_id,
                    "model": self.settings.hermes_model,
                },
            )
        except httpx.HTTPError as exc:
            raise HermesGatewayError(f"Hermes Gateway에 연결할 수 없습니다: {exc}") from exc
        self._raise_for_status(response, "Hermes run 생성 실패")
        payload = response.json()
        run_id = str(payload.get("run_id", "")).strip()
        if response.status_code != 202 or not run_id:
            raise HermesGatewayError("Hermes Gateway가 유효한 run_id를 반환하지 않았습니다.")
        return run_id

    async def wait(
        self, run_id: str, on_event: RunEventCallback | None = None
    ) -> HermesRunResult:
        tool_calls: list[str] = []
        terminal: dict[str, Any] | None = None

        try:
            async with asyncio.timeout(self.settings.hermes_run_timeout):
                async with self._client.stream("GET", f"/v1/runs/{run_id}/events", headers=self._headers) as response:
                    self._raise_for_status(response, "Hermes run 이벤트 연결 실패")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            event = json.loads(line[5:].strip())
                        except (json.JSONDecodeError, TypeError):
                            continue
                        if not isinstance(event, dict):
                            continue
                        if event.get("event") == "tool.started":
                            tool = str(event.get("tool", ""))
                            tool_calls.append(tool)
                            if len(tool_calls) > self.settings.hermes_max_tool_calls:
                                await self.stop(run_id)
                                raise HermesGatewayError(
                                    f"Hermes 도구 호출이 상한 {self.settings.hermes_max_tool_calls}회를 초과했습니다."
                                )
                        if event.get("event") == "approval.request":
                            await self.deny_approval(run_id)
                            raise HermesGatewayError("허용 목록 밖 도구가 승인을 요청해 run을 거부했습니다.")
                        if on_event is not None:
                            callback_result = on_event(event)
                            if inspect.isawaitable(callback_result):
                                await callback_result
                        if event.get("event") in TERMINAL_EVENTS:
                            terminal = event
        except TimeoutError as exc:
            await self.stop(run_id)
            raise HermesGatewayError(
                f"Hermes run이 {self.settings.hermes_run_timeout:g}초 안에 끝나지 않았습니다."
            ) from exc
        except asyncio.CancelledError:
            await asyncio.shield(self.stop(run_id))
            raise

        except httpx.HTTPError as exc:
            raise HermesGatewayError(f"Hermes run 이벤트 연결이 끊겼습니다: {exc}") from exc

        status_payload = await self.get_run(run_id)
        status = str(status_payload.get("status", ""))
        output = str(status_payload.get("output") or (terminal or {}).get("output") or "")
        usage = status_payload.get("usage") or (terminal or {}).get("usage") or {}
        if status != "completed":
            error = status_payload.get("error") or (terminal or {}).get("error") or status or "unknown"
            raise HermesGatewayError(f"Hermes run {run_id} 종료 상태: {error}")
        return HermesRunResult(
            run_id=run_id,
            status=status,
            output=output,
            session_id=status_payload.get("session_id"),
            usage={str(k): int(v) for k, v in usage.items() if isinstance(v, (int, float))},
            tool_calls=tool_calls,
        )

    async def get_run(self, run_id: str) -> dict[str, Any]:
        try:
            response = await self._client.get(f"/v1/runs/{run_id}", headers=self._headers)
        except httpx.HTTPError as exc:
            raise HermesGatewayError(f"Hermes Gateway에 연결할 수 없습니다: {exc}") from exc
        self._raise_for_status(response, "Hermes run 조회 실패")
        payload = response.json()
        if not isinstance(payload, dict):
            raise HermesGatewayError("Hermes run 상태 응답이 객체가 아닙니다.")
        return payload

    async def stop(self, run_id: str) -> None:
        try:
            response = await self._client.post(f"/v1/runs/{run_id}/stop", headers=self._headers)
        except httpx.HTTPError as exc:
            raise HermesGatewayError(f"Hermes Gateway에 연결할 수 없습니다: {exc}") from exc
        if response.status_code not in {200, 404, 409}:
            self._raise_for_status(response, "Hermes run 중단 실패")

    async def deny_approval(self, run_id: str) -> None:
        try:
            response = await self._client.post(
                f"/v1/runs/{run_id}/approval", headers=self._headers,
                json={"choice": "deny"}
            )
        except httpx.HTTPError as exc:
            raise HermesGatewayError(f"Hermes Gateway에 연결할 수 없습니다: {exc}") from exc
        if response.status_code not in {200, 404, 409}:
            self._raise_for_status(response, "Hermes 승인 거부 실패")

    @staticmethod
    def _raise_for_status(response: httpx.Response, prefix: str) -> None:
        if response.is_success:
            return
        try:
            payload = response.json()
            detail = payload.get("error", payload) if isinstance(payload, dict) else payload
        except (ValueError, TypeError):
            detail = response.text
        raise HermesGatewayError(f"{prefix} (HTTP {response.status_code}): {detail}")


__all__ = ["HermesGatewayClient", "HermesGatewayError", "HermesRunResult"]
