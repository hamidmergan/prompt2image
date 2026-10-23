"""The three tasks over an OpenAI-compatible server: create, edit and read a picture.

Create and edit post to `/images/generations` and `/images/edits`, reading posts a chat
request with the picture attached, so it needs a vision model.
"""

from __future__ import annotations

import base64
import contextlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from . import options
from .config import (CHAT, DESCRIBE_MAX_TOKENS, EDIT, IMAGE, PLACEHOLDER_API_KEY, VISION, Endpoint,
                     endpoint, max_image_mb)
from .errors import ModelError, OptionError
from .prompts import DEFAULT_QUESTION, ENHANCE_INSTRUCTION, GENERAL_INSTRUCTION, LANGUAGES
from .validation import check, dimensions

# Some servers pick their edit model only by this header, the others ignore it.
INFERENCE_SERVICE_HEADER = "inference-service"

Source = Union[str, Path, bytes]


# -- Transport ----------------------------------------------------------------

def make_client(point: Endpoint, *, extra_headers: Optional[Dict[str, str]] = None):
    """An HTTP client for one endpoint, with the key as a header where there is one."""
    import httpx

    headers: Dict[str, str] = {}
    if point.api_key and point.api_key != PLACEHOLDER_API_KEY:
        headers["Authorization"] = f"Bearer {point.api_key}"
    if extra_headers:
        headers.update(extra_headers)
    return httpx.Client(headers=headers, timeout=point.timeout)


def api_base(point: Endpoint) -> str:
    """The address of the API, with the /v1 part a person may leave out."""
    base = point.base_url.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def _transport(point: Endpoint, client, extra_headers: Optional[Dict[str, str]] = None):
    """Address, model and the client to use, a given one stays open for the next call."""
    if client is not None:
        return api_base(point), point.model, contextlib.nullcontext(client)
    return api_base(point), point.model, make_client(point, extra_headers=extra_headers)


def _payload(response) -> Any:
    try:
        return response.json()
    except Exception as e:  # noqa: BLE001 - a server may answer with anything
        raise ModelError(f"Unexpected answer format: {response.text[:300]}") from e


def _image_bytes(response) -> bytes:
    """The picture out of an answer, either as raw bytes or out of one of the usual base64 fields."""
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("image/"):
        return response.content
    data = _payload(response)
    first = (data.get("data") or [{}])[0] if isinstance(data, dict) else {}
    b64 = (
        first.get("b64_json")
        or first.get("b64")
        or (data.get("b64_json") if isinstance(data, dict) else None)
        or (data.get("b64") if isinstance(data, dict) else None)
    )
    if not b64:
        keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
        raise ModelError(f"Unexpected answer format (keys: {keys}): {str(data)[:300]}")
    return base64.b64decode(b64)


def _read(source: Source, name: str, max_mb: Optional[float]) -> Tuple[bytes, str, str, str]:
    """Content, file name, extension and media type of an input picture."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        content, name = path.read_bytes(), name or path.name
    else:
        content, name = bytes(source), name or "image.png"
    ext, media_type = check(content, name, max_image_mb(max_mb))
    return content, name, ext, media_type


# -- Create -------------------------------------------------------------------

def generate(
    prompt: str,
    *,
    style: str = "none",
    format_: str = "1:1",
    size: str = "medium",
    quality: str = "standard",
    n: int = 1,
    no_text: bool = True,
    model_prompt: str = "",
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
    client=None,
) -> List[bytes]:
    """One or more pictures for a prompt, as PNG bytes.

    `model_prompt` replaces the short prompt on its way to the model, for example an expanded one.
    """
    pixels = options.pixels(format_, size)
    quality_steps = options.steps(quality)
    text = options.image_prompt(model_prompt.strip() or prompt, style, no_text=no_text)
    count = options.variants(n, "generate")
    point = endpoint(IMAGE, base_url=base_url, model=model, api_key=api_key, timeout=timeout)
    return [_one_image(text, pixels, quality_steps, point, client) for _ in range(count)]


def _one_image(prompt: str, size: str, steps: int, point: Endpoint, client=None) -> bytes:
    base_url, model_name, session = _transport(point, client)
    body: Dict[str, Any] = {
        "model": model_name,
        "prompt": prompt,
        "size": size,
        "n": 1,
        "response_format": "b64_json",
    }
    if steps:
        body["num_inference_steps"] = steps

    with session as http:
        response = http.post(f"{base_url}/images/generations", json=body)
        # A server with a size limit (height up to 1080) gets the same picture shrunk into full HD.
        if response.status_code in (400, 422) and options.smaller(size) != size:
            body = {**body, "size": options.smaller(size)}
            response = http.post(f"{base_url}/images/generations", json=body)

    if response.status_code != 200:
        raise ModelError(f"The image could not be created: {response.text[:200]}")
    data = _payload(response)
    if not data.get("data"):
        raise ModelError("The server returned no image.")
    return base64.b64decode(data["data"][0]["b64_json"])


# -- Edit ---------------------------------------------------------------------

def edit(
    image: Source,
    prompt: str,
    *,
    format_: str = options.SOURCE_FORMAT,
    size: str = "medium",
    quality: str = "standard",
    n: int = 1,
    filename: str = "",
    max_mb: Optional[float] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
    client=None,
) -> List[bytes]:
    """The picture changed as the instruction says, as PNG bytes."""
    if not prompt.strip():
        raise OptionError("the instruction is empty")
    quality_steps = options.steps(quality, edit=True)
    count = options.variants(n, "edit")
    content, name, ext, media_type = _read(image, filename, max_mb)

    width, height = dimensions(content)
    # A very wide or tall source goes onto a 4:1 canvas, some servers refuse extreme ones.
    width, height, band = options.balance(width, height)
    if band:
        content, ext, media_type, name = options.pad(content, width, height), ".png", "image/png", f"{Path(name).stem}.png"
    if format_ == options.SOURCE_FORMAT:
        # The source keeps its aspect ratio, a portrait would be stretched to a square otherwise.
        pixels = options.like_source(width, height, size)
    else:
        # A fixed format is what the person asked for, nothing is cut back.
        pixels, band = options.pixels(format_, size), None

    point = endpoint(EDIT, base_url=base_url, model=model, api_key=api_key, timeout=timeout)
    return [_one_edit(content, name, media_type, prompt, pixels, quality_steps, band, point, client)
            for _ in range(count)]


def _one_edit(content: bytes, name: str, media_type: str, prompt: str, size: str, steps: int,
              band: Optional[dict], point: Endpoint, client=None) -> bytes:
    base_url, model_name, session = _transport(point, client, {INFERENCE_SERVICE_HEADER: point.model})
    with session as http:
        response = http.post(
            f"{base_url}/images/edits",
            files={"image": (name, content, media_type)},
            data={
                "model": model_name,
                "prompt": prompt,
                "response_format": "b64_json",
                "n": "1",
                "size": size,
                "quality": "standard",
                "guidance_scale": "3.5",
                "num_inference_steps": str(steps),
            },
        )
    if response.status_code != 200:
        raise ModelError(f"The image could not be edited (status {response.status_code}): {response.text[:300]}")
    result = _image_bytes(response)
    if band:
        # A padded panorama comes back as the band that was the source.
        result = options.crop(result, band)
    return result


def source_band(image: Source, *, filename: str = "", max_mb: Optional[float] = None) -> bytes:
    """The source of an edit as it is compared with the result, a padded panorama without its white band."""
    content, _name, _ext, _media_type = _read(image, filename, max_mb)
    width, height = dimensions(content)
    _w, _h, band = options.balance(width, height)
    return options.crop(content, band) if band else content


# -- Read ---------------------------------------------------------------------

def describe(
    image: Source,
    prompt: Optional[str] = None,
    *,
    task: str = "",
    language: str = "en",
    instruction: str = "",
    filename: str = "",
    max_tokens: int = DESCRIBE_MAX_TOKENS,
    max_mb: Optional[float] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
    client=None,
) -> str:
    """What a vision model reads out of the picture, as text.

    Without a task a prompt counts as a question, and no prompt means a description.
    """
    question = (prompt or "").strip()
    # Without a task only the text field decides, a question then, or a description without one.
    task = task or ("question" if question else "describe")
    text = instruction or options.read_instruction(task, language, question)
    content, _name, ext, media_type = _read(image, filename, max_mb)
    data_url = f"data:{media_type};base64,{base64.b64encode(content).decode('utf-8')}"

    point = endpoint(VISION, base_url=base_url, model=model, api_key=api_key, timeout=timeout)
    base_url_, model_name, session = _transport(point, client)
    with session as http:
        response = http.post(
            f"{base_url_}/chat/completions",
            json={
                "model": model_name,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
            },
        )
    if response.status_code != 200:
        raise ModelError(f"The image could not be read: {response.text[:200]}")
    data = _payload(response)
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise ModelError(f"Unexpected answer format: {str(data)[:300]}") from e


def general_instruction(language: str = "") -> str:
    """The reading instruction without a task, in a chosen answer language."""
    if not language:
        return GENERAL_INSTRUCTION
    name = LANGUAGES.get(language.strip().lower(), language.strip())
    return f"{GENERAL_INSTRUCTION}\n\nRespond in {name}.\n\n{DEFAULT_QUESTION}"


# -- Expand a prompt ----------------------------------------------------------

def enhance(
    text: str,
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
    client=None,
) -> str:
    """A short idea rewritten as a detailed prompt, with a chat model."""
    if not text.strip():
        raise OptionError("the prompt is empty")
    point = endpoint(CHAT, base_url=base_url, model=model, api_key=api_key, timeout=timeout)
    base_url_, model_name, session = _transport(point, client)
    with session as http:
        response = http.post(
            f"{base_url_}/chat/completions",
            json={
                "model": model_name,
                "temperature": 0.6,
                "max_tokens": 400,
                "messages": [
                    {"role": "system", "content": ENHANCE_INSTRUCTION},
                    {"role": "user", "content": text.strip()[:1000]},
                ],
            },
        )
    if response.status_code != 200:
        raise ModelError(f"The prompt could not be expanded: {response.text[:200]}")
    data = _payload(response)
    try:
        answer = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise ModelError(f"Unexpected answer format: {str(data)[:300]}") from e
    # The model likes to wrap its answer in quotes.
    result = answer.strip().strip('"').strip()
    if not result:
        raise ModelError("The prompt could not be expanded.")
    return result
