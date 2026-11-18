"""Azure adapter configuration from environment variables only (Phase 10 rule 2).

No secret or endpoint is ever stored in the repo. Each adapter reads its config
from env vars at construction time. If a required var is missing, the adapter
reports itself unavailable (``available() is False``) and the Guard skips it —
the oss path is unaffected.

Env vars (all optional; absence = adapter off):
    Prompt Shields (Azure AI Content Safety):
        ACA_PROMPT_SHIELDS_ENDPOINT   e.g. https://<resource>.cognitiveservices.azure.com
        ACA_PROMPT_SHIELDS_KEY        subscription key
        ACA_PROMPT_SHIELDS_API_VERSION (optional, pinned default below)
    Azure OpenAI judge (stage 3):
        ACA_AZURE_OPENAI_ENDPOINT     e.g. https://<resource>.openai.azure.com
        ACA_AZURE_OPENAI_KEY          api key
        ACA_AZURE_OPENAI_DEPLOYMENT   deployment name (pinned model)
        ACA_AZURE_OPENAI_API_VERSION  (optional, pinned default below)
    Entra ID identity mapping:
        ACA_ENTRA_TENANT_ID, ACA_ENTRA_CLIENT_ID  (group-claim mapping metadata)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Pinned API versions so behaviour is reproducible; override via env if needed.
DEFAULT_PROMPT_SHIELDS_API_VERSION = "2024-09-01"
DEFAULT_AZURE_OPENAI_API_VERSION = "2024-10-21"


@dataclass(frozen=True)
class PromptShieldsEnv:
    endpoint: str | None
    key: str | None
    api_version: str

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.key)


@dataclass(frozen=True)
class AzureOpenAIEnv:
    endpoint: str | None
    key: str | None
    deployment: str | None
    api_version: str

    @property
    def available(self) -> bool:
        return bool(self.endpoint and self.key and self.deployment)


@dataclass(frozen=True)
class EntraEnv:
    tenant_id: str | None
    client_id: str | None

    @property
    def available(self) -> bool:
        return bool(self.tenant_id and self.client_id)


def _get(env: dict | None, name: str) -> str | None:
    source = env if env is not None else os.environ
    val = source.get(name)
    return val or None


def read_prompt_shields_env(env: dict | None = None) -> PromptShieldsEnv:
    return PromptShieldsEnv(
        endpoint=_get(env, "ACA_PROMPT_SHIELDS_ENDPOINT"),
        key=_get(env, "ACA_PROMPT_SHIELDS_KEY"),
        api_version=_get(env, "ACA_PROMPT_SHIELDS_API_VERSION") or DEFAULT_PROMPT_SHIELDS_API_VERSION,
    )


def read_azure_openai_env(env: dict | None = None) -> AzureOpenAIEnv:
    return AzureOpenAIEnv(
        endpoint=_get(env, "ACA_AZURE_OPENAI_ENDPOINT"),
        key=_get(env, "ACA_AZURE_OPENAI_KEY"),
        deployment=_get(env, "ACA_AZURE_OPENAI_DEPLOYMENT"),
        api_version=_get(env, "ACA_AZURE_OPENAI_API_VERSION") or DEFAULT_AZURE_OPENAI_API_VERSION,
    )


def read_entra_env(env: dict | None = None) -> EntraEnv:
    return EntraEnv(
        tenant_id=_get(env, "ACA_ENTRA_TENANT_ID"),
        client_id=_get(env, "ACA_ENTRA_CLIENT_ID"),
    )
