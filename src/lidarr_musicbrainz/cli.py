"""CLI: build MusicBrainz release editor seeds for Lidarr."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lidarr_musicbrainz.config_loader import load_yaml_config
from lidarr_musicbrainz.job import run_seed_job


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
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "serve":
        from lidarr_musicbrainz.server import main as serve_main

        serve_main()
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.config:
        parser.error("--config is required (or run: mb-seed-release serve)")

    seed = load_yaml_config(args.config)
    result = run_seed_job(seed, args.html.parent, submit=args.submit)
    Path(args.html).write_bytes(Path(result.html_path).read_bytes())

    print(f"HTML seed written: {args.html.resolve()}")
    print("1. Connecte-toi sur https://musicbrainz.org")
    print(f"2. Ouvre {args.html.resolve()} dans le navigateur et envoie le formulaire")
    print("3. Vérifie la tracklist, soumets l'edit, puis refresh l'artiste dans Lidarr")

    if args.submit:
        if result.error:
            print(f"Erreur submit: {result.error}", file=sys.stderr)
            return 1
        if args.print_url and result.submit_url:
            print(result.submit_url)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
