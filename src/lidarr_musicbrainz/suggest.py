"""Suggest actions and optional seed YAML from MusicBrainz + Lidarr state."""

from __future__ import annotations

from typing import Any

from lidarr_musicbrainz.mb_api import get_release, get_release_group_releases, get_release_track_count
from lidarr_musicbrainz.seed import BonusTrack, ReleaseSeed
from lidarr_musicbrainz.status import album_status


def _track_rows(release_mbid: str) -> list[dict[str, Any]]:
    release = get_release(release_mbid)
    rows: list[dict[str, Any]] = []
    for medium in release.get("medium-list") or release.get("media") or []:
        for track in medium.get("track-list") or medium.get("tracks") or []:
            rec = track.get("recording") or {}
            rows.append(
                {
                    "title": track.get("title") or rec.get("title"),
                    "recording_id": rec.get("id"),
                    "length_ms": rec.get("length"),
                }
            )
    return rows


def _enrich_releases(releases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rel in releases:
        rid = rel["id"]
        out.append(
            {
                "id": rid,
                "title": rel.get("title"),
                "date": rel.get("date"),
                "disambiguation": rel.get("disambiguation") or "",
                "barcode": rel.get("barcode") or "",
                "status": rel.get("status"),
                "track_count": get_release_track_count(rid),
            }
        )
    return sorted(
        out,
        key=lambda r: (r.get("track_count") or 0, r.get("date") or ""),
        reverse=True,
    )


def _pick_source_release(enriched: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [r for r in enriched if (r.get("track_count") or 0) > 0]
    if not candidates:
        return None
    standard = [r for r in candidates if not r.get("disambiguation")]
    pool = standard or candidates
    return min(pool, key=lambda r: (r.get("track_count") or 0))


def _bonus_recording_ids(source_id: str, target_id: str) -> list[dict[str, Any]]:
    source_recs = {r["recording_id"] for r in _track_rows(source_id) if r.get("recording_id")}
    bonus: list[dict[str, Any]] = []
    for row in _track_rows(target_id):
        rid = row.get("recording_id")
        if rid and rid not in source_recs:
            bonus.append(row)
            source_recs.add(rid)
    return bonus


def seed_to_dict(seed: ReleaseSeed) -> dict[str, Any]:
    return {
        "name": seed.name,
        "disambiguation": seed.disambiguation,
        "release_group_mbid": seed.release_group_mbid,
        "artist_mbid": seed.artist_mbid,
        "artist_name": seed.artist_name,
        "source_release_mbid": seed.source_release_mbid,
        "status": seed.status,
        "medium_format": seed.medium_format,
        "secondary_type": seed.secondary_type,
        "language": seed.language,
        "script": seed.script,
        "barcode": seed.barcode,
        "event_country": seed.event_country,
        "event_year": seed.event_year,
        "event_month": seed.event_month,
        "event_day": seed.event_day,
        "edit_note": seed.edit_note,
        "bonus_tracks": [
            {
                "position": b.position,
                "title": b.title,
                "recording_mbid": b.recording_mbid,
                "length_ms": b.length_ms,
            }
            for b in seed.bonus_tracks
        ],
    }


def _parse_event_date(date_str: str | None) -> tuple[int | None, int | None, int | None]:
    if not date_str:
        return None, None, None
    parts = date_str.split("-")
    y = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else None
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    d = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    return y, m, d


def suggest_album(release_group_mbid: str) -> dict[str, Any]:
    status = album_status(release_group_mbid)
    enriched = _enrich_releases(get_release_group_releases(release_group_mbid))
    if not enriched:
        return {
            "release_group_mbid": release_group_mbid,
            "error": "Aucune release sur MusicBrainz pour ce release group.",
            "lidarr_configured": status.get("lidarr_configured"),
        }

    richest = enriched[0]
    richest_count = richest.get("track_count") or 0
    source = _pick_source_release(enriched)
    source_count = (source or {}).get("track_count") or 0

    lidarr_releases = status.get("lidarr") or []
    lidarr_max = max((r.get("trackCount") or 0 for r in lidarr_releases), default=0)
    lidarr_has_richest = richest_count > 0 and lidarr_max >= richest_count

    recommended_action = "none"
    message = "Rien à faire de particulier."
    proposed_seed_yaml: dict[str, Any] | None = None

    if richest_count == 0:
        recommended_action = "fix_musicbrainz"
        message = "Tracklists manquantes ou incomplètes sur MusicBrainz."
    elif status.get("lidarr_configured") and not lidarr_releases:
        recommended_action = "refresh_lidarr"
        message = "Album non trouvé via Lidarr lookup — ajouter l’artiste ou vérifier le release group MBID."
    elif status.get("lidarr_configured") and not lidarr_has_richest:
        recommended_action = "refresh_lidarr"
        message = (
            f"MusicBrainz : édition max {richest_count} pistes "
            f"({richest.get('disambiguation') or 'standard'}, {richest.get('date') or '?'}). "
            f"Lidarr/Servarr : max {lidarr_max} pistes. "
            "Attendre la synchro Servarr ou refresh artiste — pas besoin d’un nouvel edit MusicBrainz."
        )
    elif source and richest_count > source_count and richest["id"] != source["id"]:
        # Édition la plus complète déjà distincte sur MB
        recommended_action = "refresh_lidarr" if status.get("lidarr_configured") else "none"
        message = (
            f"L’édition la plus complète ({richest_count} pistes) est déjà sur MusicBrainz. "
            "Configure LIDARR_API_KEY pour comparer au cache Servarr."
        )

    # Proposer un YAML seed seulement si la cible « riche » n’existe pas encore sur MB
    # mais qu’on peut la déduire (union de pistes sur une autre release du groupe)
    if source and richest_count > source_count:
        existing_richest_ids = {r["id"] for r in enriched if (r.get("track_count") or 0) == richest_count}
        if richest["id"] in existing_richest_ids and len(existing_richest_ids) >= 1:
            pass  # déjà sur MB, pas de seed
        else:
            bonus_rows = _bonus_recording_ids(source["id"], richest["id"])
            if bonus_rows:
                recommended_action = "seed_musicbrainz"
                message = (
                    "Proposition de seed pour une édition plus complète — "
                    "compléter barcode, label et edit note avant soumission."
                )
                src_rel = get_release(source["id"])
                ac = src_rel.get("artist-credit") or []
                artist_mbid = ac[0]["artist"]["id"] if ac else ""
                artist_name = ac[0].get("name", "") if ac else ""
                y, m, d = _parse_event_date(richest.get("date"))
                seed = ReleaseSeed(
                    name=richest.get("title") or source.get("title") or "",
                    release_group_mbid=release_group_mbid,
                    artist_mbid=artist_mbid,
                    artist_name=artist_name,
                    disambiguation=richest.get("disambiguation") or "",
                    source_release_mbid=source["id"],
                    barcode=richest.get("barcode") or "",
                    event_country="US",
                    event_year=y,
                    event_month=m,
                    event_day=d,
                    edit_note=(
                        "Généré par lidarr-musicbrainz /suggest — vérifier avant soumission MusicBrainz."
                    ),
                    bonus_tracks=[
                        BonusTrack(
                            position=source_count + i + 1,
                            title=str(row["title"]),
                            recording_mbid=row.get("recording_id"),
                            length_ms=row.get("length_ms"),
                        )
                        for i, row in enumerate(bonus_rows)
                    ],
                )
                proposed_seed_yaml = seed_to_dict(seed)

    return {
        "release_group_mbid": release_group_mbid,
        "musicbrainz_releases": enriched,
        "richest_musicbrainz": richest,
        "standard_source_musicbrainz": source,
        "lidarr_max_track_count": lidarr_max,
        "lidarr_has_richest_edition": lidarr_has_richest,
        "recommended_action": recommended_action,
        "message": message,
        "proposed_seed_yaml": proposed_seed_yaml,
        "lidarr_releases": lidarr_releases,
        "lidarr_configured": status.get("lidarr_configured"),
        "lidarr_error": status.get("lidarr_error"),
    }
