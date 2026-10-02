"""Run one album seed job."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from lidarr_musicbrainz.html_seed import write_seed_html
from lidarr_musicbrainz.mb_api import get_release
from lidarr_musicbrainz.seed import ReleaseSeed, build_seed_fields, tracks_from_release
from lidarr_musicbrainz.session_submit import (
    MusicBrainzAuthError,
    credentials_from_env,
    login_session,
    post_seed,
)

DEFAULT_ACTION = "https://musicbrainz.org/release/add"


@dataclass
class SeedJobResult:
    job_id: str
    html_path: str
    field_count: int
    submit_url: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_seed_job(
    seed: ReleaseSeed,
    output_dir: Path,
    *,
    submit: bool = False,
    job_id: str | None = None,
) -> SeedJobResult:
    if not seed.source_release_mbid:
        raise ValueError("source_release_mbid is required")

    job_id = job_id or uuid.uuid4().hex[:12]
    job_dir = output_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    html_path = job_dir / "mb-seed.html"

    release = get_release(seed.source_release_mbid)
    source_tracks = tracks_from_release(release)
    fields = build_seed_fields(seed, source_tracks)
    write_seed_html(html_path, fields, DEFAULT_ACTION)

    # Lien pratique vers la dernière génération
    latest = output_dir / "mb-seed.html"
    latest.write_bytes(html_path.read_bytes())

    submit_url: str | None = None
    error: str | None = None
    if submit:
        try:
            user, password = credentials_from_env()
            session = login_session(user, password)
            response = post_seed(session, fields)
            submit_url = response.url
        except MusicBrainzAuthError as exc:
            error = str(exc)

    return SeedJobResult(
        job_id=job_id,
        html_path=str(html_path),
        field_count=len(fields),
        submit_url=submit_url,
        error=error,
    )
