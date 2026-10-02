"""Read track list from audio files on disk."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

AUDIO_SUFFIXES = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".ape", ".wav", ".wma"}


def allowed_scan_roots() -> list[Path]:
    raw = os.environ.get(
        "MB_ALLOWED_SCAN_PATHS",
        "/downloads,/music,/data,/import,/mnt",
    )
    roots: list[Path] = []
    for part in raw.split(","):
        p = Path(part.strip()).expanduser()
        if part.strip():
            roots.append(p)
    return roots


def resolve_scan_path(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise ValueError(f"Chemin introuvable : {path}")
    if not target.is_dir():
        raise ValueError(f"Le chemin doit être un dossier : {path}")
    for root in allowed_scan_roots():
        try:
            root_res = root.resolve()
        except OSError:
            continue
        try:
            target.relative_to(root_res)
            return target
        except ValueError:
            continue
    roots = ", ".join(str(r) for r in allowed_scan_roots())
    raise ValueError(
        f"Dossier hors périmètre autorisé (MB_ALLOWED_SCAN_PATHS). Racines : {roots}"
    )


def _first_tag(audio: Any, *keys: str) -> str | None:
    for key in keys:
        if key in audio:
            val = audio.get(key)
            if val is None:
                continue
            if isinstance(val, (list, tuple)):
                val = val[0] if val else None
            if val is not None:
                text = str(val).strip()
                if text:
                    return text
    return None


def _parse_track_number(raw: str | None) -> int | None:
    if not raw:
        return None
    m = re.match(r"^(\d+)", str(raw).strip())
    return int(m.group(1)) if m else None


def _length_ms(audio: Any) -> int | None:
    info = getattr(audio, "info", None)
    if info is None:
        return None
    length = getattr(info, "length", None)
    if length is None:
        return None
    return int(float(length) * 1000)


def scan_directory(directory: Path) -> list[dict[str, Any]]:
    try:
        from mutagen import File as MutagenFile
    except ImportError as exc:
        raise RuntimeError("mutagen non installé") from exc

    files = [
        p
        for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES
    ]
    if not files:
        raise ValueError(f"Aucun fichier audio trouvé dans {directory}")

    rows: list[dict[str, Any]] = []
    for idx, path in enumerate(sorted(files)):
        audio = MutagenFile(path, easy=True)
        if audio is None:
            audio = MutagenFile(path)
        if audio is None:
            continue
        title = _first_tag(audio, "title") or path.stem
        track_no = _parse_track_number(
            _first_tag(audio, "tracknumber", "track")
        )
        rows.append(
            {
                "path": str(path),
                "title": title,
                "position": track_no if track_no is not None else idx + 1,
                "length_ms": _length_ms(audio),
            }
        )

    rows.sort(key=lambda r: (r["position"], r["title"].lower()))
    for i, row in enumerate(rows):
        if row["position"] is None or row["position"] <= 0:
            row["position"] = i + 1
    return rows
