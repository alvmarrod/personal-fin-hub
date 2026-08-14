import logging
import threading
import time
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from services.config import config

logger = logging.getLogger(__name__)


def _read_backend_version() -> str:
    """Read the backend version from ``pyproject.toml`` (canonical source)."""
    path = Path(__file__).parent.parent / "pyproject.toml"
    try:
        data = tomllib.loads(path.read_text())
        return str(data["project"]["version"])
    except Exception as e:  # pragma: no cover - defensive fallback
        logger.warning("update_check: cannot read backend version from %s: %s", path, e)
        return "0.0.0"


_BACKEND_VERSION = _read_backend_version()


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple of integers.

    Strips an optional ``side/v`` prefix (e.g. ``backend/v0.11.0``) and treats
    any non-numeric component as ``0`` so malformed segments order lowest.
    """
    tag = version.rsplit("/", 1)[-1].lstrip("vV")
    parts: list[int] = []
    for segment in tag.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def bare_version(tag: str) -> str:
    """Strip an optional ``side/v`` prefix, returning the plain version."""
    return tag.rsplit("/", 1)[-1].lstrip("vV")


def max_version(tags: list[str]) -> str | None:
    """Return the tag with the greatest semantic version, or ``None``."""
    if not tags:
        return None
    return max(tags, key=parse_version)


def latest_by_prefix(releases: list[dict], prefix: str) -> str | None:
    """Return the greatest release tag under ``prefix`` (e.g. ``backend/``)."""
    tags = [r["tag_name"] for r in releases if r.get("tag_name", "").startswith(prefix)]
    return max_version(tags)


@dataclass
class ComponentUpdate:
    """Update status for a single component (backend or frontend)."""

    current: str
    latest: str | None
    outdated: bool
    url: str | None


def release_url(tag: str) -> str:
    """Build the public release URL for a tag."""
    return f"https://github.com/{config.update_check_repo}/releases/tag/{tag}"


def _component_status(current: str, latest_tag: str | None) -> ComponentUpdate:
    if latest_tag is None:
        return ComponentUpdate(current=current, latest=None, outdated=False, url=None)
    return ComponentUpdate(
        current=current,
        latest=bare_version(latest_tag),
        outdated=parse_version(latest_tag) > parse_version(current),
        url=release_url(latest_tag),
    )


def _to_dict(status: ComponentUpdate) -> dict:
    return {"current": status.current, "latest": status.latest, "outdated": status.outdated, "url": status.url}


_cache: dict = {"fetched_at": 0.0, "releases": None}
_lock = threading.Lock()


def reset_cache() -> None:
    """Clear the release cache (used by tests)."""
    with _lock:
        _cache["fetched_at"] = 0.0
        _cache["releases"] = None


def _fetch_releases() -> list[dict]:
    """Fetch the public GitHub releases list (unauthenticated)."""
    url = f"https://api.github.com/repos/{config.update_check_repo}/releases?per_page=100"
    with httpx.Client(timeout=config.update_check_timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def _fetch_releases_cached() -> list[dict]:
    """Fetch releases, reusing the cached result within the TTL."""
    now = time.monotonic()
    with _lock:
        if _cache["releases"] is not None and now - _cache["fetched_at"] < config.update_check_cache_seconds:
            return _cache["releases"]

    releases = _fetch_releases()
    with _lock:
        _cache["releases"] = releases
        _cache["fetched_at"] = time.monotonic()
    return releases


def get_update_status(frontend_version: str | None = None) -> dict:
    """Return the update-availability status for the backend and frontend.

    Parameters
    ----------
    frontend_version : str or None
        The frontend's own version, self-reported by the UI. When omitted the
        ``frontend`` field is ``None``.

    Returns
    -------
    dict
        ``{enabled, backend, frontend, checked_at}``, with an ``error`` key
        when GitHub is unreachable (fail-open: never a false ``outdated``).
    """
    if not config.update_check_enabled:
        return {"enabled": False}

    checked_at = datetime.now(UTC).isoformat()
    try:
        releases = _fetch_releases_cached()
    except Exception as e:  # fail-open on any transport/HTTP error
        logger.warning("update check unavailable: %s", e)
        return {"enabled": True, "error": "unavailable", "backend": None, "frontend": None, "checked_at": checked_at}

    backend = _component_status(_BACKEND_VERSION, latest_by_prefix(releases, "backend/"))
    frontend = None
    if frontend_version:
        frontend = _component_status(frontend_version, latest_by_prefix(releases, "frontend/"))

    return {
        "enabled": True,
        "backend": _to_dict(backend),
        "frontend": _to_dict(frontend) if frontend else None,
        "checked_at": checked_at,
    }
