from dataclasses import dataclass
from fastapi import Header, HTTPException
@dataclass
class Principal:
    user_id: str
    tenant_id: str
USERS = {"tok_acme": Principal("u_acme", "tenant_acme"), "tok_globex": Principal("u_globex", "tenant_globex")}
def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    principal = USERS.get(authorization.removeprefix("Bearer ").strip())
    if not principal: raise HTTPException(401, "invalid token")
    return principal
