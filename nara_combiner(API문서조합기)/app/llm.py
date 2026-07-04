"""Ollama 호출 — 스트리밍 / 논스트리밍."""
import json
import logging
from typing import AsyncIterator

import httpx

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


async def generate(prompt: str, model: str = OLLAMA_MODEL) -> str:
    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except httpx.ConnectError:
            raise RuntimeError(f"Ollama 연결 실패 ({OLLAMA_BASE_URL}). Ollama가 실행 중인지 확인하세요.")
        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama 응답 시간 초과 ({OLLAMA_BASE_URL}).")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise RuntimeError(f"모델 없음: {model}. `ollama pull {model}` 을 먼저 실행하세요.")
            raise RuntimeError(f"Ollama 오류 응답: HTTP {e.response.status_code}")
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama 호출 실패: {type(e).__name__}")


async def generate_stream(prompt: str, model: str = OLLAMA_MODEL) -> AsyncIterator[str]:
    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": True},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                    except Exception:
                        pass
        except httpx.ConnectError:
            raise RuntimeError(f"Ollama 연결 실패 ({OLLAMA_BASE_URL})")
        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama 응답 시간 초과 ({OLLAMA_BASE_URL})")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama 오류 응답: HTTP {e.response.status_code}")
