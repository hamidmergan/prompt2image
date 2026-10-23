"""Default values and resolution of settings.

Order: argument, then environment variable, then default.
Each task has its own endpoint. Edit, vision and chat fall back to the main image values:
PROMPT2IMAGE_EDIT_MODEL, then PROMPT2IMAGE_MODEL, and so on.
"""

import os
from dataclasses import dataclass
from typing import Optional

from .errors import ConfigError

ENV_PREFIX = "PROMPT2IMAGE_"

# Placeholder, because the OpenAI library requires a value. Local servers ignore it.
PLACEHOLDER_API_KEY = "none"

# Endpoint kinds and the prefix of their own variables.
IMAGE, EDIT, VISION, CHAT = "image", "edit", "vision", "chat"
_KIND_PREFIX = {IMAGE: "", EDIT: "EDIT_", VISION: "VISION_", CHAT: "CHAT_"}
# The flags that feed a kind on the command line, so an error can name the right one.
_KIND_FLAG = {
    IMAGE: ("--base-url", "--model"),
    EDIT: ("--base-url", "--model"),
    VISION: ("--base-url", "--model"),
    CHAT: ("--chat-base-url", "--chat-model"),
}
_KIND_MODEL = {
    IMAGE: "an image generation model",
    EDIT: "an image editing model",
    VISION: "a vision model",
    CHAT: "a chat model",
}

# A large picture in high quality can take about a minute, 300 s leave room for a busy server.
# Describing and prompt writing answer faster.
TIMEOUT_SECONDS = {IMAGE: 300.0, EDIT: 300.0, VISION: 60.0, CHAT: 60.0}
MAX_RETRIES = 2

# Limits
MAX_IMAGE_MB = 20
DESCRIBE_MAX_TOKENS = 1500


@dataclass(frozen=True)
class Endpoint:
    kind: str
    base_url: str
    model: str
    api_key: str
    timeout: float
    max_retries: int


def _env(name: str) -> Optional[str]:
    value = os.environ.get(ENV_PREFIX + name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _cast(name: str, raw: str, cast):
    try:
        return cast(raw)
    except ValueError:
        raise ConfigError(f"Environment variable {ENV_PREFIX}{name} has an invalid value: {raw!r}")


def _kind_value(kind: str, name: str) -> Optional[str]:
    """The kind's own variable, then the main one."""
    own = _env(_KIND_PREFIX[kind] + name)
    return own if own is not None else _env(name)


def _kind_var(kind: str, name: str) -> str:
    own = ENV_PREFIX + _KIND_PREFIX[kind] + name
    main = ENV_PREFIX + name
    return own if own == main else f"{own} or {main}"


def _number(kind: str, name: str, arg, default, cast):
    if arg is not None:
        return arg
    for env_name in dict.fromkeys([_KIND_PREFIX[kind] + name, name]):
        raw = _env(env_name)
        if raw is not None:
            return _cast(env_name, raw, cast)
    return default


def endpoint(
    kind: str,
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> Endpoint:
    """Address, model and key for one kind of request."""
    if kind not in _KIND_PREFIX:
        raise ConfigError(f"Unknown endpoint kind {kind!r}.")
    base_url = base_url or _kind_value(kind, "BASE_URL")
    model = model or _kind_value(kind, "MODEL")
    url_flag, model_flag = _KIND_FLAG[kind]
    missing = []
    if not base_url:
        missing.append(f"base_url ({url_flag} or {_kind_var(kind, 'BASE_URL')})")
    if not model:
        missing.append(f"model ({model_flag} or {_kind_var(kind, 'MODEL')})")
    if missing:
        raise ConfigError(
            "Missing: " + " and ".join(missing) + ". "
            f"Example for Ollama: base_url http://localhost:11434/v1 and {_KIND_MODEL[kind]}."
        )

    key = api_key or _kind_value(kind, "API_KEY") or os.environ.get("OPENAI_API_KEY") or PLACEHOLDER_API_KEY

    result = Endpoint(
        kind=kind,
        base_url=base_url,
        model=model,
        api_key=key,
        timeout=_number(kind, "TIMEOUT", timeout, TIMEOUT_SECONDS[kind], float),
        max_retries=_number(kind, "MAX_RETRIES", max_retries, MAX_RETRIES, int),
    )
    if result.timeout <= 0:
        raise ConfigError(f"timeout must be greater than 0, but is {result.timeout}.")
    if result.max_retries < 0:
        raise ConfigError("max_retries must not be negative.")
    return result


def max_image_mb(value: Optional[float] = None) -> float:
    """Largest input image in MB."""
    if value is None:
        raw = _env("MAX_IMAGE_MB")
        value = MAX_IMAGE_MB if raw is None else _cast("MAX_IMAGE_MB", raw, float)
    if value <= 0:
        raise ConfigError(f"max_image_mb must be greater than 0, but is {value}.")
    return value
