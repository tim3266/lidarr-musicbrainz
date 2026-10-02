"""Lidarr HTTP API helpers (queue, library album)."""

from __future__ import annotations

import os
from typing import Any

import requests


def _lidarr_session() -> tuple[str, dict[str, str]] | None:
    api_key = os.environ.get("LIDARR_API_KEY", "").strip()
    if not api_key:
        return None
    base = os.environ.get("LIDARR_URL", "http://127.0.0.1:8686").rstrip("/")
    return base, {"X-Api-Key": api_key}


def fetch_queue(page_size: int = 250) -> list[dict[str, Any]]:
    session = _lidarr_session()
    if not session:
        return []
    base, headers = session
    response = requests.get(
        f"{base}/api/v1/queue",
        params={
            "page": 1,
            "pageSize": page_size,
            "includeUnknownArtistItems": "true",
            "sortKey": "timeleft",
            "sortDirection": "descending",
        },
        headers=headers,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    records = data.get("records") if isinstance(data, dict) else data
    return records if isinstance(records, list) else []


def queue_for_release_group(foreign_album_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in fetch_queue():
        album = item.get("album") or {}
        if album.get("foreignAlbumId") == foreign_album_id:
            out.append(item)
            continue
        if item.get("foreignAlbumId") == foreign_album_id:
            out.append(item)
    return out


def pick_queue_scan_path(foreign_album_id: str) -> dict[str, Any] | None:
    """Prefer a completed grab with outputPath for the release group."""
    items = queue_for_release_group(foreign_album_id)
    if not items:
        return None

    def score(row: dict[str, Any]) -> tuple[int, int]:
        path = (row.get("outputPath") or "").strip()
        has_path = 1 if path else 0
        track_files = int(row.get("trackFileCount") or 0)
        return (has_path, track_files)

    best = max(items, key=score)
    path = (best.get("outputPath") or "").strip()
    if not path:
        return {
            "queue_item": _public_queue_item(best),
            "output_path": None,
            "error": "Aucun outputPath sur la queue (téléchargement pas terminé ?).",
        }
    return {
        "queue_item": _public_queue_item(best),
        "output_path": path,
    }


def _public_queue_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "outputPath": item.get("outputPath"),
        "trackFileCount": item.get("trackFileCount"),
        "statusMessages": item.get("statusMessages"),
        "errorMessage": item.get("errorMessage"),
    }
