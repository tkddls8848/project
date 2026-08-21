from __future__ import annotations

from infra.database import Database


class ReceiptReconciler:
    """Reconciles local, allowlisted Adapter receipts without issuing HTTP requests."""

    def __init__(self, database: Database):
        self.database = database

    def reconcile(self, run_id: str, principal_id: str):
        return self.database.reconcile_from_receipt(run_id, principal_id)
