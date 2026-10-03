"""Resolve on-disk album files (queue outputPath or explicit folder)."""

from __future__ import annotations

from typing import Any

from lidarr_musicbrainz.file_tracks import resolve_scan_path, scan_directory
from lidarr_musicbrainz.lidarr_client import _lidarr_session, pick_queue_scan_path


def resolve_album_file_scan(
    release_group_mbid: str,
    *,
    scan_path: str | None = None,
    use_queue: bool = False,
) -> dict[str, Any]:
    """
    Return file_tracks + metadata, or error/empty file_track_count when unavailable.
    """
    queue_info: dict[str, Any] | None = None
    path_str = (scan_path or "").strip()

    if use_queue and not path_str:
        if not _lidarr_session():
            return {
                "error": "LIDARR_URL et LIDARR_API_KEY requis pour use_queue.",
            }
        queue_info = pick_queue_scan_path(release_group_mbid)
        if not queue_info:
            return {"error": "Aucun item en queue pour ce release group."}
        if queue_info.get("output_path"):
            path_str = queue_info["output_path"]
        else:
            return {
                "error": queue_info.get("error", "Pas de outputPath en queue."),
                "queue": queue_info.get("queue_item"),
            }

    if not path_str:
        return {}

    try:
        directory = resolve_scan_path(path_str)
        file_tracks = scan_directory(directory)
    except (ValueError, OSError, RuntimeError) as exc:
        return {
            "scan_path": path_str,
            "queue": queue_info,
            "error": str(exc),
        }

    return {
        "scan_path": str(directory),
        "queue": queue_info,
        "file_tracks": file_tracks,
        "file_track_count": len(file_tracks),
    }
