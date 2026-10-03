"""Servarr metadata API (cache between MusicBrainz and Lidarr)."""

from __future__ import annotations

import os
from typing import Any

import requests


def servarr_metadata_base_url() -> str:
    return os.environ.get(
        "SERVARR_METADATA_URL",
        "https://api.lidarr.audio/api/v0.4",
    ).rstrip("/")


def fetch_release_group(foreign_album_id: str) -> dict[str, Any]:
    """
    GET /album/{release-group-mbid} on the Servarr metadata server.

    Returns a normalized dict. On cache miss the API may respond 503.
    """
    url = f"{servarr_metadata_base_url()}/album/{foreign_album_id}"
    response = requests.get(
        url,
        headers={"Accept": "application/json", "User-Agent": "LidarrMusicBrainz/0.2"},
        timeout=90,
    )
    if response.status_code == 503:
        return {
            "available": False,
            "http_status": 503,
            "error": "Cache Servarr absent ou en génération (503). Réessayer ou !refresh album sur Discord.",
            "url": url,
        }
    if response.status_code == 404:
        return {
            "available": False,
            "http_status": 404,
            "error": "Release group inconnu du serveur metadata Servarr.",
            "url": url,
        }
    response.raise_for_status()
    payload = response.json()
    releases_raw = payload.get("Releases") or payload.get("releases") or []
    releases: list[dict[str, Any]] = []
    for rel in releases_raw:
        releases.append(
            {
                "id": rel.get("Id") or rel.get("id"),
                "title": rel.get("Title") or rel.get("title"),
                "disambiguation": rel.get("Disambiguation") or rel.get("disambiguation") or "",
                "release_date": rel.get("ReleaseDate") or rel.get("releaseDate"),
                "track_count": rel.get("TrackCount") or rel.get("trackCount"),
                "status": rel.get("Status") or rel.get("status"),
                "country": rel.get("Country") or rel.get("country"),
                "label": rel.get("Label") or rel.get("label"),
            }
        )
    releases.sort(key=lambda r: (r.get("track_count") or 0), reverse=True)
    max_tracks = max((r.get("track_count") or 0 for r in releases), default=0)
    return {
        "available": True,
        "http_status": response.status_code,
        "url": url,
        "title": payload.get("title") or payload.get("Title"),
        "release_date": payload.get("releasedate") or payload.get("releaseDate"),
        "release_count": len(releases),
        "max_track_count": max_tracks,
        "releases": releases,
    }


def compare_mb_servarr_release_ids(
    mb_releases: list[dict[str, Any]],
    servarr: dict[str, Any],
) -> dict[str, Any]:
    """Which MusicBrainz release MBIDs are missing from Servarr cache."""
    if not servarr.get("available"):
        return {
            "missing_on_servarr": [],
            "extra_on_servarr": [],
            "mb_ids_on_servarr": [],
        }
    mb_ids = {r["id"] for r in mb_releases if r.get("id")}
    srv_ids = {r["id"] for r in servarr.get("releases") or [] if r.get("id")}
    return {
        "missing_on_servarr": [
            r for r in mb_releases if r.get("id") and r["id"] not in srv_ids
        ],
        "extra_on_servarr": [
            r for r in (servarr.get("releases") or []) if r.get("id") and r["id"] not in mb_ids
        ],
        "mb_ids_on_servarr": sorted(srv_ids & mb_ids),
    }
