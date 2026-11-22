"""Phase 1 — deterministic secret scanner."""

from aca.check.secrets import has_secret, scan_secrets


def test_detects_assignment_secret():
    assert has_secret('api_key = "ABCD1234efgh5678ijkl"')
    assert has_secret("password: s3cretValue123456")


def test_detects_known_formats():
    assert "aws_access_key_id" in scan_secrets("AKIAIOSFODNN7EXAMPLE")
    assert "github_pat" in scan_secrets("ghp_" + "a" * 36)
    assert "openai_key" in scan_secrets("sk-" + "a" * 32)
    assert "private_key" in scan_secrets("-----BEGIN RSA PRIVATE KEY-----")
    assert "azure_account_key" in scan_secrets("AccountKey=abcdefghijklmnopqrstuvwxyz0123")


def test_clean_text_has_no_secret():
    assert not has_secret("compute a fraud risk score on transactions")
    assert not has_secret("def add(a, b):\n    return a + b")
