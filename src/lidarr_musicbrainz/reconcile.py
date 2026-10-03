"""Balance on-disk files vs MusicBrainz releases for seed proposals."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from lidarr_musicbrainz.album_files import resolve_album_file_scan
from lidarr_musicbrainz.mb_api import get_release, get_release_group_releases
from lidarr_musicbrainz.seed import BonusTrack, ReleaseSeed
from lidarr_musicbrainz.suggest import (
    _enrich_releases,
    _parse_event_date,
    _pick_source_release,
    _track_rows,
    seed_to_dict,
)


def _normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_similar(a: str, b: str) -> bool:
    na, nb = _normalize_title(a), _normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return na in nb or nb in na


def _all_recordings_by_title(release_ids: list[str]) -> dict[str, dict[str, Any]]:
    """normalized title -> {recording_id, title, length_ms, release_id}"""
    index: dict[str, dict[str, Any]] = {}
    for rid in release_ids:
        for row in _track_rows(rid):
            rec = row.get("recording_id")
            title = row.get("title") or ""
            if not rec or not title:
                continue
            key = _normalize_title(title)
            if key and key not in index:
                index[key] = {
                    "recording_id": rec,
                    "title": title,
                    "length_ms": row.get("length_ms"),
                    "release_id": rid,
                }
    return index


def _lookup_recording(title: str, index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    key = _normalize_title(title)
    if key in index:
        return index[key]
    for k, row in index.items():
        if _title_similar(key, k):
            return row
    return None


def reconcile_album(
    release_group_mbid: str,
    *,
    scan_path: str | None = None,
    use_queue: bool = False,
) -> dict[str, Any]:
    file_scan = resolve_album_file_scan(
        release_group_mbid,
        scan_path=scan_path,
        use_queue=use_queue,
    )
    if file_scan.get("error") and not file_scan.get("file_tracks"):
        return {"release_group_mbid": release_group_mbid, **file_scan}

    if not file_scan.get("file_tracks"):
        return {
            "release_group_mbid": release_group_mbid,
            "error": "Indique scan_path ou use_queue avec un grab Lidarr (outputPath).",
        }

    file_tracks = file_scan["file_tracks"]
    directory = file_scan["scan_path"]
    queue_info = file_scan.get("queue")

    mb_releases = get_release_group_releases(release_group_mbid)
    enriched = _enrich_releases(mb_releases)
    if not enriched:
        return {
            "release_group_mbid": release_group_mbid,
            "scan_path": str(directory),
            "file_tracks": file_tracks,
            "file_track_count": len(file_tracks),
            "error": "Aucune release MusicBrainz pour ce release group.",
        }

    source = _pick_source_release(enriched)
    if not source:
        return {
            "release_group_mbid": release_group_mbid,
            "scan_path": str(directory),
            "file_tracks": file_tracks,
            "error": "Impossible de choisir une release source MusicBrainz.",
        }

    source_rows = _track_rows(source["id"])
    source_count = len(source_rows)
    file_count = len(file_tracks)
    release_ids = [r["id"] for r in enriched]
    recording_index = _all_recordings_by_title(release_ids)

    paired: list[dict[str, Any]] = []
    for i in range(min(source_count, file_count)):
        sr = source_rows[i]
        fr = file_tracks[i]
        paired.append(
            {
                "index": i + 1,
                "file_title": fr["title"],
                "source_title": sr.get("title"),
                "title_match": _title_similar(fr["title"], sr.get("title") or ""),
                "recording_id": sr.get("recording_id"),
            }
        )

    source_only = [
        {
            "position": i + 1,
            "title": source_rows[i].get("title"),
            "recording_id": source_rows[i].get("recording_id"),
        }
        for i in range(file_count, source_count)
    ]

    file_only: list[dict[str, Any]] = []
    bonus_tracks: list[BonusTrack] = []
    for i in range(source_count, file_count):
        fr = file_tracks[i]
        pos = int(fr["position"]) if fr.get("position") else i + 1
        lookup = _lookup_recording(fr["title"], recording_index)
        entry: dict[str, Any] = {
            "file_position": pos,
            "file_title": fr["title"],
            "length_ms": fr.get("length_ms"),
            "recording_id": lookup.get("recording_id") if lookup else None,
            "matched_mb_title": lookup.get("title") if lookup else None,
            "matched_from_release": lookup.get("release_id") if lookup else None,
            "needs_mb_recording": lookup is None,
        }
        file_only.append(entry)
        bonus_tracks.append(
            BonusTrack(
                position=pos,
                title=fr["title"],
                recording_mbid=entry["recording_id"],
                length_ms=fr.get("length_ms"),
            )
        )

    title_mismatches = [p for p in paired if not p["title_match"]]
    missing_recording = [b for b in bonus_tracks if not b.recording_mbid]

    richest = enriched[0]
    recommended_action = "none"
    message = "Fichiers alignés avec une release source MusicBrainz."
    proposed_seed_yaml: dict[str, Any] | None = None

    if file_count > source_count:
        recommended_action = "seed_musicbrainz"
        message = (
            f"{file_count} fichiers vs {source_count} pistes sur la release source MB "
            f"({source.get('disambiguation') or 'standard'}). "
            f"Proposition : nouvelle release avec {len(bonus_tracks)} piste(s) bonus."
        )
        if missing_recording:
            message += (
                f" {len(missing_recording)} bonus sans recording MB connu — "
                "à lier à la main dans l’éditeur."
            )
    elif file_count < source_count:
        recommended_action = "fix_files_or_release"
        message = (
            f"Seulement {file_count} fichiers pour {source_count} pistes sur la release source. "
            "Import incomplet ou mauvaise release source."
        )
    elif title_mismatches:
        recommended_action = "verify_match"
        message = (
            f"Même nombre de pistes ({file_count}) mais {len(title_mismatches)} titre(s) "
            "fichier ≠ MusicBrainz — vérifier avant seed."
        )

    existing_full = [
        r for r in enriched if (r.get("track_count") or 0) == file_count
    ]
    if existing_full and file_count > source_count:
        recommended_action = "refresh_lidarr"
        message = (
            f"MusicBrainz a déjà une release à {file_count} pistes. "
            "Refresh Lidarr / choisir cette édition avant de créer un doublon."
        )

    if recommended_action == "seed_musicbrainz" and bonus_tracks:
        src_rel = get_release(source["id"])
        ac = src_rel.get("artist-credit") or []
        artist_mbid = ac[0]["artist"]["id"] if ac else ""
        artist_name = ac[0].get("name", "") if ac else ""
        y, m, d = _parse_event_date(richest.get("date"))
        disambig = richest.get("disambiguation") or f"{file_count} tracks"
        seed = ReleaseSeed(
            name=richest.get("title") or source.get("title") or "",
            release_group_mbid=release_group_mbid,
            artist_mbid=artist_mbid,
            artist_name=artist_name,
            disambiguation=disambig,
            source_release_mbid=source["id"],
            barcode=richest.get("barcode") or "",
            event_country="US",
            event_year=y,
            event_month=m,
            event_day=d,
            edit_note=(
                f"Généré par lidarr-musicbrainz /reconcile — scan {directory.name} "
                f"({file_count} pistes). Vérifier tracklist et recordings."
            ),
            bonus_tracks=bonus_tracks,
        )
        proposed_seed_yaml = seed_to_dict(seed)

    return {
        "release_group_mbid": release_group_mbid,
        "scan_path": str(directory),
        "queue": queue_info,
        "file_tracks": file_tracks,
        "file_track_count": file_count,
        "musicbrainz_source_release": source,
        "musicbrainz_source_track_count": source_count,
        "musicbrainz_richest_release": richest,
        "paired_tracks": paired,
        "file_only_tracks": file_only,
        "source_only_tracks": source_only,
        "title_mismatch_count": len(title_mismatches),
        "bonus_missing_recording_count": len(missing_recording),
        "recommended_action": recommended_action,
        "message": message,
        "proposed_seed_yaml": proposed_seed_yaml,
    }
