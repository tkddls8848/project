from typing import Any

from ..core import config


class ChromaRetriever:
    def __init__(self) -> None:
        self._collection = None
        self._last_error = ""
        self._disabled = False

    def collection_count(self) -> int | None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
            collection = client.get_collection(config.COLLECTION_NAME)
            return collection.count()
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def last_error(self) -> str:
        return self._last_error

    def _load_collection(self):
        if self._collection is not None:
            return self._collection

        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        embedding_function = SentenceTransformerEmbeddingFunction(
            model_name=config.DEFAULT_MODEL,
            local_files_only=config.MODEL_LOCAL_FILES_ONLY,
        )
        self._collection = client.get_collection(
            name=config.COLLECTION_NAME,
            embedding_function=embedding_function,
        )
        return self._collection

    def query(self, query: str, n_results: int) -> list[dict[str, Any]]:
        if self._disabled:
            return []
        try:
            collection = self._load_collection()
            count = collection.count()
            if count <= 0:
                return []
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            self._last_error = str(exc)
            self._disabled = True
            return []

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        candidates = []
        for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
            distance_value = float(distance) if distance is not None else 999.0
            candidates.append(
                {
                    "service_id": metadata.get("service_id"),
                    "chunk_id": chunk_id,
                    "chunk_type": metadata.get("chunk_type"),
                    "distance": distance_value,
                    "vector_score": 1.0 / (1.0 + max(distance_value, 0.0)),
                    "document": document,
                    "metadata": metadata,
                    "reasons": [f"{metadata.get('chunk_type', 'chunk')} vector match"],
                }
            )
        return candidates
