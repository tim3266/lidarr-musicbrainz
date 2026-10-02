"""Load ReleaseSeed from YAML file or dict."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lidarr_musicbrainz.seed import BonusTrack, ReleaseSeed


def seed_from_dict(raw: dict[str, Any]) -> ReleaseSeed:
    bonus = [
        BonusTrack(
            position=int(item["position"]),
            title=str(item["title"]),
            recording_mbid=item.get("recording_mbid"),
            length_ms=item.get("length_ms"),
            number=item.get("number"),
        )
        for item in raw.get("bonus_tracks") or []
    ]
    return ReleaseSeed(
        name=raw["name"],
        release_group_mbid=raw["release_group_mbid"],
        artist_mbid=raw["artist_mbid"],
        artist_name=raw.get("artist_name", ""),
        disambiguation=raw.get("disambiguation", ""),
        status=raw.get("status", "official"),
        packaging=raw.get("packaging", ""),
        barcode=raw.get("barcode", ""),
        language=raw.get("language", "eng"),
        script=raw.get("script", "Latn"),
        medium_format=raw.get("medium_format", "CD"),
        secondary_type=raw.get("secondary_type", "Compilation"),
        event_country=raw.get("event_country", "US"),
        event_year=raw.get("event_year"),
        event_month=raw.get("event_month"),
        event_day=raw.get("event_day"),
        label_mbid=raw.get("label_mbid", ""),
        catalog_number=raw.get("catalog_number", ""),
        edit_note=raw.get("edit_note", ""),
        discogs_url=raw.get("discogs_url", ""),
        source_release_mbid=raw.get("source_release_mbid", ""),
        bonus_tracks=bonus,
        skip_source_tracks_after=raw.get("skip_source_tracks_after"),
    )


def load_yaml_config(path: Path) -> ReleaseSeed:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid YAML config: {path}")
    return seed_from_dict(raw)
