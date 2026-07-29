"""BM25 기반 렉시컬 검색기.

한국어를 형태소 분석기 없이 다루기 위해 Elasticsearch `cjk` analyzer와
같은 방식으로 CJK 문자를 bigram으로 분해하고, ASCII 단어는 그대로
토큰으로 쓴다. 외부 패키지·임베딩 모델·FAISS 인덱스가 없어도 동작하는
검색 경로를 제공한다.

코퍼스는 storage/metadata.jsonl(빌드 산출물)을 우선 사용하고, 없으면
평면 apidata JSON에서 직접 추출한다.
"""
import json
import math
import re
from collections import Counter, defaultdict

from ..core import config

_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[가-힣ㄱ-ㆎ一-鿿]+")

# BM25 표준 파라미터
K1 = 1.2
B = 0.75

# 필드 반복 가중치 (BM25F 근사): 제목 > 키워드 > 분류·기관 > 설명
FIELD_WEIGHTS = (
    ("title", 3),
    ("keywords", 2),
    ("category", 1),
    ("provider", 1),
    ("description", 1),
)


def tokenize(text: str) -> list[str]:
    """소문자 ASCII 단어 토큰 + CJK 문자 bigram 토큰."""
    lowered = str(text or "").lower()
    tokens = _ASCII_WORD_RE.findall(lowered)
    for run in _CJK_RE.findall(lowered):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _doc_tokens(meta: dict) -> list[str]:
    tokens: list[str] = []
    for field, weight in FIELD_WEIGHTS:
        value = meta.get(field, "")
        if not value:
            continue
        field_tokens = tokenize(value)
        for _ in range(weight):
            tokens.extend(field_tokens)
    return tokens


def _load_metadata_corpus() -> list[dict]:
    if not config.STORAGE_META_PATH.exists():
        return []
    records = []
    with config.STORAGE_META_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def _load_apidata_corpus() -> list[dict]:
    """빌드 산출물이 없을 때 평면 apidata에서 직접 코퍼스를 만든다."""
    from ..indexing.index_builder import _extract_metadata

    if not config.APIDATA_DIR.exists():
        return []
    records = []
    for path in sorted(config.APIDATA_DIR.glob("**/*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = _extract_metadata(doc, path)
        if meta.get("api_id"):
            records.append(meta)
    return records


class LexicalRetriever:
    """metadata 코퍼스 위의 BM25. 인덱스는 메모리에 lazy 구축."""

    def __init__(self) -> None:
        self._loaded = False
        self._source = ""
        self._metadata: list[dict] = []
        self._doc_freqs: list[Counter] = []
        self._doc_lens: list[int] = []
        self._avg_len = 0.0
        self._df: dict[str, int] = defaultdict(int)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        metadata = _load_metadata_corpus()
        self._source = "storage_metadata" if metadata else ""
        if not metadata:
            metadata = _load_apidata_corpus()
            self._source = "apidata_scan" if metadata else ""
        self._metadata = metadata

        for meta in metadata:
            tokens = _doc_tokens(meta)
            freqs = Counter(tokens)
            self._doc_freqs.append(freqs)
            self._doc_lens.append(len(tokens))
            for token in freqs:
                self._df[token] += 1
        self._avg_len = (sum(self._doc_lens) / len(self._doc_lens)) if self._doc_lens else 0.0

    def reload(self) -> None:
        self.__init__()

    def corpus_size(self) -> int:
        self._ensure_loaded()
        return len(self._metadata)

    def corpus_source(self) -> str:
        self._ensure_loaded()
        return self._source

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        self._ensure_loaded()
        if not self._metadata:
            return []

        query_tokens = [t for t in set(tokenize(query)) if t in self._df]
        if not query_tokens:
            return []

        n_docs = len(self._metadata)
        scores = [0.0] * n_docs
        for token in query_tokens:
            df = self._df[token]
            idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            for idx, freqs in enumerate(self._doc_freqs):
                tf = freqs.get(token)
                if not tf:
                    continue
                norm = K1 * (1 - B + B * self._doc_lens[idx] / (self._avg_len or 1.0))
                scores[idx] += idf * tf * (K1 + 1) / (tf + norm)

        ranked = sorted(
            (idx for idx in range(n_docs) if scores[idx] > 0),
            key=lambda idx: scores[idx],
            reverse=True,
        )[: max(1, top_k)]

        results = []
        for idx in ranked:
            record = dict(self._metadata[idx])
            record["score"] = round(scores[idx], 4)
            results.append(record)
        return results
