"""Semantic Guard service — runs configured adapters and merges labels.

The service selects adapters per profile (R4.2), runs each ``detect(event)``,
and returns the merged labels. ``local_embeddings`` is always present. Optional
adapters that are absent or raise are skipped cleanly (R4.3, R4.4) — a missing
optional adapter must never fail the oss profile or the request.

The service emits labels only; OPA decides.
"""

from __future__ import annotations

import logging

from aca.config import Config, load_config
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.event import Event

log = logging.getLogger("aca.guard")


def build_adapters(config: Config):
    """Instantiate adapters named in the profile. Required first, then optional.

    Optional adapters are imported lazily; if an import or construction fails
    (e.g. missing credentials or an uninstalled vendor SDK), the adapter is
    skipped with a log line instead of failing the request.
    """
    adapters = []
    embedder = build_embedder(
        config.embeddings.model,
        allow_hashed_fallback=config.embeddings.allow_hashed_fallback,
        dim=config.embeddings.dim,
    )
    # Required.
    adapters.append(LocalEmbeddingsAdapter(embedder=embedder, dim=config.embeddings.dim))

    for name in config.adapters:
        if name == "local_embeddings":
            continue
        try:
            adapters.append(_build_optional(name, config))
        except Exception as exc:  # degrade cleanly (R4.4)
            log.warning("optional adapter %r unavailable, skipping: %s", name, exc)
    return adapters


def _build_optional(name: str, config: Config):
    # Optional adapters land in Phase 10. Until then, selecting one on a profile
    # raises here and is skipped cleanly by build_adapters.
    raise NotImplementedError(f"optional adapter {name!r} not implemented until Phase 10")


class SemanticGuard:
    def __init__(self, config: Config | None = None, *, adapters=None) -> None:
        self.config = config or load_config()
        self._adapters = adapters if adapters is not None else build_adapters(self.config)

    @property
    def adapter_names(self) -> list[str]:
        return [a.name for a in self._adapters]

    def label(self, event: Event) -> list[dict]:
        """Run all adapters and return merged labels (labels only)."""
        labels, _healthy = self.label_with_health(event)
        return labels

    def label_with_health(self, event: Event) -> tuple[list[dict], bool]:
        """Return (labels, healthy).

        ``healthy`` is False when *every* adapter raised, i.e. the Guard could
        not classify the event at all. The pipeline needs this to tell "ran
        clean, nothing concerning" (healthy, no labels) apart from "the Guard is
        down" (unhealthy) so it can apply the fail-safe tier and never a silent
        allow.
        """
        labels: list[dict] = []
        failures = 0
        for adapter in self._adapters:
            try:
                labels.extend(adapter.detect(event))
            except Exception as exc:  # one adapter failing must not break others
                failures += 1
                log.warning("adapter %r raised, skipping: %s", adapter.name, exc)
        healthy = failures < len(self._adapters) if self._adapters else False
        return labels, healthy
