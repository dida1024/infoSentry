"""Token service port."""

from typing import Protocol


class TokenService(Protocol):
    def create_access_token(self, subject: str, extra_claims: dict | None = None) -> str: ...

    def create_magic_link_token(self, email: str) -> str: ...
