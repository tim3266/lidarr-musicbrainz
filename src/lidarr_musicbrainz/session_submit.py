"""Optional: POST seed with MusicBrainz credentials from the environment."""

from __future__ import annotations

import os
import re
from typing import Iterable

import requests

MB_LOGIN = "https://musicbrainz.org/login"
MB_RELEASE_ADD = "https://musicbrainz.org/release/add"
USER_AGENT = "lidarr-musicbrainz/0.1.0 (https://github.com/tim3266/lidarr-musicbrainz)"


class MusicBrainzAuthError(RuntimeError):
    pass


def _find_csrf(html_text: str) -> str | None:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html_text)
    if match:
        return match.group(1)
    match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html_text)
    if match:
        return match.group(1)
    return None


def login_session(username: str, password: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    login_page = session.get(MB_LOGIN, timeout=60)
    login_page.raise_for_status()
    csrf = _find_csrf(login_page.text)
    payload: dict[str, str] = {
        "username": username,
        "password": password,
    }
    if csrf:
        payload["csrf_token"] = csrf
    response = session.post(MB_LOGIN, data=payload, timeout=60, allow_redirects=True)
    response.raise_for_status()
    if "logout" not in response.text.lower() and "Log out" not in response.text:
        raise MusicBrainzAuthError(
            "Connexion MusicBrainz échouée (vérifie user/mot de passe ou 2FA)."
        )
    return session


def post_seed(session: requests.Session, fields: Iterable[tuple[str, str]]) -> requests.Response:
    data = dict(fields)
    response = session.post(
        MB_RELEASE_ADD,
        data=data,
        timeout=120,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response


def credentials_from_env() -> tuple[str, str]:
    user = os.environ.get("MUSICBRAINZ_USER") or os.environ.get("MB_USER")
    password = os.environ.get("MUSICBRAINZ_PASSWORD") or os.environ.get("MB_PASSWORD")
    if not user or not password:
        raise MusicBrainzAuthError(
            "Définis MUSICBRAINZ_USER et MUSICBRAINZ_PASSWORD (ou MB_USER / MB_PASSWORD)."
        )
    return user, password
