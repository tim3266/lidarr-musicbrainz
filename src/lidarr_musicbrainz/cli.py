"""CLI: build MusicBrainz release editor seeds for Lidarr."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from lidarr_musicbrainz.html_seed import write_seed_html
from lidarr_musicbrainz.mb_api import get_release
from lidarr_musicbrainz.seed import BonusTrack, ReleaseSeed, build_seed_fields, tracks_from_release
from lidarr_musicbrainz.session_submit import (
    MusicBrainzAuthError,
    credentials_from_env,
    login_session,
    post_seed,
)

DEFAULT_ACTION = "https://musicbrainz.org/release/add"


def load_yaml_config(path: Path) -> ReleaseSeed:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
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
        artist_name=raw.get("artist_name", "Justin Bieber"),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed MusicBrainz release editor from an existing release + bonus tracks.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="YAML config (see examples/)",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("mb-seed.html"),
        help="Write auto-POST HTML form (recommended; no password)",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="POST via session using MUSICBRAINZ_USER / MUSICBRAINZ_PASSWORD",
    )
    parser.add_argument(
        "--print-url",
        action="store_true",
        help="Print release editor URL after --submit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.config:
        parser.error("--config is required")

    seed = load_yaml_config(args.config)
    if not seed.source_release_mbid:
        print("source_release_mbid is required in config", file=sys.stderr)
        return 2

    release = get_release(seed.source_release_mbid)
    source_tracks = tracks_from_release(release)
    fields = build_seed_fields(seed, source_tracks)

    write_seed_html(args.html, fields, DEFAULT_ACTION)
    print(f"HTML seed written: {args.html.resolve()}")
    print("1. Connecte-toi sur https://musicbrainz.org")
    print(f"2. Ouvre {args.html.resolve()} dans le navigateur et envoie le formulaire")
    print("3. Vérifie la tracklist, soumets l'edit, puis refresh l'artiste dans Lidarr")

    if args.submit:
        try:
            user, password = credentials_from_env()
            session = login_session(user, password)
            response = post_seed(session, fields)
        except MusicBrainzAuthError as exc:
            print(f"Erreur: {exc}", file=sys.stderr)
            return 1
        if args.print_url:
            print(response.url)
        else:
            print("Seed POST OK — termine la release dans l'éditeur si tu n'es pas redirigé.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
