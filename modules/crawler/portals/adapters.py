"""The five protocol adapters used for all institutional portal hosts."""

import json
from typing import Any, List
from urllib.parse import urljoin
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from .models import HarvestedItem


class CKANAdapter:
    name = "ckan"
    paths = ("/api/3/action/package_list",)

    @staticmethod
    def matches(payload: Any) -> bool:
        return isinstance(payload, dict) and payload.get("success") is True and isinstance(payload.get("result"), list)

    @staticmethod
    def items(payload: dict, base_url: str, source_url: str) -> List[HarvestedItem]:
        return [HarvestedItem(str(name), urljoin(base_url + "/", f"dataset/{name}")) for name in payload["result"]]


class OpenAPIAdapter:
    name = "openapi"
    paths = ("/v2/api-docs", "/swagger.json", "/openapi.json", "/v3/api-docs")

    @staticmethod
    def matches(payload: Any) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get("paths"), dict) and bool(payload.get("swagger") or payload.get("openapi"))

    @staticmethod
    def items(payload: dict, base_url: str, source_url: str) -> List[HarvestedItem]:
        info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
        return [HarvestedItem(str(info.get("title") or base_url), source_url, {"spec": payload})]


class SitemapAdapter:
    name = "sitemap"
    paths = ("/sitemap.xml",)

    @staticmethod
    def items(xml: str, base_url: str, source_url: str) -> List[HarvestedItem]:
        root = ElementTree.fromstring(xml)
        locations = [element.text.strip() for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "loc" and element.text]
        return [HarvestedItem(location.rsplit("/", 1)[-1] or location, location, {"source": "sitemap"}) for location in locations]


class JSONLDAdapter:
    name = "jsonld"
    paths = ("/",)

    @classmethod
    def datasets(cls, html: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        output: List[dict] = []
        for script in soup.find_all("script", attrs={"type": lambda value: value and value.lower() == "application/ld+json"}):
            try:
                value = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            cls._collect(value, output)
        return output

    @classmethod
    def _collect(cls, value: Any, output: List[dict]) -> None:
        if isinstance(value, dict):
            kinds = value.get("@type", [])
            kinds = kinds if isinstance(kinds, list) else [kinds]
            if any(str(kind).lower().rstrip("/").endswith("dataset") for kind in kinds):
                output.append(value)
            for child in value.values():
                cls._collect(child, output)
        elif isinstance(value, list):
            for child in value:
                cls._collect(child, output)

    @staticmethod
    def items(datasets: List[dict], base_url: str, source_url: str) -> List[HarvestedItem]:
        return [
            HarvestedItem(
                str(dataset.get("name") or dataset.get("headline") or "Dataset"),
                str(dataset.get("url") or source_url),
                {"jsonld": dataset},
            )
            for dataset in datasets
        ]


class GenericAdapter:
    name = "generic"
    paths = ("/",)

    @staticmethod
    def items(html: str, base_url: str, source_url: str) -> List[HarvestedItem]:
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else source_url
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for row in table.find_all("tr"):
                cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return [HarvestedItem(title, source_url, {"tables": tables}, verified=False)]


ADAPTERS = (CKANAdapter, OpenAPIAdapter, SitemapAdapter, JSONLDAdapter, GenericAdapter)
