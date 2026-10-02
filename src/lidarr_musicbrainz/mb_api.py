"""Read-only MusicBrainz Web Service helpers."""

from __future__ import annotations

import time
from typing import Any

import musicbrainzngs as mb

USER_AGENT = "lidarr-musicbrainz/0.1.0 (https://github.com/tim3266/lidarr-musicbrainz)"


def configure_client() -> None:
    mb.set_useragent("lidarr-musicbrainz", "0.1.0", "https://github.com/tim3266/lidarr-musicbrainz")
    mb.set_rate_limit(limit_or_interval=1.0)


def get_release(release_mbid: str) -> dict[str, Any]:
    configure_client()
    time.sleep(1.05)
    payload = mb.get_release_by_id(
        release_mbid,
        includes=["recordings", "artist-credits", "labels", "release-groups"],
    )
    return payload["release"]


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
