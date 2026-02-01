import json
import os
import urllib.error
import urllib.request

from audio_visualizer import __version__

DEFAULT_REPO_OWNER = "pulsence"
DEFAULT_REPO_NAME = "audio-visualizer"
GITHUB_API_BASE = "https://api.github.com"


def get_current_version() -> str:
    return __version__


def _get_repo() -> tuple[str, str]:
    env = os.getenv("AUDIO_VISUALIZER_REPO", "").strip()
    if env and "/" in env:
        owner, repo = env.split("/", 1)
        if owner and repo:
            return owner, repo
    return DEFAULT_REPO_OWNER, DEFAULT_REPO_NAME


def _normalize_version(version: str):
    version = (version or "").strip()
    if version.startswith("v"):
        version = version[1:]
    try:
        from packaging.version import Version

        return Version(version)
    except Exception:
        parts = [part for part in version.replace("-", ".").split(".") if part.isdigit()]
        return tuple(int(part) for part in parts)


def is_update_available(current_version: str, latest_version: str) -> bool:
    return _normalize_version(latest_version) > _normalize_version(current_version)


def fetch_latest_release(timeout_seconds: int = 8) -> dict:
    owner, repo = _get_repo()
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "audio-visualizer",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to reach GitHub: {exc}") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid response from GitHub.") from exc

    return {
        "version": data.get("tag_name") or "",
        "name": data.get("name") or "",
        "url": data.get("html_url") or "",
    }
