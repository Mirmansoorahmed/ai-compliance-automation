"""Phase 0 — profile/flag loader tests (R4.2)."""

import pytest

from aca.config import ConfigError, load_config


def test_default_profile_is_oss():
    cfg = load_config()
    assert cfg.profile == "oss"
    assert cfg.has_adapter("local_embeddings")
    assert cfg.judge_enabled is False
    assert cfg.fixture_mode is True


def test_oss_profile_has_no_cloud_adapter():
    cfg = load_config("oss")
    assert "prompt_shields" not in cfg.adapters
    assert cfg.identity_provider == "fixture"


def test_hybrid_profile_loads_but_judge_off_by_default():
    cfg = load_config("hybrid")
    assert cfg.profile == "hybrid"
    assert "prompt_shields" in cfg.adapters
    assert cfg.judge_enabled is False  # judge is off by default even on hybrid


def test_unknown_profile_rejected():
    with pytest.raises(ConfigError):
        load_config("does-not-exist")


def test_embeddings_defaults_present():
    cfg = load_config()
    assert cfg.embeddings.allow_hashed_fallback is True
    assert cfg.embeddings.dim > 0
    assert "MiniLM" in cfg.embeddings.model
