"""Read-only MusicBrainz Web Service helpers."""

from __future__ import annotations

import os
import time
from typing import Any

import musicbrainzngs as mb

# MusicBrainz rejette les User-Agent contenant « lidarr-musicbrainz » (403).
APP_NAME = "LidarrMusicBrainz"
APP_VERSION = "0.1.0"
DEFAULT_CONTACT = "https://github.com/tim3266/lidarr-musicbrainz/issues"


def configure_client() -> None:
    contact = (
        os.environ.get("MUSICBRAINZ_APP_CONTACT")
        or os.environ.get("MB_APP_CONTACT")
        or DEFAULT_CONTACT
    )
    mb.set_useragent(APP_NAME, APP_VERSION, contact)
    mb.set_rate_limit(limit_or_interval=1.1)


def get_release(release_mbid: str) -> dict[str, Any]:
    configure_client()
    time.sleep(1.05)
    payload = mb.get_release_by_id(
        release_mbid,
        includes=["recordings", "artist-credits"],
    )
    return payload["release"]


def get_release_group_releases(release_group_mbid: str) -> list[dict[str, Any]]:
    configure_client()
    time.sleep(1.05)
    payload = mb.get_release_group_by_id(
        release_group_mbid,
        includes=["releases"],
    )
    group = payload.get("release-group") or payload
    return list(group.get("release-list") or group.get("releases") or [])


def get_release_track_count(release_mbid: str) -> int | None:
    configure_client()
    time.sleep(1.05)
    payload = mb.get_release_by_id(release_mbid, includes=["recordings"])
    release = payload.get("release") or payload
    total = 0
    for medium in release.get("medium-list") or release.get("media") or []:
        tracks = medium.get("track-list") or medium.get("tracks") or []
        total += len(tracks)
    return total if total else None


def recording_mbid(track: dict[str, Any]) -> str | None:
    rec = track.get("recording")
    if not rec:
        return None
    return rec.get("id")


def track_length_ms(track: dict[str, Any]) -> int | None:
    rec = track.get("recording") or {}
    length = rec.get("length") or track.get("length")
    if length is None:
        return None
    try:
        return int(length)
    except (TypeError, ValueError):
        return None
