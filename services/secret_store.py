"""Windows-user-protected local storage for application secrets."""

from __future__ import annotations

import base64
import ctypes
import json
import os
import tempfile
from ctypes import wintypes
from pathlib import Path
from typing import Protocol

from core.config import CONFIG_DIR


class SecretStoreError(RuntimeError):
    """A secret could not be protected, read, or persisted."""


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class WindowsProtectedSecretStore:
    """Persist DPAPI-encrypted values that only this Windows user can decrypt."""

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def __init__(self, path: str | Path | None = None) -> None:
        override = os.environ.get("STUDENT_CODE_DIAGNOSIS_SECRET_PATH")
        self.path = Path(path or override or CONFIG_DIR / "secrets.json")

    def get(self, name: str) -> str | None:
        encoded = self._load().get(name)
        if not encoded:
            return None
        try:
            protected = base64.b64decode(encoded, validate=True)
            return self._unprotect(protected).decode("utf-8")
        except (ValueError, UnicodeError, OSError) as exc:
            raise SecretStoreError("本地凭据无法解密，请清除后重新保存。") from exc

    def set(self, name: str, value: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("secret name must be non-empty")
        if not isinstance(value, str) or not value:
            raise ValueError("secret value must be non-empty")
        payload = self._load()
        payload[name] = base64.b64encode(self._protect(value.encode("utf-8"))).decode("ascii")
        self._save(payload)

    def delete(self, name: str) -> None:
        payload = self._load()
        if name in payload:
            del payload[name]
            self._save(payload)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or not all(
                isinstance(key, str) and isinstance(item, str)
                for key, item in value.items()
            ):
                raise ValueError
            return value
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise SecretStoreError("本地凭据文件损坏。") from exc

    def _save(self, payload: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".secrets-", suffix=".json", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                json.dump(payload, file, ensure_ascii=True, indent=2)
                file.write("\n")
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _input_blob(data: bytes) -> tuple[_DataBlob, object]:
        buffer = ctypes.create_string_buffer(data)
        blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        return blob, buffer

    def _protect(self, data: bytes) -> bytes:
        if os.name != "nt":
            raise SecretStoreError("本地凭据保存目前仅支持 Windows。")
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        input_blob, input_buffer = self._input_blob(data)
        output_blob = _DataBlob()
        success = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            "Student Code Diagnosis",
            None,
            None,
            None,
            self._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        del input_buffer
        if not success:
            raise SecretStoreError("Windows 无法保护本地凭据。")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)

    def _unprotect(self, data: bytes) -> bytes:
        if os.name != "nt":
            raise SecretStoreError("本地凭据读取目前仅支持 Windows。")
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        input_blob, input_buffer = self._input_blob(data)
        output_blob = _DataBlob()
        success = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob), None, None, None, None,
            self._CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(output_blob)
        )
        del input_buffer
        if not success:
            raise SecretStoreError("Windows 无法解密本地凭据。")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)
