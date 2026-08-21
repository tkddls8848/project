from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domain.approvals import hash_password, verify_password
from infra.database import Database


@dataclass(frozen=True)
class Principal:
    principal_id: str
    permissions: frozenset[str] = frozenset({"epilogue"})


class LocalSessionAuth:
    def __init__(self, database: Database, users: dict[str, str], session_ttl_seconds: int):
        self.database = database
        self.session_ttl_seconds = session_ttl_seconds
        self._password_hashes = {principal: hash_password(password) for principal, password in users.items()}

    def authenticate(self, principal_id: str, password: str) -> bool:
        encoded = self._password_hashes.get(principal_id)
        return bool(encoded and verify_password(password, encoded))

    def issue_session(self, principal_id: str, password: str) -> str:
        if not self.authenticate(principal_id, password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid local credentials")
        return self.database.create_session(principal_id, self.session_ttl_seconds)


_bearer = HTTPBearer(auto_error=False)


def authenticated_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    principal_id = request.app.state.database.resolve_session(credentials.credentials)
    if principal_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")
    return Principal(principal_id)
