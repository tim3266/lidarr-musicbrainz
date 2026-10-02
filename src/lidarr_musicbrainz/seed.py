"""Build MusicBrainz release-editor seed field maps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BonusTrack:
    position: int
    title: str
    recording_mbid: str | None = None
    length_ms: int | None = None
    number: str | None = None


@dataclass
class ReleaseSeed:
    name: str
    release_group_mbid: str
    artist_mbid: str
    artist_name: str = "Justin Bieber"
    disambiguation: str = ""
    status: str = "official"
    packaging: str = ""
    barcode: str = ""
    language: str = "eng"
    script: str = "Latn"
    medium_format: str = "CD"
    secondary_type: str = "Compilation"
    event_country: str = "US"
    event_year: int | None = None
    event_month: int | None = None
    event_day: int | None = None
    label_mbid: str = ""
    catalog_number: str = ""
    edit_note: str = ""
    discogs_url: str = ""
    source_release_mbid: str = ""
    bonus_tracks: list[BonusTrack] = field(default_factory=list)
    skip_source_tracks_after: int | None = None


def _flat_fields(data: dict[str, str]) -> list[tuple[str, str]]:
    return [(k, v) for k, v in data.items() if v is not None and v != ""]


def build_seed_fields(
    seed: ReleaseSeed,
    source_tracks: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    """Return (name, value) pairs for POST to /release/add."""

    fields: dict[str, str] = {
        "name": seed.name,
        "release_group": seed.release_group_mbid,
        "comment": seed.disambiguation,
        "status": seed.status,
        "language": seed.language,
        "script": seed.script,
        "barcode": seed.barcode or "none",
        "type": seed.secondary_type,
        "edit_note": seed.edit_note,
    }
    if seed.packaging:
        fields["packaging"] = seed.packaging

    fields["artist_credit.names.0.mbid"] = seed.artist_mbid
    fields["artist_credit.names.0.name"] = seed.artist_name

    if seed.event_year is not None:
        fields["events.0.date.year"] = str(seed.event_year)
    if seed.event_month is not None:
        fields["events.0.date.month"] = str(seed.event_month)
    if seed.event_day is not None:
        fields["events.0.date.day"] = str(seed.event_day)
    if seed.event_country:
        fields["events.0.country"] = seed.event_country

    if seed.label_mbid:
        fields["labels.0.mbid"] = seed.label_mbid
    if seed.catalog_number:
        fields["labels.0.catalog_number"] = seed.catalog_number

    if seed.discogs_url:
        fields["urls.0.url"] = seed.discogs_url
        fields["urls.0.link_type"] = "86"  # Discogs

    fields["mediums.0.format"] = seed.medium_format

    limit = seed.skip_source_tracks_after
    kept = source_tracks if limit is None else source_tracks[:limit]

    track_index = 0
    for src in kept:
        pos = src.get("position") or str(track_index + 1)
        title = src.get("title") or src.get("recording", {}).get("title") or ""
        rec = src.get("recording") or {}
        rec_id = rec.get("id")
        length = rec.get("length")

        prefix = f"mediums.0.track.{track_index}"
        fields[f"{prefix}.name"] = title
        fields[f"{prefix}.number"] = str(pos)
        if rec_id:
            fields[f"{prefix}.recording"] = rec_id
        if length:
            fields[f"{prefix}.length"] = str(length)
        track_index += 1

    for bonus in sorted(seed.bonus_tracks, key=lambda t: t.position):
        prefix = f"mediums.0.track.{track_index}"
        fields[f"{prefix}.name"] = bonus.title
        fields[f"{prefix}.number"] = str(bonus.number or bonus.position)
        if bonus.recording_mbid:
            fields[f"{prefix}.recording"] = bonus.recording_mbid
        if bonus.length_ms:
            fields[f"{prefix}.length"] = str(bonus.length_ms)
        track_index += 1

    return _flat_fields(fields)


def tracks_from_release(release: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for medium in release.get("medium-list") or release.get("media") or []:
        for track in medium.get("track-list") or medium.get("tracks") or []:
            out.append(track)
    return out
