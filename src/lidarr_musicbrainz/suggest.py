"""Suggest actions and optional seed YAML from MusicBrainz + Lidarr state."""

from __future__ import annotations

from typing import Any

from lidarr_musicbrainz.album_files import resolve_album_file_scan
from lidarr_musicbrainz.mb_release_provenance import release_creation_info
from lidarr_musicbrainz.mb_api import (
    get_release,
    get_release_artist_credit,
    get_release_group_bundle,
    get_release_track_count,
)
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


def _releases_with_track_count(
    releases: list[dict[str, Any]],
    count: int,
    field: str = "track_count",
) -> list[dict[str, Any]]:
    return [r for r in releases if (r.get(field) or 0) == count]


def _pick_preferred_release(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not matches:
        return None
    with_dis = [m for m in matches if (m.get("disambiguation") or "").strip()]
    return with_dis[0] if with_dis else matches[0]


def _format_release_short(rel: dict[str, Any]) -> str:
    label = rel.get("disambiguation") or rel.get("title") or rel.get("id", "")[:8]
    rid = rel.get("id") or rel.get("foreignReleaseId") or "?"
    tc = rel.get("track_count") or rel.get("trackCount") or "?"
    return f"«{label}» ({tc} p., {rid})"


def _edition_summary(rel: dict[str, Any] | None) -> dict[str, Any] | None:
    if not rel:
        return None
    label = (rel.get("disambiguation") or rel.get("title") or "").strip() or "édition standard"
    return {
        "label": label,
        "track_count": rel.get("track_count") or rel.get("trackCount"),
        "date": rel.get("date") or rel.get("releaseDate") or "",
        "mbid": rel.get("id") or rel.get("foreignReleaseId") or "",
        "monitored": rel.get("monitored"),
    }


def _files_summary(file_scan: dict[str, Any]) -> dict[str, Any]:
    count = int(file_scan.get("file_track_count") or 0)
    path = file_scan.get("scan_path") or ""
    queue = file_scan.get("queue") or {}
    queue_item = queue.get("queue_item") if isinstance(queue, dict) else None
    source = "queue" if queue_item else ("path" if path else "none")
    return {
        "track_count": count,
        "source": source,
        "scan_path": path,
        "queue_title": (queue_item or {}).get("title") if queue_item else None,
        "queue_status": (queue_item or {}).get("status") if queue_item else None,
        "error": file_scan.get("error"),
    }


def build_analysis_display(
    *,
    file_scan: dict[str, Any],
    file_based: dict[str, Any] | None,
    mb_group: dict[str, Any],
    status: dict[str, Any],
    richest: dict[str, Any],
    servarr: dict[str, Any],
    matched_mb_artist_credit: str = "",
    mb_creation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    files = _files_summary(file_scan)
    target_n = files["track_count"] or None
    mb_match = (file_based or {}).get("matched_musicbrainz_release")
    lidarr_match = (file_based or {}).get("matched_lidarr_release")
    if not mb_match and not target_n:
        mb_match = richest

    mb_edition = _edition_summary(mb_match)
    if mb_edition and matched_mb_artist_credit:
        mb_edition["artist_credit"] = matched_mb_artist_credit

    mb_at_n = (file_based or {}).get("musicbrainz_releases_matching_files")
    if mb_at_n is None and target_n:
        mb_at_n = [r for r in (status.get("musicbrainz") or []) if (r.get("track_count") or 0) == target_n]

    lidarr_at_n = (file_based or {}).get("lidarr_releases_matching_files")
    if lidarr_at_n is None and target_n:
        lidarr_at_n = [
            r for r in (status.get("lidarr") or []) if (r.get("trackCount") or 0) == target_n
        ]

    servarr_ok = bool(servarr.get("available"))
    mb_on_servarr = True
    if mb_match and servarr_ok:
        srv_ids = {r.get("id") for r in servarr.get("releases") or [] if r.get("id")}
        mb_on_servarr = mb_match.get("id") in srv_ids

    return {
        "files": files,
        "target_track_count": target_n,
        "musicbrainz": {
            "release_group_title": mb_group.get("title") or "",
            "artist_name": mb_group.get("artist_name") or "",
            "target_edition": mb_edition,
            "editions_at_target_count": len(mb_at_n or []),
            "richest_track_count": richest.get("track_count"),
            "on_servarr_cache": mb_on_servarr if servarr_ok else None,
            "creation_editor": (mb_creation or {}).get("editor"),
            "creation_editor_is_me": (mb_creation or {}).get("editor_is_me"),
            "creation_edit_url": (mb_creation or {}).get("edit_url"),
            "creation_source": (mb_creation or {}).get("source"),
            "creation_error": (mb_creation or {}).get("error"),
        },
        "lidarr": {
            "artist_name": status.get("lidarr_artist_name") or "",
            "album_title": status.get("lidarr_album_title") or "",
            "in_library": status.get("lidarr_in_library"),
            "configured": status.get("lidarr_configured"),
            "target_edition": _edition_summary(lidarr_match),
            "editions_at_target_count": len(lidarr_at_n or []),
            "max_track_count": max(
                (r.get("trackCount") or 0 for r in (status.get("lidarr") or [])),
                default=0,
            ),
        },
    }


def _suggest_from_files(
    release_group_mbid: str,
    file_count: int,
    file_scan: dict[str, Any],
    enriched: list[dict[str, Any]],
    status: dict[str, Any],
    servarr: dict[str, Any],
    lidarr_releases: list[dict[str, Any]],
) -> dict[str, Any] | None:
    mb_matches = _releases_with_track_count(enriched, file_count)
    srv_matches = _releases_with_track_count(
        servarr.get("releases") or [],
        file_count,
        "track_count",
    )
    lidarr_matches = _releases_with_track_count(
        lidarr_releases,
        file_count,
        "trackCount",
    )
    target_mb = _pick_preferred_release(mb_matches)
    target_srv = _pick_preferred_release(srv_matches)
    monitored = [r for r in lidarr_matches if r.get("monitored")]

    servarr_ids = {r.get("id") for r in servarr.get("releases") or [] if r.get("id")}

    recommended_action = "none"
    message = f"{file_count} fichiers audio — recherche d’une release à {file_count} pistes."
    proposed_seed_yaml: dict[str, Any] | None = None

    if not target_mb:
        recommended_action = "seed_musicbrainz"
        message = (
            f"{file_count} fichiers — aucune release MusicBrainz avec exactement {file_count} pistes. "
            "Utilise « Créer une release sur MusicBrainz (fichiers) » ou POST /reconcile."
        )
        from lidarr_musicbrainz.reconcile import reconcile_album

        recon = reconcile_album(
            release_group_mbid,
            scan_path=file_scan.get("scan_path"),
            use_queue=False,
        )
        proposed_seed_yaml = recon.get("proposed_seed_yaml")
        if recon.get("message"):
            message += " " + recon["message"]
    elif target_mb["id"] not in servarr_ids:
        recommended_action = "refresh_servarr_cache"
        message = (
            f"{file_count} fichiers → correspondance MusicBrainz {_format_release_short(target_mb)} "
            f"absente du cache Servarr ({len(srv_matches)} release(s) à {file_count} p. côté Servarr). "
            f"Discord : !refresh album/{release_group_mbid} puis refresh artiste Lidarr."
        )
    elif not lidarr_matches:
        recommended_action = "refresh_lidarr"
        message = (
            f"{file_count} fichiers → MB + Servarr OK ({_format_release_short(target_srv or target_mb)}). "
            "Refresh artiste Lidarr et sélectionne cette édition (Edit → Releases)."
        )
    elif not monitored:
        recommended_action = "select_release"
        message = (
            f"{file_count} fichiers — édition(s) à {file_count} pistes dans Lidarr "
            f"({', '.join(_format_release_short(r) for r in lidarr_matches[:2])}) "
            "mais aucune n’est surveillée : cocher Monitored sur la bonne release."
        )
    else:
        recommended_action = "import_ready"
        message = (
            f"{file_count} fichiers — édition surveillée à {file_count} pistes "
            f"({_format_release_short(monitored[0])}). Import depuis la queue ou import interactif."
        )

    return {
        "recommended_action": recommended_action,
        "message": message,
        "proposed_seed_yaml": proposed_seed_yaml,
        "file_based": True,
        "file_track_count": file_count,
        "file_scan_path": file_scan.get("scan_path"),
        "file_queue": file_scan.get("queue"),
        "target_track_count": file_count,
        "musicbrainz_releases_matching_files": mb_matches,
        "servarr_releases_matching_files": srv_matches,
        "lidarr_releases_matching_files": lidarr_matches,
        "matched_musicbrainz_release": target_mb,
        "matched_servarr_release": target_srv,
        "matched_lidarr_release": monitored[0] if monitored else _pick_preferred_release(lidarr_matches),
    }


def _parse_event_date(date_str: str | None) -> tuple[int | None, int | None, int | None]:
    if not date_str:
        return None, None, None
    parts = date_str.split("-")
    y = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else None
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    d = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    return y, m, d


def suggest_album(
    release_group_mbid: str,
    *,
    scan_path: str | None = None,
    use_queue: bool = False,
) -> dict[str, Any]:
    status = album_status(release_group_mbid)
    file_scan = resolve_album_file_scan(
        release_group_mbid,
        scan_path=scan_path,
        use_queue=use_queue,
    )
    mb_releases, mb_group = get_release_group_bundle(release_group_mbid)
    enriched = _enrich_releases(mb_releases)
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

    servarr = status.get("servarr_metadata") or {}
    servarr_max = int(servarr.get("max_track_count") or 0)
    missing_on_servarr = status.get("servarr_vs_musicbrainz", {}).get(
        "missing_on_servarr"
    ) or []
    servarr_has_richest = richest_count > 0 and servarr_max >= richest_count

    recommended_action = "none"
    message = "Rien à faire de particulier."
    proposed_seed_yaml: dict[str, Any] | None = None
    file_based: dict[str, Any] | None = None

    file_count = int(file_scan.get("file_track_count") or 0)
    if file_count > 0:
        file_based = _suggest_from_files(
            release_group_mbid,
            file_count,
            file_scan,
            enriched,
            status,
            servarr,
            lidarr_releases,
        )
        if file_based:
            recommended_action = file_based["recommended_action"]
            message = file_based["message"]
            proposed_seed_yaml = file_based.get("proposed_seed_yaml")

    elif file_scan.get("error") and (use_queue or scan_path):
        recommended_action = "fix_file_scan"
        message = f"Impossible de lire les fichiers : {file_scan['error']}"

    if file_based:
        pass  # ne pas écraser la recommandation basée fichiers
    elif richest_count == 0:
        recommended_action = "fix_musicbrainz"
        message = "Tracklists manquantes ou incomplètes sur MusicBrainz."
    elif missing_on_servarr and servarr.get("available"):
        recommended_action = "refresh_servarr_cache"
        names = ", ".join(
            f"{r.get('disambiguation') or r.get('id', '')[:8]} ({r.get('track_count')} p.)"
            for r in missing_on_servarr[:3]
        )
        message = (
            f"MusicBrainz a {len(missing_on_servarr)} release(s) absente(s) du cache Servarr "
            f"(ex. {names}). Discord Servarr : !refresh album/{release_group_mbid} "
            "(Donatarr), puis refresh artiste Lidarr."
        )
    elif status.get("lidarr_configured") and not lidarr_releases:
        recommended_action = "refresh_lidarr"
        if status.get("lidarr_in_library"):
            message = (
                "Album présent dans Lidarr mais éditions non lues — refresh artiste, "
                "ou vérifier LIDARR_URL (http://lidarr:8686 depuis Docker)."
            )
        else:
            best = next(
                (r for r in enriched if (r.get("disambiguation") or "").lower().find("expand") >= 0),
                None,
            ) or next((r for r in enriched if (r.get("track_count") or 0) >= 17), None)
            if best:
                message = (
                    f"MusicBrainz a déjà « {best.get('disambiguation') or best.get('title')} » "
                    f"({best.get('track_count')} pistes, {best['id']}). "
                    "Refresh artiste Lidarr, choisir cette édition, puis import — pas de seed MB. "
                    "Si la bibliothèque n’apparaît pas ici : LIDARR_URL + album ajouté dans Lidarr."
                )
            else:
                message = (
                    "Aucune édition Lidarr visible — album absent de la bibliothèque ou "
                    "LIDARR_URL incorrect (127.0.0.1 ne marche pas depuis le conteneur)."
                )
    elif servarr.get("available") and not servarr_has_richest and richest_count > 0:
        recommended_action = "refresh_servarr_cache"
        message = (
            f"Cache Servarr : max {servarr_max} pistes vs {richest_count} sur MusicBrainz. "
            f"!refresh album/{release_group_mbid} si ça persiste après quelques heures."
        )
    elif status.get("lidarr_configured") and not lidarr_has_richest:
        recommended_action = "refresh_lidarr"
        message = (
            f"MusicBrainz : édition max {richest_count} pistes "
            f"({richest.get('disambiguation') or 'standard'}, {richest.get('date') or '?'}). "
            f"Lidarr local : max {lidarr_max} pistes. "
            "Refresh artiste — pas besoin d’un nouvel edit MusicBrainz si Servarr est à jour."
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
    if not file_based and source and richest_count > source_count:
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

    payload: dict[str, Any] = {
        "release_group_mbid": release_group_mbid,
        "musicbrainz_releases": enriched,
        "richest_musicbrainz": richest,
        "standard_source_musicbrainz": source,
        "lidarr_max_track_count": lidarr_max,
        "lidarr_has_richest_edition": lidarr_has_richest,
        "servarr_max_track_count": servarr_max,
        "servarr_has_richest_edition": servarr_has_richest,
        "servarr_metadata": servarr,
        "servarr_vs_musicbrainz": status.get("servarr_vs_musicbrainz"),
        "releases_missing_on_servarr": missing_on_servarr,
        "recommended_action": recommended_action,
        "message": message,
        "proposed_seed_yaml": proposed_seed_yaml,
        "lidarr_releases": lidarr_releases,
        "lidarr_configured": status.get("lidarr_configured"),
        "lidarr_in_library": status.get("lidarr_in_library"),
        "lidarr_album_title": status.get("lidarr_album_title"),
        "lidarr_error": status.get("lidarr_error"),
        "file_scan": file_scan if file_scan else None,
    }
    if file_based:
        payload.update({k: v for k, v in file_based.items() if k not in payload})

    matched_mb = (file_based or {}).get("matched_musicbrainz_release")
    mb_release_artist = ""
    creation_mbid = (matched_mb or {}).get("id") or (richest or {}).get("id")
    mb_creation: dict[str, Any] | None = None
    if creation_mbid:
        try:
            mb_creation = release_creation_info(creation_mbid)
        except Exception as exc:
            mb_creation = {"editor": None, "editor_is_me": None, "error": str(exc)}
    if matched_mb and matched_mb.get("id"):
        try:
            mb_release_artist = get_release_artist_credit(matched_mb["id"])
        except Exception:
            mb_release_artist = ""

    payload["musicbrainz_release_group"] = mb_group
    payload["musicbrainz_release_creation"] = mb_creation
    payload["analysis_display"] = build_analysis_display(
        file_scan=file_scan or {},
        file_based=file_based,
        mb_group=mb_group,
        status=status,
        richest=richest,
        servarr=servarr,
        matched_mb_artist_credit=mb_release_artist,
        mb_creation=mb_creation,
    )
    return payload
