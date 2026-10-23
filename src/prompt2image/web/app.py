"""Web API for the image page: create, edit and read pictures in the browser.

Everything stays in memory. A result is shown on the page and can be downloaded from there.
Settings come from the environment, a field on the page can override them per call.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import options
from ..config import CHAT, EDIT, IMAGE, VISION, endpoint, max_image_mb
from ..core import describe, edit, enhance, generate, source_band
from ..errors import ImageToolError
from ..prompts import QUICK_EDITS

STATIC = Path(__file__).parent / "static"
KEPT_IMAGES = 60  # pictures held in memory, the oldest one goes first


def _hostname(host: str) -> str:
    if host.startswith("["):
        return host[1:host.find("]")].lower()
    return host.rsplit(":", 1)[0].lower() if host.count(":") == 1 else host.lower()


def _configured(kind: str) -> bool:
    """Whether the environment already names an address and a model for this task."""
    try:
        endpoint(kind)
        return True
    except ImageToolError:
        return False


def _overrides(base_url: str, model: str, api_key: str) -> Dict[str, Optional[str]]:
    """What the fields on the page say, empty fields leave the environment in charge."""
    return {
        "base_url": base_url.strip() or None,
        "model": model.strip() or None,
        "api_key": api_key.strip() or None,
    }


def create_app(allowed_hosts: Optional[Sequence[str]] = None) -> FastAPI:
    """The image page and its JSON API.

    `allowed_hosts` limits the Host header (against DNS rebinding);
    requests from another origin are always refused.
    """
    images: "OrderedDict[str, bytes]" = OrderedDict()
    lock = threading.Lock()

    app = FastAPI(title="prompt2image")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    hosts = {h.lower() for h in allowed_hosts} if allowed_hosts is not None else None

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = request.headers.get("host", "")
        if hosts is not None and _hostname(host) not in hosts:
            return PlainTextResponse("Unknown host", status_code=400)
        origin = request.headers.get("origin")
        own = {host.lower(), request.headers.get("x-forwarded-host", "").lower()}  # also behind a reverse proxy
        if origin is not None and urlsplit(origin).netloc.lower() not in own:
            return PlainTextResponse("Cross-origin requests are not allowed", status_code=403)
        return await call_next(request)

    def keep(data: bytes) -> str:
        image_id = uuid.uuid4().hex
        with lock:
            images[image_id] = data
            while len(images) > KEPT_IMAGES:
                images.popitem(last=False)
        return image_id

    def answer(pictures: List[bytes], **extra: Any) -> Dict[str, Any]:
        return {"images": [keep(data) for data in pictures], **extra}

    @app.exception_handler(ImageToolError)
    async def tool_error(_request: Request, exc: ImageToolError):
        return PlainTextResponse(str(exc), status_code=400)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", media_type="text/html")

    @app.get("/api/options")
    def read_options() -> Dict[str, Any]:
        """Everything the page needs to build its forms."""
        return {
            "formats": list(options.FORMATS),
            "source_format": options.SOURCE_FORMAT,
            "sizes": list(options.SIZES),
            "qualities": list(options.QUALITIES),
            "styles": list(options.STYLE_NAMES),
            "tasks": list(options.TASK_NAMES),
            "variants": options.MAX_VARIANTS,
            "pixels": {f: {s: options.pixels(f, s) for s in options.SIZES} for f in options.FORMATS},
            "quick_edits": QUICK_EDITS,
            "max_image_mb": max_image_mb(),
            "configured": {kind: _configured(kind) for kind in (IMAGE, EDIT, VISION, CHAT)},
        }

    @app.post("/api/enhance")
    def expand(
        prompt: str = Form(...),
        base_url: str = Form(""),
        model: str = Form(""),
        api_key: str = Form(""),
    ) -> Dict[str, str]:
        return {"prompt": enhance(prompt, **_overrides(base_url, model, api_key))}

    @app.post("/api/generate")
    def create(
        prompt: str = Form(...),
        model_prompt: str = Form(""),
        style: str = Form("none"),
        format_: str = Form("1:1", alias="format"),
        size: str = Form("medium"),
        quality: str = Form("standard"),
        variants: int = Form(1),
        no_text: bool = Form(True),
        base_url: str = Form(""),
        model: str = Form(""),
        api_key: str = Form(""),
    ) -> Dict[str, Any]:
        pictures = generate(prompt, style=style, format_=format_, size=size, quality=quality,
                            n=variants, no_text=no_text, model_prompt=model_prompt,
                            **_overrides(base_url, model, api_key))
        return answer(pictures, prompt=prompt,
                      model_prompt=options.image_prompt(model_prompt.strip() or prompt, style, no_text=no_text),
                      size=options.pixels(format_, size), style=style, format=format_, quality=quality)

    def _upload(image: UploadFile) -> tuple:
        if not image.filename:
            raise HTTPException(status_code=400, detail="The file has no name.")
        content = image.file.read()
        return content, image.filename

    @app.post("/api/edit")
    def change(
        image: UploadFile = File(...),
        prompt: str = Form(...),
        format_: str = Form(options.SOURCE_FORMAT, alias="format"),
        size: str = Form("medium"),
        quality: str = Form("standard"),
        variants: int = Form(1),
        base_url: str = Form(""),
        model: str = Form(""),
        api_key: str = Form(""),
    ) -> Dict[str, Any]:
        content, filename = _upload(image)
        pictures = edit(content, prompt, format_=format_, size=size, quality=quality, n=variants,
                        filename=filename, **_overrides(base_url, model, api_key))
        # The source stays with the result, so the page can show before and after.
        return answer(pictures, prompt=prompt, filename=filename, format=format_, quality=quality,
                      source=keep(source_band(content, filename=filename)))

    @app.post("/api/describe")
    def read(
        image: UploadFile = File(...),
        prompt: str = Form(""),
        task: str = Form(""),
        language: str = Form("en"),
        base_url: str = Form(""),
        model: str = Form(""),
        api_key: str = Form(""),
    ) -> Dict[str, Any]:
        content, filename = _upload(image)
        text = describe(content, prompt, task=task, language=language, filename=filename,
                        **_overrides(base_url, model, api_key))
        return {"text": text, "filename": filename, "task": task or ("question" if prompt.strip() else "describe"),
                "question": prompt.strip()}

    @app.get("/api/image/{image_id}")
    def picture(image_id: str) -> Response:
        with lock:
            data = images.get(image_id)
        if data is None:
            raise HTTPException(status_code=404, detail="This image is gone.")
        return Response(content=data, media_type="image/png",
                        headers={"Cache-Control": "private, max-age=3600"})

    return app
