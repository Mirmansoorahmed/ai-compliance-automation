"""Profile and feature-flag loader (R4.2).

The ``oss`` profile is the default and is the profile CI guarantees. Loading is
done with the standard-library ``tomllib`` so the oss profile needs no
third-party dependency.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

VALID_PROFILES = ("oss", "hybrid")
DEFAULT_PROFILE = "oss"

# Adapters known to the system. Selecting an unknown adapter is an error.
KNOWN_ADAPTERS = ("local_embeddings", "prompt_shields", "lakera", "aws_placeholder")

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class ConfigError(ValueError):
    """Raised when a profile or flag is invalid."""


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    allow_hashed_fallback: bool = True
    dim: int = 256


@dataclass(frozen=True)
class Config:
    profile: str
    adapters: tuple[str, ...]
    judge_enabled: bool
    identity_provider: str
    evidence_exporter: str
    fixture_mode: bool
    embeddings: EmbeddingConfig = field(default_factory=EmbeddingConfig)

    def has_adapter(self, name: str) -> bool:
        return name in self.adapters


def _config_path(profile: str) -> Path:
    return _CONFIG_DIR / f"{profile}.toml"


def load_config(profile: str | None = None, *, config_dir: Path | None = None) -> Config:
    """Load a profile config.

    Defaults to ``oss``. Rejects unknown profiles and unknown adapter names so a
    typo cannot silently enable (or disable) a control.
    """

    profile = profile or DEFAULT_PROFILE
    if profile not in VALID_PROFILES:
        raise ConfigError(
            f"unknown profile {profile!r}; valid profiles: {VALID_PROFILES}"
        )

    base = config_dir or _CONFIG_DIR
    path = base / f"{profile}.toml"
    if not path.exists():
        raise ConfigError(f"missing profile config: {path}")

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    guard = raw.get("guard", {})
    adapters = tuple(guard.get("adapters", ["local_embeddings"]))
    if "local_embeddings" not in adapters:
        raise ConfigError("local_embeddings is required in every profile")
    for name in adapters:
        if name not in KNOWN_ADAPTERS:
            raise ConfigError(
                f"unknown adapter {name!r}; known adapters: {KNOWN_ADAPTERS}"
            )

    emb_raw = guard.get("embeddings", {})
    embeddings = EmbeddingConfig(
        model=emb_raw.get("model", EmbeddingConfig.model),
        allow_hashed_fallback=bool(emb_raw.get("allow_hashed_fallback", True)),
        dim=int(emb_raw.get("dim", 256)),
    )

    return Config(
        profile=raw.get("profile", profile),
        adapters=adapters,
        judge_enabled=bool(guard.get("judge_enabled", False)),
        identity_provider=raw.get("identity", {}).get("provider", "fixture"),
        evidence_exporter=raw.get("evidence", {}).get("exporter", "file"),
        fixture_mode=bool(raw.get("api", {}).get("fixture_mode", True)),
        embeddings=embeddings,
    )
