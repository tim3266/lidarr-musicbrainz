"""Compare MusicBrainz vs Lidarr metadata for a release group."""

from __future__ import annotations

import os
from typing import Any

import requests

from lidarr_musicbrainz.mb_api import get_release_group_releases, get_release_track_count


def lidarr_album_lookup(release_group_mbid: str) -> list[dict[str, Any]]:
    base = os.environ.get("LIDARR_URL", "http://127.0.0.1:8686").rstrip("/")
    api_key = os.environ.get("LIDARR_API_KEY", "")
    if not api_key:
        return []
    response = requests.get(
        f"{base}/api/v1/album/lookup",
        params={"term": release_group_mbid},
        headers={"X-Api-Key": api_key},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def album_status(release_group_mbid: str) -> dict[str, Any]:
    mb_releases = get_release_group_releases(release_group_mbid)
    mb_summary = [
        {
            "id": r["id"],
            "date": r.get("date"),
            "disambiguation": r.get("disambiguation", ""),
            "barcode": r.get("barcode", ""),
            "track_count": get_release_track_count(r["id"]),
        }
        for r in mb_releases
    ]

    lidarr_releases: list[dict[str, Any]] = []
    lidarr_configured = bool(os.environ.get("LIDARR_API_KEY"))
    if lidarr_configured:
        try:
            lookup = lidarr_album_lookup(release_group_mbid)
            if lookup:
                for rel in lookup[0].get("releases") or []:
                    lidarr_releases.append(
                        {
                            "title": rel.get("title"),
                            "disambiguation": rel.get("disambiguation", ""),
                            "releaseDate": rel.get("releaseDate"),
                            "trackCount": rel.get("trackCount"),
                            "status": rel.get("status"),
                        }
                    )
        except requests.RequestException as exc:
            return {
                "release_group_mbid": release_group_mbid,
                "musicbrainz": mb_summary,
                "lidarr": lidarr_releases,
                "lidarr_configured": True,
                "lidarr_error": str(exc),
            }

    return {
        "release_group_mbid": release_group_mbid,
        "musicbrainz": mb_summary,
        "lidarr": lidarr_releases,
        "lidarr_configured": lidarr_configured,
    }
