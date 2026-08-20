"""Application-level access to locally protected credentials."""

from __future__ import annotations

import json
from dataclasses import dataclass

from services.secret_store import SecretStore, WindowsProtectedSecretStore
from services.vesibay_readonly_client import VesibayCredentials


_MODEL_API_KEY = "model_api_key"
_VESIBAY_CREDENTIALS = "vesibay_credentials"


@dataclass(slots=True)
class CredentialService:
    store: SecretStore | None = None

    def __post_init__(self) -> None:
        if self.store is None:
            self.store = WindowsProtectedSecretStore()

    def load_model_api_key(self) -> str:
        assert self.store is not None
        return self.store.get(_MODEL_API_KEY) or ""

    def save_model_api_key(self, api_key: str) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("API Key不能为空。")
        assert self.store is not None
        self.store.set(_MODEL_API_KEY, api_key.strip())

    def clear_model_api_key(self) -> None:
        assert self.store is not None
        self.store.delete(_MODEL_API_KEY)

    def load_vesibay_credentials(self) -> VesibayCredentials | None:
        assert self.store is not None
        raw = self.store.get(_VESIBAY_CREDENTIALS)
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return VesibayCredentials(
                username=payload["username"], password=payload["password"]
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("本地网站凭据格式无效，请清除后重新保存。") from exc

    def save_vesibay_credentials(self, credentials: VesibayCredentials) -> None:
        assert self.store is not None
        self.store.set(
            _VESIBAY_CREDENTIALS,
            json.dumps(
                {"username": credentials.username, "password": credentials.password},
                ensure_ascii=False,
            ),
        )

    def clear_vesibay_credentials(self) -> None:
        assert self.store is not None
        self.store.delete(_VESIBAY_CREDENTIALS)
