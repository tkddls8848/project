"""외부 URL이 내부망을 가리킬 때 요청이 나가지 않는지 확인한다.

공공데이터 문서의 download_urls와 외부 기관 URL은 우리가 정한 값이 아니다.
--deep·--harvest·LINK 수집이 그 값을 그대로 요청하므로, 로컬 서비스나 내부망을
가리키는 주소는 요청 전에 걸러야 한다.
"""

from __future__ import annotations

import asyncio
import socket

import pytest

from link_docs.runner import build_tasks
from portals.inventory import build_host_inventory
from portals.transport import SafeHttpTransport
from utils.url_guard import (
    literal_rejection_reason,
    rejection_reason,
    rejection_reason_async,
)

BLOCKED_URLS = [
    "http://127.0.0.1:8000/admin",
    "http://localhost:8000/admin",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.1.2.3/internal",
    "http://192.168.0.10/",
    "http://172.16.5.4/",
    "http://[::1]:8000/",
    "http://0.0.0.0/",
]


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_internal_targets_are_rejected(url):
    assert rejection_reason(url) is not None


@pytest.mark.parametrize(
    ("url", "fragment"),
    [
        ("http://127.0.0.1/", "loopback"),
        ("http://169.254.169.254/", "link-local"),
        ("http://10.1.2.3/", "사설"),
    ],
)
def test_rejection_reason_names_the_actual_cause(url, fragment):
    """loopback·link-local은 IPv4에서 사설 대역에도 걸린다. 좁은 이유가 나와야 한다."""
    assert fragment in rejection_reason(url)


@pytest.mark.parametrize(
    "url",
    ["ftp://example.org/x", "file:///etc/passwd", "javascript:alert(1)", "", "http:///path"],
)
def test_non_http_targets_are_rejected(url):
    assert rejection_reason(url) is not None


def test_public_hosts_pass(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    assert rejection_reason("https://www.data.go.kr/") is None


def test_a_name_resolving_to_both_public_and_private_is_rejected(monkeypatch):
    """한 이름이 공개·비공개 주소를 함께 돌려줄 수 있다. 하나라도 걸리면 막는다."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_a, **_k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
        ],
    )
    assert "loopback" in rejection_reason("http://mixed.example/")


def test_unresolvable_names_are_rejected(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    assert "이름을 풀 수 없습니다" in rejection_reason("http://nope.invalid/")


# ── 이름을 풀지 않는 검사 ───────────────────────────────────────────────


def test_literal_check_catches_ip_literals():
    assert literal_rejection_reason("http://127.0.0.1:8000/admin") is not None
    assert literal_rejection_reason("http://169.254.169.254/") is not None


def test_literal_check_lets_names_through_without_dns(monkeypatch):
    """작업 목록을 만드는 순수 함수가 네트워크에 의존하면 안 된다."""
    def _fail(*_args, **_kwargs):
        raise AssertionError("이름을 풀지 않아야 한다")

    monkeypatch.setattr(socket, "getaddrinfo", _fail)
    assert literal_rejection_reason("http://www.data.go.kr/") is None


# ── 실제 수집 경로 ──────────────────────────────────────────────────────


def test_internal_urls_do_not_become_harvest_targets():
    records = [
        {
            "api_id": "15000001",
            "external_endpoint_urls": [
                "http://127.0.0.1:8000/admin",
                "http://10.0.0.5/internal",
                "https://api.example.org/v1/list",
            ],
        }
    ]

    hosts = build_host_inventory(records)

    assert [host.host for host in hosts] == ["api.example.org"]


def test_internal_urls_do_not_become_link_doc_tasks():
    records = [
        {"api_id": "1", "info": {"URL": "http://127.0.0.1:9000/docs"}},
        {"api_id": "2", "info": {"URL": "http://192.168.1.5/docs"}},
        {"api_id": "3", "info": {"URL": "https://agency.example.org/docs"}},
    ]

    tasks = build_tasks(records)

    assert [task.url for task in tasks] == ["https://agency.example.org/docs"]


def test_transport_refuses_before_fetching_robots():
    """robots.txt를 받는 것부터가 요청이다. 그 전에 막혀야 한다.

    robots는 SSRF 방어가 아니다. robots가 없는 호스트는 오히려 허용되므로,
    로컬 서비스는 robots 검사만으로는 통과한다.
    """
    async def scenario():
        transport = SafeHttpTransport()

        def _fail(*_args, **_kwargs):
            raise AssertionError("차단 대상에 요청을 보내면 안 된다")

        transport._raw_get = _fail
        return await transport.robots_decision("http://127.0.0.1:8000/admin")

    decision = asyncio.run(scenario())

    assert decision.allowed is False
    assert decision.reason.startswith("blocked_target:")


def test_transport_get_raises_for_internal_targets():
    async def scenario():
        transport = SafeHttpTransport()
        transport._raw_get = lambda *_a, **_k: pytest.fail("요청이 나가면 안 된다")
        with pytest.raises(PermissionError):
            await transport.get("http://169.254.169.254/latest/meta-data/")

    asyncio.run(scenario())


def test_redirect_hops_are_rechecked():
    """공개 호스트가 리다이렉트로 내부망을 가리켜도 따라가면 안 된다."""
    assert asyncio.run(rejection_reason_async("http://127.0.0.1/")) is not None
