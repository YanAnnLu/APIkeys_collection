from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import socketserver
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from frontends.web.preview_api import (
    crawler_asset_cards,
    crawler_asset_detail,
    crawler_asset_payload_from_web_values,
    crawler_asset_plan_preview,
    web_preview_recent_events,
    web_preview_status,
)


STATIC_DIR = Path(__file__).resolve().parent / "static"


class WebPreviewHandler(BaseHTTPRequestHandler):
    server_version = "RRKALWebPreview/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/health":
                self.write_json(web_preview_runtime_status(self.server))
                return
            if path == "/api/crawler-assets":
                self.write_json(crawler_asset_cards())
                return
            if path == "/api/events/recent":
                query = parse_qs(parsed.query)
                limit = int(first_query_value(query, "limit") or "50")
                self.write_json(web_preview_recent_events(limit=limit))
                return
            if path.startswith("/api/crawler-assets/"):
                asset_id, suffix = self.parse_asset_route(path)
                if suffix == "":
                    self.write_json(crawler_asset_detail(asset_id))
                    return
                if suffix == "/bounds-form":
                    self.write_json(crawler_asset_detail(asset_id)["bound_form"])
                    return
            self.serve_static(path)
        except KeyError as exc:
            self.write_error(HTTPStatus.NOT_FOUND, str(exc))
        except ValueError as exc:
            self.write_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover - local preview guard
            self.write_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(exc).__name__}: {exc}")

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path.startswith("/api/crawler-assets/"):
                asset_id, suffix = self.parse_asset_route(path)
                if suffix == "/bounds-payload":
                    values = self.read_json_body()
                    self.write_json(crawler_asset_payload_from_web_values(asset_id, values).to_dict())
                    return
                if suffix == "/plan-preview":
                    values = self.read_json_body()
                    query = parse_qs(parsed.query)
                    execute = first_query_value(query, "execute").lower() in {"1", "true", "yes", "on"}
                    self.write_json(crawler_asset_plan_preview(asset_id, values, execute=execute))
                    return
            self.write_error(HTTPStatus.NOT_FOUND, "unknown endpoint")
        except KeyError as exc:
            self.write_error(HTTPStatus.NOT_FOUND, str(exc))
        except ValueError as exc:
            self.write_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover - local preview guard
            self.write_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(exc).__name__}: {exc}")

    def parse_asset_route(self, path: str) -> tuple[str, str]:
        prefix = "/api/crawler-assets/"
        remainder = path[len(prefix) :]
        parts = remainder.split("/", 1)
        asset_id = unquote(parts[0])
        suffix = "" if len(parts) == 1 else "/" + parts[1]
        return asset_id, suffix

    def read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            path = "/index.html"
        relative = unquote(path.lstrip("/"))
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self.write_error(HTTPStatus.FORBIDDEN, "static path outside web root")
            return
        if not target.exists() or not target.is_file():
            self.write_error(HTTPStatus.NOT_FOUND, "static file not found")
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def write_json(self, payload: object, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def write_error(self, status: HTTPStatus, message: str) -> None:
        self.write_json({"error": message, "status": int(status)}, status=status)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[web-preview] " + format % args + "\n")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True
    requested_host: str
    requested_port: int
    port_scan: int


def build_web_preview_server(
    host: str,
    port: int,
    *,
    port_scan: int = 20,
) -> ReusableTCPServer:
    """Bind a preview server, scanning nearby ports when the preferred one is busy."""

    if port < 0 or port > 65535:
        raise ValueError("port must be between 0 and 65535")
    if port == 0:
        return _configured_server(host, port, port_scan, port)

    attempts = max(port_scan, 0) + 1
    last_error: OSError | None = None
    for candidate in range(port, min(65535, port + attempts - 1) + 1):
        try:
            return _configured_server(host, candidate, port_scan, port)
        except OSError as exc:
            last_error = exc
            if not port_is_unavailable(exc):
                raise
    message = f"no available port found from {port} to {min(65535, port + attempts - 1)}"
    if last_error is not None:
        raise OSError(message) from last_error
    raise OSError(message)


def _configured_server(host: str, bind_port: int, port_scan: int, requested_port: int) -> ReusableTCPServer:
    server = ReusableTCPServer((host, bind_port), WebPreviewHandler)
    # 前端/agent 需要知道實際綁定的 port；不要讓多個 Web Preview 並行時只顯示抽象狀態。
    server.requested_host = host
    server.requested_port = requested_port
    server.port_scan = max(port_scan, 0)
    return server


def web_preview_runtime_status(server: socketserver.TCPServer) -> dict[str, object]:
    payload = web_preview_status()
    actual_host, actual_port = server.server_address
    requested_port = int(getattr(server, "requested_port", actual_port))
    port_scan = int(getattr(server, "port_scan", 0))
    payload["server"] = {
        "host": str(actual_host),
        "port": int(actual_port),
        "url": f"http://{actual_host}:{actual_port}/",
        "requested_port": requested_port,
        "port_scan": port_scan,
        "port_scanned": requested_port not in {0, int(actual_port)},
    }
    return payload


def port_is_unavailable(exc: OSError) -> bool:
    return exc.errno in {
        getattr(socket, "EADDRINUSE", 10048),
        48,
        98,
        10013,
        10048,
    } or "address already in use" in str(exc).lower() or "10048" in str(exc) or "10013" in str(exc)


def first_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or [""]
    return values[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the RRKAL local Web Preview.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--port-scan", type=int, default=20, help="Try this many following ports when --port is busy.")
    parser.add_argument("--open", action="store_true", help="Open the preview in the default browser.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with build_web_preview_server(args.host, args.port, port_scan=args.port_scan) as httpd:
        actual_host, actual_port = httpd.server_address
        url = f"http://{actual_host}:{actual_port}/"
        if actual_port != args.port:
            print(f"Requested port {args.port} was unavailable; using {actual_port}.")
        print(f"RRKAL Web Preview ready: {url}")
        if args.open:
            webbrowser.open(url)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
