"""Small local API used by deterministic API and browser tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit


def _handler_factory() -> type[BaseHTTPRequestHandler]:
    users: list[dict[str, object]] = [
        {"id": 1, "name": "Anna Smith", "email": "anna@example.com"},
        {"id": 2, "name": "Brian Miller", "email": "brian@example.com"},
    ]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def _json(self, status: int, body: object) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _method_not_allowed(self) -> None:
            # Consume the rejected payload so closing the socket preserves the response.
            size = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(size)
            self.send_response(405)
            self.send_header("Allow", "GET, POST")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            body = json.dumps({"error": "Method not allowed"}).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _allowed_methods(self) -> None:
            self.send_response(204)
            self.send_header("Allow", "GET, POST, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            path = urlsplit(self.path).path
            if path == "/":
                html = (
                    b"<!doctype html><html><head><title>QA Python Lab</title></head>"
                    b"<body><main><h1>QA Python Lab</h1>"
                    b'<a href="/about">About the lab</a></main></body></html>'
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            elif path == "/about":
                html = b"<!doctype html><title>About</title><h1>About this lab</h1>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            elif path == "/api/health":
                self._json(200, {"status": "ok"})
            elif path == "/api/users":
                self._json(200, users)
            elif path.startswith("/api/users/") and path.removeprefix("/api/users/").isdigit():
                user_id = int(path.rsplit("/", 1)[1])
                user = next((item for item in users if item["id"] == user_id), None)
                if user:
                    self._json(200, user)
                else:
                    self._json(404, {"error": "User not found"})
            else:
                self._json(404, {"error": "Resource not found"})

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if urlsplit(self.path).path != "/api/users":
                self._json(404, {"error": "Resource not found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "Invalid JSON"})
                return
            if not isinstance(body, dict) or not all(
                isinstance(body.get(field), str) and body[field].strip()
                for field in ("name", "email")
            ):
                self._json(400, {"error": "name and email are required"})
                return
            normalized_email = body["email"].strip().lower()
            local_part, separator, domain = normalized_email.partition("@")
            if not separator or not local_part or not domain or "@" in domain:
                self._json(400, {"error": "valid email is required"})
                return
            if any(item["email"].strip().lower() == normalized_email for item in users):
                self._json(409, {"error": "email already exists"})
                return
            user = {
                "id": max(item["id"] for item in users) + 1,
                "name": body["name"].strip(),
                "email": normalized_email,
            }
            users.append(user)
            self._json(201, user)

        def do_PUT(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            self._method_not_allowed()

        def do_PATCH(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            self._method_not_allowed()

        def do_DELETE(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            self._method_not_allowed()

        def do_OPTIONS(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            if urlsplit(self.path).path == "/api/users":
                self._allowed_methods()
            else:
                self._json(404, {"error": "Resource not found"})

    return Handler


@contextmanager
def local_server() -> Iterator[str]:
    """Start a fresh server on an ephemeral loopback port and stop it afterward."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_factory())
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
