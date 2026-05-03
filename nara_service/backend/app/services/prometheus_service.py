import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.models import PrometheusCreateRequest, PrometheusResponse, PrometheusUpdateRequest

class PrometheusService:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.prometheus_file = self.storage_path / "prometheus" / "prometheus.json"
        self._ensure_storage()

    def _ensure_storage(self):
        # Ensure prometheus directory exists
        self.prometheus_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.prometheus_file.exists():
            with open(self.prometheus_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _read_db(self) -> Dict[str, Any]:
        try:
            with open(self.prometheus_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_db(self, data: Dict[str, Any]):
        with open(self.prometheus_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_prometheus(self, request: PrometheusCreateRequest) -> PrometheusResponse:
        db = self._read_db()
        prometheus_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        prometheus = {
            "id": prometheus_id,
            "user_id": request.user_id,
            "name": request.name,
            "nodes": request.nodes,
            "edges": request.edges,
            "created_at": now,
            "updated_at": now
        }

        db[prometheus_id] = prometheus
        self._write_db(db)
        return PrometheusResponse(**prometheus)

    def get_prometheus(self, prometheus_id: str) -> Optional[PrometheusResponse]:
        db = self._read_db()
        prometheus = db.get(prometheus_id)
        if prometheus:
            return PrometheusResponse(**prometheus)
        return None

    def list_prometheuss(self, user_id: str) -> List[PrometheusResponse]:
        db = self._read_db()
        prometheuss = [
            PrometheusResponse(**w) for w in db.values()
            if w.get("user_id") == user_id
        ]
        # Sort by updated_at desc
        prometheuss.sort(key=lambda x: x.updated_at, reverse=True)
        return prometheuss

    def update_prometheus(self, prometheus_id: str, request: PrometheusUpdateRequest, user_id: str) -> Optional[PrometheusResponse]:
        db = self._read_db()
        prometheus = db.get(prometheus_id)

        if not prometheus:
            return None
        
        if prometheus.get("user_id") != user_id:
            raise PermissionError("User not authorized to update this prometheus")

        updated = False
        if request.name is not None:
            prometheus["name"] = request.name
            updated = True
        if request.nodes is not None:
            prometheus["nodes"] = request.nodes
            updated = True
        if request.edges is not None:
            prometheus["edges"] = request.edges
            updated = True

        if updated:
            prometheus["updated_at"] = datetime.utcnow().isoformat()
            db[prometheus_id] = prometheus
            self._write_db(db)

        return PrometheusResponse(**prometheus)

    def delete_prometheus(self, prometheus_id: str, user_id: str) -> bool:
        db = self._read_db()
        prometheus = db.get(prometheus_id)

        if not prometheus:
            return False
        
        if prometheus.get("user_id") != user_id:
            raise PermissionError("User not authorized to delete this prometheus")

        del db[prometheus_id]
        self._write_db(db)
        return True
