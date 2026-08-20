import json
import os

import pytest

from services.secret_store import WindowsProtectedSecretStore


@pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")
def test_windows_secret_store_encrypts_round_trip_without_plaintext(tmp_path) -> None:
    path = tmp_path / "secrets.json"
    store = WindowsProtectedSecretStore(path)

    store.set("api", "highly-secret-value")

    assert store.get("api") == "highly-secret-value"
    raw = path.read_text(encoding="utf-8")
    assert "highly-secret-value" not in raw
    assert isinstance(json.loads(raw)["api"], str)

    store.delete("api")
    assert store.get("api") is None
