"""Generate a local HTML form that POSTs to the MusicBrainz release editor."""

from __future__ import annotations

import html
from pathlib import Path


def write_seed_html(path: Path, fields: list[tuple[str, str]], action: str) -> None:
    inputs = "\n".join(
        f'    <input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}" />'
        for k, v in fields
    )
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>MusicBrainz release seed</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.3rem; }}
  </style>
</head>
<body>
  <h1>Préremplir une release MusicBrainz</h1>
  <p>Ouvre cette page <strong>après</strong> t&apos;être connecté sur
    <a href="https://musicbrainz.org/login">musicbrainz.org</a>.
    Clique sur le bouton pour envoyer le formulaire vers l&apos;éditeur.</p>
  <form id="seed" method="post" action="{html.escape(action)}">
{inputs}
    <p><button type="submit">Ouvrir l&apos;éditeur de release</button></p>
  </form>
  <p><small>Action: <code>{html.escape(action)}</code></small></p>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")
