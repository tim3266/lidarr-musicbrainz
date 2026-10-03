"""Who created a MusicBrainz release (editor), and whether that is the configured account."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from lidarr_musicbrainz.session_submit import (
    MusicBrainzAuthError,
    USER_AGENT,
    credentials_from_env,
    login_session,
)

_ADD_RELEASE = re.compile(
    r"add release|add medium and release|import release",
    re.I,
)
_USER_LINK = re.compile(r'href="/user/([^"/]+)"')
_EDIT_LINK = re.compile(r'href="/edit/(\d+)"')


def _config_dir() -> Path:
    return Path(os.environ.get("MB_CONFIG_DIR", "/config"))


def _registry_path() -> Path:
    return _config_dir() / "submitted_releases.json"


def _mb_account_name() -> str:
    return (
        os.environ.get("MUSICBRAINZ_USER")
        or os.environ.get("MB_USER")
        or ""
    ).strip()


def _extra_my_release_ids() -> set[str]:
    raw = os.environ.get("MUSICBRAINZ_MY_RELEASE_MBIDS", "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.is_file():
        return {"releases": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"releases": {}}
    if not isinstance(data, dict):
        return {"releases": {}}
    releases = data.get("releases")
    if not isinstance(releases, dict):
        data["releases"] = {}
    return data


def record_submitted_release(
    release_mbid: str,
    *,
    editor: str | None = None,
    source: str = "submit",
) -> None:
    """Persist a release MBID this tool (or you) registered as yours."""
    rid = release_mbid.strip().lower()
    if not rid:
        return
    data = _load_registry()
    releases = data.setdefault("releases", {})
    releases[rid] = {
        "editor": editor or _mb_account_name() or None,
        "source": source,
    }
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def record_from_submit_url(submit_url: str | None) -> None:
    if not submit_url:
        return
    parsed = urlparse(submit_url)
    q = parse_qs(parsed.query)
    for key in ("release_mbid", "mbid"):
        values = q.get(key) or []
        if values:
            record_submitted_release(values[0], source="submit")
            return
    match = re.search(
        r"/release/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        submit_url,
        re.I,
    )
    if match:
        record_submitted_release(match.group(1), source="submit")


def _editor_is_me(editor: str | None) -> bool | None:
    me = _mb_account_name().lower()
    if not editor or not me:
        return None
    return editor.lower() == me


def _registry_hit(release_mbid: str) -> dict[str, Any] | None:
    rid = release_mbid.lower()
    entry = (_load_registry().get("releases") or {}).get(rid)
    if isinstance(entry, dict):
        return entry
    if rid in _extra_my_release_ids():
        return {"editor": _mb_account_name() or None, "source": "env"}
    return None


def _parse_creation_editor(html: str) -> dict[str, Any]:
    if "Verifying your browser" in html or "__meb_verify" in html:
        return {"error": "MusicBrainz exige une vérification navigateur (session requise)."}

    blocks = re.split(r"<tr\b", html, flags=re.I)
    for block in blocks:
        if not _ADD_RELEASE.search(block):
            continue
        edit_id = _EDIT_LINK.search(block)
        user = _USER_LINK.search(block)
        if user:
            edit_type = _ADD_RELEASE.search(block)
            label = edit_type.group(0) if edit_type else "Add release"
            out: dict[str, Any] = {
                "editor": user.group(1),
                "edit_type": label,
                "source": "musicbrainz_edits",
            }
            if edit_id:
                out["edit_id"] = int(edit_id.group(1))
            return out

    idx = html.lower().find("add release")
    if idx >= 0:
        window = html[max(0, idx - 1200) : idx + 1200]
        user = _USER_LINK.search(window)
        if user:
            return {
                "editor": user.group(1),
                "edit_type": "Add release",
                "source": "musicbrainz_edits",
            }

    return {"editor": None, "source": "musicbrainz_edits"}


def fetch_creation_editor_from_musicbrainz(release_mbid: str) -> dict[str, Any]:
    """
    Read the release edit history (Add release) using MUSICBRAINZ_USER/PASSWORD if set.
    """
    url = f"https://musicbrainz.org/release/{release_mbid}/edits"
    try:
        user, password = credentials_from_env()
    except MusicBrainzAuthError:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        response = session.get(url, params={"order": "asc", "limit": 50}, timeout=60)
    else:
        session = login_session(user, password)
        response = session.get(url, params={"order": "asc", "limit": 50}, timeout=60)

    response.raise_for_status()
    parsed = _parse_creation_editor(response.text)
    parsed.setdefault("release_mbid", release_mbid)
    return parsed


def release_creation_info(release_mbid: str | None) -> dict[str, Any]:
    """
    Editor who added the release on MusicBrainz, and whether it matches MUSICBRAINZ_USER.
    """
    if not release_mbid:
        return {
            "editor": None,
            "editor_is_me": None,
            "source": None,
        }

    reg = _registry_hit(release_mbid)
    if reg and reg.get("editor"):
        editor = str(reg["editor"])
        return {
            "editor": editor,
            "editor_is_me": _editor_is_me(editor) if _mb_account_name() else True,
            "source": reg.get("source") or "registry",
            "via_registry": True,
        }
    if reg:
        me = _mb_account_name()
        return {
            "editor": me or None,
            "editor_is_me": True if me else None,
            "source": reg.get("source") or "registry",
            "via_registry": True,
        }

    try:
        credentials_from_env()
    except MusicBrainzAuthError:
        return {
            "editor": None,
            "editor_is_me": None,
            "source": None,
            "error": (
                "Définis MUSICBRAINZ_USER et MUSICBRAINZ_PASSWORD, "
                "ou MUSICBRAINZ_MY_RELEASE_MBIDS pour marquer tes releases."
            ),
        }

    try:
        live = fetch_creation_editor_from_musicbrainz(release_mbid)
    except requests.RequestException as exc:
        return {
            "editor": None,
            "editor_is_me": None,
            "source": None,
            "error": str(exc),
        }

    if live.get("error"):
        return {
            "editor": None,
            "editor_is_me": None,
            "source": live.get("source"),
            "error": live["error"],
        }

    editor = live.get("editor")
    return {
        "editor": editor,
        "editor_is_me": _editor_is_me(editor) if editor else None,
        "edit_id": live.get("edit_id"),
        "edit_type": live.get("edit_type"),
        "source": live.get("source"),
        "edit_url": (
            f"https://musicbrainz.org/edit/{live['edit_id']}" if live.get("edit_id") else None
        ),
    }
