from __future__ import annotations

from pathlib import Path

from domain.operations import OperationRegistry

from .dummy import DummyAdapter


class AdapterRegistry(OperationRegistry):
    def __init__(self, specs, adapter: DummyAdapter | None = None):
        super().__init__(specs)
        self.adapter = adapter or DummyAdapter()

    @classmethod
    def from_json(cls, path: Path) -> "AdapterRegistry":
        loaded = OperationRegistry.from_json(path)
        return cls(list(loaded._specs.values()))

    def adapter_for(self, adapter_name: str) -> DummyAdapter:
        if adapter_name != "dummy":
            raise ValueError("only the reviewed Dummy Adapter is enabled")
        return self.adapter
