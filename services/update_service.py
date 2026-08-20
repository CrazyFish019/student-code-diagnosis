"""Read-only GitHub Release update checks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.version import UPDATE_REPOSITORY, __version__
from services.json_http_client import (
    JsonHttpTransport,
    NetworkRequestError,
    UrllibJsonHttpTransport,
)


_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class UpdateCheckError(RuntimeError):
    """An update check could not produce a trustworthy result."""


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_url: str
    installer_url: str | None

    @property
    def update_available(self) -> bool:
        return _version_tuple(self.latest_version) > _version_tuple(self.current_version)


def check_for_updates(
    *,
    repository: str = UPDATE_REPOSITORY,
    current_version: str = __version__,
    transport: JsonHttpTransport | None = None,
    timeout_seconds: int = 5,
) -> UpdateInfo:
    if not _REPOSITORY.fullmatch(repository):
        raise UpdateCheckError("当前版本尚未配置更新源。")
    endpoint = f"https://api.github.com/repos/{repository}/releases/latest"
    try:
        response = (transport or UrllibJsonHttpTransport()).request_json(
            "GET",
            endpoint,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"StudentCodeDiagnosis/{current_version}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout_seconds=timeout_seconds,
        )
    except NetworkRequestError as exc:
        raise UpdateCheckError("无法连接更新服务器，请稍后重试。") from exc
    if response.status_code == 404:
        raise UpdateCheckError("更新源中还没有可用的正式版本。")
    if response.status_code != 200:
        raise UpdateCheckError("更新服务器暂时不可用。")
    tag = response.payload.get("tag_name")
    release_url = response.payload.get("html_url")
    if not isinstance(tag, str) or not isinstance(release_url, str):
        raise UpdateCheckError("更新服务器返回的数据不完整。")
    latest_version = tag.removeprefix("v")
    _version_tuple(latest_version)
    installer_url = _installer_asset_url(response.payload.get("assets"))
    return UpdateInfo(current_version, latest_version, release_url, installer_url)


def _installer_asset_url(assets: object) -> str | None:
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if (
            isinstance(name, str)
            and name.lower().endswith(".exe")
            and "setup" in name.lower()
            and isinstance(url, str)
            and url.startswith("https://github.com/")
        ):
            return url
    return None


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value.strip())
    if match is None:
        raise UpdateCheckError("更新版本号格式无效。")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]
