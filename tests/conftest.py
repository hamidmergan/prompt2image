"""A fake OpenAI-compatible server for the three image routes, so no real model is needed."""

import base64
import io
import json
import threading
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


def png(width: int = 4, height: int = 4, color: str = "white") -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, "PNG")
    return buffer.getvalue()


def jpg(width: int = 4, height: int = 4) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, "JPEG")
    return buffer.getvalue()


def _form(body: bytes, content_type: str) -> dict:
    """The fields of a multipart body, files as bytes and their file name."""
    message = BytesParser(policy=HTTP).parsebytes(b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body)
    fields = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        fields[name] = {"filename": filename, "content": payload} if filename else payload.decode("utf-8")
    return fields


class FakeServer:
    """Answers the three routes, records every call and can be told to fail."""

    def __init__(self):
        self.requests = []
        self.status = 200  # the status of the next answer, 200 for a normal one
        self.statuses = []  # a queue of statuses, for the size fallback
        self.answer = "A white square."
        self.image = png()
        self.raw_image = False  # answer with image bytes instead of base64
        self.raw_type = "image/png"  # the content type of a raw image answer
        self.error = "something went wrong"  # the message inside a failing answer
        # How the picture is packed into a JSON answer: b64_json, b64, top_b64_json, top_b64,
        # url (a link instead of the data) or empty (no picture at all).
        self.spelling = "b64_json"
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, body, content_type="application/json"):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                content_type = self.headers.get("Content-Type", "")
                if content_type.startswith("multipart/"):
                    body = _form(raw, content_type)
                else:
                    body = json.loads(raw or b"{}")
                outer.requests.append({
                    "path": self.path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body,
                })
                status = outer.statuses.pop(0) if outer.statuses else outer.status
                if status != 200:
                    self._send(status, json.dumps({"error": {"message": outer.error}}).encode())
                    return
                if self.path.endswith("/chat/completions"):
                    self._send(200, json.dumps({
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": outer.answer}}],
                    }).encode())
                    return
                if outer.raw_image:
                    self._send(200, outer.image, outer.raw_type)
                    return
                self._send(200, json.dumps(outer.packed()).encode())

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def packed(self) -> dict:
        """The picture in the spelling this server was told to answer with."""
        data = base64.b64encode(self.image).decode()
        return {
            "b64_json": {"data": [{"b64_json": data}]},
            "b64": {"data": [{"b64": data}]},
            "top_b64_json": {"b64_json": data},
            "top_b64": {"b64": data},
            "url": {"data": [{"url": "http://127.0.0.1:1/picture.png"}]},
            "empty": {"data": []},
        }[self.spelling]

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.httpd.server_port}/v1"

    def bodies(self, suffix):
        return [r["body"] for r in self.requests if r["path"].endswith(suffix)]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    s = FakeServer()
    yield s
    s.stop()


@pytest.fixture
def other_server():
    """A second server, for the test that an edit can go somewhere else."""
    s = FakeServer()
    yield s
    s.stop()


@pytest.fixture
def settings(server, monkeypatch):
    """Address and model in the environment, as a person would set them."""
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", server.base_url)
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    return server


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    import os

    for name in list(os.environ):
        if name.startswith("PROMPT2IMAGE_") or name == "OPENAI_API_KEY":
            monkeypatch.delenv(name)


@pytest.fixture
def closed_port():
    """An address nothing listens on, for the tests about a failing connection."""
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}/v1"


@pytest.fixture
def image_file(tmp_path):
    path = tmp_path / "picture.png"
    path.write_bytes(png())
    return path
