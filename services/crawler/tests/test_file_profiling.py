import asyncio
from collections import deque

from profiling.fetcher import FetchPolicy, PoliteFileFetcher
from profiling.schema_infer import infer_schema


class FakeContent:
    def __init__(self, body):
        self.body = body

    async def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    async def iter_chunked(self, size):
        for offset in range(0, len(self.body), size):
            yield self.body[offset : offset + size]


class FakeResponse:
    def __init__(self, url, body=b"", status=200, headers=None):
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.content = FakeContent(body)

    async def text(self, errors="strict"):
        return self.content.body.decode("utf-8", errors=errors)

    def release(self):
        pass

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.requests = []

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        response = self.responses.popleft()
        response.url = url
        return response


def test_cp949_csv_schema_has_types_null_ratio_and_samples():
    body = "코드,지역명,인구,기준일\n001,서울,100,2026-01-01\n002,,120,2026-01-02\n".encode("cp949")
    result = infer_schema(body, filename="지역.csv")

    assert result.status == "ok"
    assert result.encoding == "euc-kr"
    columns = {column.name: column for column in result.columns}
    assert columns["코드"].inferred_type == "string"
    assert columns["지역명"].null_ratio == 0.5
    assert columns["인구"].inferred_type == "integer"
    assert columns["기준일"].inferred_type == "date"
    assert columns["지역명"].sample_values == ["서울"]


def test_truncated_csv_drops_incomplete_last_row():
    result = infer_schema(b"name,count\na,1\nb,", filename="x.csv", truncated=True)
    assert result.sampled_rows == 1
    assert result.columns[1].null_ratio == 0.0


def test_zip_and_xlsx_are_explicitly_unsupported():
    assert infer_schema(b"PK\x03\x04archive", filename="data.zip").status == "unsupported"
    assert infer_schema(b"PK\x03\x04archive", filename="data.xlsx").format == "xlsx"


def test_fetcher_checks_robots_and_bounds_sample_without_network():
    csv_body = b"a,b\n1,2\n3,4\n"
    session = FakeSession(
        [
            FakeResponse("", b"User-agent: *\nAllow: /\n"),
            FakeResponse(
                "",
                csv_body,
                headers={"Content-Type": "text/csv", "Content-Length": str(len(csv_body))},
            ),
        ]
    )
    fetcher = PoliteFileFetcher(FetchPolicy(sample_bytes=8, request_delay=0))
    results = asyncio.run(
        fetcher.fetch_download_urls({"fixture.csv": "https://example.test/data.csv"}, session=session)
    )

    result = results["fixture.csv"]
    assert result.status == "ok"
    assert result.sample == csv_body[:8]
    assert result.truncated is True
    assert result.robots_status == "verified"
    assert session.requests[0][1] == "https://example.test/robots.txt"
    assert session.requests[1][2]["headers"] == {"Range": "bytes=0-7"}


def test_fetcher_obeys_robots_denial_without_requesting_file():
    session = FakeSession([FakeResponse("", b"User-agent: *\nDisallow: /private\n")])
    fetcher = PoliteFileFetcher(FetchPolicy(request_delay=0))
    result = asyncio.run(
        fetcher.fetch_download_urls(
            {"secret.csv": "https://example.test/private/data.csv"}, session=session
        )
    )["secret.csv"]

    assert result.status == "robots_denied"
    assert len(session.requests) == 1


def test_full_download_is_never_implicit():
    fetcher = PoliteFileFetcher(FetchPolicy(full_download=True, request_delay=0))
    try:
        asyncio.run(fetcher.fetch_download_urls({}))
    except ValueError as exc:
        assert "output_dir" in str(exc)
    else:
        raise AssertionError("full download must require an explicit destination")


def test_explicit_full_download_streams_to_disk(tmp_path):
    body = b"name,count\na,1\n"
    session = FakeSession(
        [
            FakeResponse("", b"User-agent: *\nAllow: /\n"),
            FakeResponse(
                "",
                body,
                headers={
                    "Content-Type": "text/csv",
                    "Content-Disposition": 'attachment; filename="fixture.csv"',
                    "Content-Length": str(len(body)),
                },
            ),
        ]
    )
    fetcher = PoliteFileFetcher(
        FetchPolicy(full_download=True, sample_bytes=8, request_delay=0)
    )
    result = asyncio.run(
        fetcher.fetch_download_urls(
            {"fixture": "https://example.test/file"}, output_dir=tmp_path, session=session
        )
    )["fixture"]

    assert result.status == "ok"
    assert result.sample == body[:8]
    assert (tmp_path / "fixture.csv").read_bytes() == body
    assert session.requests[1][2]["headers"] == {}
