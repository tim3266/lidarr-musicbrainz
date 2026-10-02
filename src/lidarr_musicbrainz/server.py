"""HTTP server: album status and on-demand MusicBrainz seed jobs."""

from __future__ import annotations

import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from lidarr_musicbrainz.config_loader import load_yaml_config, seed_from_dict
from lidarr_musicbrainz.job import run_seed_job
from lidarr_musicbrainz.status import album_status
from lidarr_musicbrainz.reconcile import reconcile_album
from lidarr_musicbrainz.suggest import suggest_album

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def _write_body(handler: BaseHTTPRequestHandler, body: bytes) -> None:
    if handler.command != "HEAD":
        handler.wfile.write(body)


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    _write_body(handler, body)


def _unauthorized(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, 401, {"error": "Invalid or missing API key"})


def _check_api_key(handler: BaseHTTPRequestHandler) -> bool:
    required = os.environ.get("LIDARR_MB_API_KEY", "").strip()
    if not required:
        return True
    got = handler.headers.get("X-Api-Key", "")
    return got == required


def _plugin_demo_roots() -> list[Path]:
    roots: list[Path] = []
    for candidate in (
        Path("/app/plugin-demo"),
        Path(__file__).resolve().parents[2] / "plugin-demo",
    ):
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def _plugin_demo_file(relative: str) -> Path | None:
    rel = relative.lstrip("/").replace("\\", "/")
    if not rel or ".." in rel.split("/"):
        return None
    for root in _plugin_demo_roots():
        resolved_root = root.resolve()
        target = (resolved_root / rel).resolve()
        try:
            target.relative_to(resolved_root)
        except ValueError:
            continue
        if target.is_file():
            return target
    return None


class AlbumHandler(BaseHTTPRequestHandler):
    output_dir: Path = Path("/output")
    config_dir: Path = Path("/config")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            _json_response(self, 200, {"ok": True})
            return

        if path in ("/", "/app", "/app.html"):
            app_page = _plugin_demo_file("app.html")
            if app_page:
                self._serve_static_anywhere(app_page)
            else:
                _json_response(self, 404, {"error": "App page missing — rebuild image"})
            return

        if path.startswith("/plugin-demo/"):
            rel = path[len("/plugin-demo/") :]
            static = _plugin_demo_file(rel)
            if static:
                self._serve_static_anywhere(static)
            else:
                _json_response(self, 404, {"error": "Not found", "path": path})
            return

        if path == "/v1/configs":
            if not _check_api_key(self):
                _unauthorized(self)
                return
            configs = sorted(
                p.name for p in self.config_dir.glob("*.yaml") if p.is_file()
            )
            _json_response(
                self,
                200,
                {
                    "config_dir": str(self.config_dir),
                    "yaml_files": configs,
                    "hint": "POST /v1/album/seed with {\"config\": \"fichier.yaml\"}",
                },
            )
            return

        if path == "/mb-seed.html":
            self._serve_file(self.output_dir / "mb-seed.html")
            return
        if path.startswith("/output/"):
            rel = path[len("/output/") :]
            self._serve_file(self.output_dir / rel)
            return

        match = re.match(r"^/v1/album/([0-9a-f-]{36})/status$", path, re.I)
        if match:
            if not _check_api_key(self):
                _unauthorized(self)
                return
            try:
                _json_response(self, 200, album_status(match.group(1)))
            except Exception as exc:  # noqa: BLE001 — API boundary
                _json_response(self, 500, {"error": str(exc)})
            return

        match = re.match(r"^/v1/album/([0-9a-f-]{36})/suggest$", path, re.I)
        if match:
            if not _check_api_key(self):
                _unauthorized(self)
                return
            try:
                _json_response(self, 200, suggest_album(match.group(1)))
            except Exception as exc:  # noqa: BLE001
                _json_response(self, 500, {"error": str(exc)})
            return

        _json_response(self, 404, {"error": "Not found", "path": path})

    def do_POST(self) -> None:
        if not _check_api_key(self):
            _unauthorized(self)
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "Invalid JSON body"})
            return

        match = re.match(r"^/v1/album/([0-9a-f-]{36})/reconcile$", path, re.I)
        if match:
            try:
                payload = reconcile_album(
                    match.group(1),
                    scan_path=body.get("scan_path") or body.get("path"),
                    use_queue=bool(body.get("use_queue")),
                )
                _json_response(self, 200, payload)
            except Exception as exc:  # noqa: BLE001
                _json_response(self, 500, {"error": str(exc)})
            return

        if path != "/v1/album/seed":
            _json_response(self, 404, {"error": "Not found"})
            return

        try:
            seed = self._resolve_seed(body)
        except (ValueError, OSError) as exc:
            _json_response(self, 400, {"error": str(exc)})
            return

        submit = bool(body.get("submit", False))
        try:
            result = run_seed_job(
                seed,
                self.output_dir,
                submit=submit,
            )
        except Exception as exc:  # noqa: BLE001
            _json_response(self, 500, {"error": str(exc)})
            return

        port = os.environ.get("MB_SEED_SERVE_PORT", "8787")
        host_header = self.headers.get("Host", f"localhost:{port}")
        base = f"http://{host_header}"
        payload = result.to_dict()
        payload["html_url"] = f"{base}/output/{result.job_id}/mb-seed.html"
        payload["latest_html_url"] = f"{base}/mb-seed.html"
        _json_response(self, 200, payload)

    def _resolve_seed(self, body: dict[str, Any]):
        if "config" in body:
            name = str(body["config"])
            path = self.config_dir / name
            if not path.is_file():
                path = Path(name)
            if not path.is_file():
                raise ValueError(f"Config not found: {body['config']}")
            return load_yaml_config(path)

        if "release_group_mbid" in body and "source_release_mbid" in body:
            if not UUID_RE.match(str(body["release_group_mbid"])):
                raise ValueError("Invalid release_group_mbid")
            return seed_from_dict(body)

        if body.get("from_suggest") is True:
            rg = body.get("release_group_mbid")
            if not rg or not UUID_RE.match(str(rg)):
                raise ValueError("release_group_mbid required with from_suggest")
            suggestion = suggest_album(str(rg))
            proposed = suggestion.get("proposed_seed_yaml")
            if not proposed:
                raise ValueError(suggestion.get("message") or "No seed proposal for this album")
            return seed_from_dict(proposed)

        if body.get("from_reconcile") is True:
            rg = body.get("release_group_mbid")
            if not rg or not UUID_RE.match(str(rg)):
                raise ValueError("release_group_mbid required with from_reconcile")
            report = reconcile_album(
                str(rg),
                scan_path=body.get("scan_path") or body.get("path"),
                use_queue=bool(body.get("use_queue")),
            )
            proposed = report.get("proposed_seed_yaml")
            if not proposed:
                raise ValueError(report.get("message") or report.get("error") or "No seed from reconcile")
            return seed_from_dict(proposed)

        if isinstance(body.get("proposed_seed_yaml"), dict):
            return seed_from_dict(body["proposed_seed_yaml"])

        raise ValueError(
            "Provide 'config', a full seed object, or {'from_suggest': true, 'release_group_mbid': '...'}"
        )

    def _serve_static_anywhere(self, path: Path) -> None:
        resolved = path.resolve()
        if not resolved.is_file():
            _json_response(self, 404, {"error": "File not found"})
            return
        mime, _ = mimetypes.guess_type(str(resolved))
        data = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        _write_body(self, data)

    def _serve_file(self, path: Path) -> None:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.output_dir.resolve())
        except ValueError:
            _json_response(self, 403, {"error": "Forbidden"})
            return
        self._serve_static_anywhere(resolved)


def serve(host: str, port: int, output_dir: Path, config_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    class Handler(AlbumHandler):
        pass

    Handler.output_dir = output_dir
    Handler.config_dir = config_dir

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Listening on http://{host}:{port} (output={output_dir}, config={config_dir})")
    httpd.serve_forever()


def main() -> None:
    host = os.environ.get("MB_BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("MB_SEED_SERVE_PORT", "8787"))
    output_dir = Path(os.environ.get("MB_OUTPUT_DIR", "/output"))
    config_dir = Path(os.environ.get("MB_CONFIG_DIR", "/config"))
    serve(host, port, output_dir, config_dir)


if __name__ == "__main__":
    main()
