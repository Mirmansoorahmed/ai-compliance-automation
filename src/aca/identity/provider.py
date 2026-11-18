"""Identity providers: fixture/Keycloak (default) and optional Entra ID (R15.1).

The oss profile requires NO cloud IdP. A fixture token (a plain dict of claims)
is the default and is all the tests use. Entra ID is an *optional* adapter that
normalises group claims the same way; when its env config is absent it reports
unavailable and the caller falls back to the fixture provider.

An identity provider turns a token/claims into a normalised ``Subject``:
``{subject_id, groups[], site}``. Pseudonymisation of ``subject_id`` happens
later, in the evidence layer — identity providers deal in clear claims only in
memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from aca.guard.adapters.azure_env import EntraEnv, read_entra_env


@dataclass(frozen=True)
class Subject:
    subject_id: str
    groups: list[str] = field(default_factory=list)
    site: str | None = None


class IdentityProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def resolve(self, token: dict) -> Subject:
        ...


class FixtureIdentityProvider:
    """Default provider: reads claims straight from a fixture/Keycloak token."""

    name = "fixture"

    def available(self) -> bool:
        return True

    def resolve(self, token: dict) -> Subject:
        return Subject(
            subject_id=str(token.get("sub") or token.get("subject_id") or "anonymous"),
            groups=list(token.get("groups", [])),
            site=token.get("site"),
        )


class EntraIdentityProvider:
    """Optional Entra ID provider: normalises group claims from an Entra token.

    Entra places group object-ids in the ``groups`` claim (or ``roles`` /
    ``wids`` depending on config). This maps them to normalised group names via
    a supplied mapping, falling back to the raw id when unmapped. It never calls
    the network to resolve groups in v1 — it reads claims already in the token —
    so it is testable with a mocked token and needs only tenant/client metadata.
    """

    name = "entra"

    def __init__(self, *, env: EntraEnv | None = None, group_map: dict | None = None) -> None:
        self._env = env or read_entra_env()
        self._group_map = group_map or {}

    def available(self) -> bool:
        return self._env.available

    def resolve(self, token: dict) -> Subject:
        raw_groups = list(token.get("groups", []))
        groups = [self._group_map.get(g, g) for g in raw_groups]
        return Subject(
            subject_id=str(token.get("oid") or token.get("sub") or "anonymous"),
            groups=groups,
            site=token.get("site") or token.get("usageLocation"),
        )


def build_identity_provider(profile_provider: str, *, group_map: dict | None = None) -> IdentityProvider:
    """Return the configured provider, falling back to fixture when Entra is off.

    ``profile_provider`` is the ``identity.provider`` from the profile config
    ("fixture" | "entra"). Entra degrades cleanly to fixture when its env config
    is missing, so the lab stays reproducible without a cloud login (R15.1).
    """
    if profile_provider == "entra":
        entra = EntraIdentityProvider(group_map=group_map)
        if entra.available():
            return entra
    return FixtureIdentityProvider()
