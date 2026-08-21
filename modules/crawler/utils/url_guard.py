"""외부 데이터에서 나온 URL을 요청하기 전에 거른다.

크롤러는 공공데이터 문서에 적힌 ``download_urls``와 외부 기관 URL을 그대로 받아
요청한다(``--deep``, ``--harvest``, LINK 문서 수집). 그 값은 우리가 정한 것이
아니므로 실행 머신의 로컬 서비스나 내부망을 가리키는 주소가 섞여 들어올 수 있다.

공개 기관 도메인 목록으로 막지는 않는다. ``--harvest``는 사전에 알 수 없는 기관
사이트를 도는 것이 목적이라 화이트리스트를 두면 기능 자체가 없어진다. 대신
이름을 풀어 loopback·사설·link-local 같은 비공개 주소로 가는 요청만 막는다.

검사는 두 갈래다. 이름을 푸는 검사(:func:`rejection_reason`)는 실제로 요청을
보내는 자리에서 쓰고, 이름을 풀지 않는 검사(:func:`literal_rejection_reason`)는
작업 목록을 만드는 순수 함수에서 쓴다. 목록을 만들 때마다 DNS를 두드리면 순수
함수가 네트워크에 의존하게 되고, 호스트 수만큼 느려진다.

한계: 이름을 푼 시점과 실제 연결 사이가 벌어져 있어(TOCTOU) 그 사이에 응답이
바뀌는 DNS rebinding까지는 막지 못한다. 그것까지 막으려면 확인한 IP로 직접
연결해야 하는데, 지금 쓰는 aiohttp 경로에 넣기에는 변경이 크다.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})
DEFAULT_PORTS = {"http": 80, "https": 443}


def _address_reason(address: str) -> Optional[str]:
    """공개 대상이 아닌 IP면 이유를, 괜찮으면 None을 준다."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return f"IP로 읽을 수 없는 주소입니다: {address}"

    # loopback과 link-local은 IPv4에서 is_private에도 걸린다. 더 좁은 것부터
    # 확인해야 이유 문구가 실제 원인을 가리킨다.
    if ip.is_loopback:
        return f"loopback 주소입니다: {ip}"
    if ip.is_link_local:
        return f"link-local 주소입니다: {ip}"
    if ip.is_private:
        return f"사설 주소입니다: {ip}"
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return f"공개 대상이 아닌 주소입니다: {ip}"
    return None


def split_target(url: str) -> Tuple[str, int, Optional[str]]:
    """URL에서 (host, port)를 뽑는다. 쓸 수 없으면 이유를 함께 준다."""
    parsed = urlsplit(str(url or "").strip())
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        return "", 0, f"http/https가 아닙니다: {scheme or '(스킴 없음)'}"
    try:
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port or DEFAULT_PORTS[scheme]
    except ValueError as exc:
        return "", 0, f"주소를 읽을 수 없습니다: {exc}"
    if not host:
        return "", 0, "호스트가 없습니다."
    return host, port, None


def literal_rejection_reason(url: str) -> Optional[str]:
    """이름을 풀지 않고 판단할 수 있는 것만 본다.

    호스트가 이미 IP로 적혀 있으면 그 자리에서 거른다. 이름으로 적혀 있으면
    여기서는 통과시키고, 실제 요청 직전에 :func:`rejection_reason`이 막는다.
    """
    host, _port, reason = split_target(url)
    if reason is not None:
        return reason
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None
    return _address_reason(host.strip("[]"))


def _resolved_reason(host: str, infos: Sequence) -> Optional[str]:
    addresses: List[str] = [info[4][0] for info in infos]
    if not addresses:
        return f"이름을 풀 수 없습니다: {host}"
    # 한 이름이 공개 주소와 비공개 주소를 함께 돌려줄 수 있다. 하나라도 걸리면 막는다.
    for address in addresses:
        blocked = _address_reason(address)
        if blocked is not None:
            return f"{host} -> {blocked}"
    return None


def rejection_reason(url: str) -> Optional[str]:
    """요청해서는 안 되는 URL이면 이유를, 괜찮으면 None을 준다."""
    host, port, reason = split_target(url)
    if reason is not None:
        return reason
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return f"이름을 풀 수 없습니다: {host} ({type(exc).__name__})"
    return _resolved_reason(host, infos)


async def rejection_reason_async(url: str) -> Optional[str]:
    """같은 검사를 이벤트 루프를 막지 않고 한다."""
    host, port, reason = split_target(url)
    if reason is not None:
        return reason
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except OSError as exc:
        return f"이름을 풀 수 없습니다: {host} ({type(exc).__name__})"
    return _resolved_reason(host, infos)


__all__ = [
    "literal_rejection_reason",
    "rejection_reason",
    "rejection_reason_async",
    "split_target",
]
