from services.credential_service import CredentialService
from services.vesibay_readonly_client import VesibayCredentials


class MemorySecretStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def test_model_api_key_is_saved_loaded_and_cleared() -> None:
    service = CredentialService(MemorySecretStore())

    service.save_model_api_key(" secret-key ")
    assert service.load_model_api_key() == "secret-key"

    service.clear_model_api_key()
    assert service.load_model_api_key() == ""


def test_vesibay_credentials_are_saved_loaded_and_cleared() -> None:
    service = CredentialService(MemorySecretStore())
    expected = VesibayCredentials("admin", "private-password")

    service.save_vesibay_credentials(expected)
    assert service.load_vesibay_credentials() == expected

    service.clear_vesibay_credentials()
    assert service.load_vesibay_credentials() is None
