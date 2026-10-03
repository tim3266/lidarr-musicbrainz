"""Compare MusicBrainz vs Lidarr metadata for a release group."""

from __future__ import annotations

import os
from typing import Any

import requests

from lidarr_musicbrainz.lidarr_client import (
    library_album_by_foreign_id,
    lidarr_library_releases,
)
from lidarr_musicbrainz.mb_api import get_release_group_releases, get_release_track_count
from lidarr_musicbrainz.servarr_metadata import (
    compare_mb_servarr_release_ids,
    fetch_release_group,
)


def lidarr_metadata_lookup(release_group_mbid: str) -> list[dict[str, Any]]:
    """Servarr metadata search (album not necessarily in library)."""
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
    lidarr_in_library = False
    lidarr_album_title: str | None = None
    lidarr_artist_name: str | None = None

    if lidarr_configured:
        try:
            library = library_album_by_foreign_id(release_group_mbid)
            if library:
                lidarr_in_library = True
                lidarr_album_title = library.get("title")
                artist = library.get("artist") or {}
                lidarr_artist_name = artist.get("artistName") or artist.get("name")
                lidarr_releases = lidarr_library_releases(release_group_mbid)
            else:
                lookup = lidarr_metadata_lookup(release_group_mbid)
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
                "lidarr_in_library": lidarr_in_library,
                "lidarr_error": str(exc),
            }

    servarr: dict[str, Any] = {}
    servarr_compare: dict[str, Any] = {}
    servarr_error: str | None = None
    try:
        servarr = fetch_release_group(release_group_mbid)
        servarr_compare = compare_mb_servarr_release_ids(mb_summary, servarr)
    except requests.RequestException as exc:
        servarr_error = str(exc)
        servarr = {"available": False, "error": servarr_error}

    return {
        "release_group_mbid": release_group_mbid,
        "musicbrainz": mb_summary,
        "servarr_metadata": servarr,
        "servarr_vs_musicbrainz": servarr_compare,
        "servarr_error": servarr_error,
        "lidarr": lidarr_releases,
        "lidarr_configured": lidarr_configured,
        "lidarr_in_library": lidarr_in_library,
        "lidarr_album_title": lidarr_album_title,
        "lidarr_artist_name": lidarr_artist_name,
    }
