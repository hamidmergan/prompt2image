"""The choices of the image tool: format and size as pixels, quality as steps, style and the reading tasks."""

from __future__ import annotations

import io
import math
from typing import Dict, Optional, Tuple

from .errors import OptionError
from .prompts import BASE_RULES, LANGUAGES, NO_TEXT, STYLES, TASKS

FORMATS: Tuple[str, ...] = ("1:1", "16:9", "4:3", "3:4", "9:16")
SIZES: Tuple[str, ...] = ("small", "medium", "large")
# An edit keeps the aspect ratio of its source unless a fixed format is asked for.
SOURCE_FORMAT = "source"

# Fixed pixels per format and size, all sides multiples of 16, about 0.6, 1 and 2 megapixels.
_PIXELS: Dict[str, Tuple[str, str, str]] = {
    "1:1": ("768x768", "1024x1024", "1440x1440"),
    "16:9": ("1024x576", "1344x768", "1920x1088"),
    "4:3": ("896x672", "1152x864", "1664x1248"),
    "3:4": ("672x896", "864x1152", "1248x1664"),
    "9:16": ("576x1024", "768x1344", "1088x1920"),
}
_AREA: Dict[str, float] = {"small": 0.59e6, "medium": 1.05e6, "large": 2.07e6}

# Steps for a diffusion model. A server with a distilled model maps them onto the few steps it needs.
_STEPS: Dict[str, int] = {"draft": 12, "standard": 28, "high": 50}
# Some servers crash on an edit without these numbers, so editing keeps its own scale.
_STEPS_EDIT: Dict[str, int] = {"draft": 15, "standard": 25, "high": 40}
QUALITIES: Tuple[str, ...] = tuple(_STEPS)

STYLE_NAMES: Tuple[str, ...] = tuple(STYLES)
TASK_NAMES: Tuple[str, ...] = tuple(TASKS)

# How many pictures one call may ask for.
MAX_VARIANTS: Dict[str, int] = {"generate": 4, "edit": 2}


def pixels(format_: str, size: str) -> str:
    """The pixels for a format and a size, OptionError for anything else."""
    if format_ not in _PIXELS or size not in SIZES:
        raise OptionError(f"unknown format {format_!r} or size {size!r}")
    return _PIXELS[format_][SIZES.index(size)]


def _to16(value: float) -> int:
    return max(256, int(value // 16) * 16)


def like_source(width: int, height: int, size: str) -> str:
    """The aspect ratio of the source image at the area of the chosen size, both sides multiples of 16."""
    if size not in SIZES or width <= 0 or height <= 0:
        raise OptionError(f"unknown size {size!r} or empty image")
    ratio = width / height
    h = math.sqrt(_AREA[size] / ratio)
    w = h * ratio
    # A panorama would get a side of several thousand pixels, servers refuse those.
    factor = min(1.0, 2048 / max(w, h))
    return f"{_to16(w * factor)}x{_to16(h * factor)}"


# Some servers refuse sources beyond 8:1, so anything beyond 4:1 goes onto a white ground
# and the band is cut out again afterwards.
_MAX_RATIO = 4


def balance(width: int, height: int) -> Tuple[int, int, Optional[dict]]:
    """The canvas a source goes onto and which central band of the result is the source again, None when it fits."""
    if width > _MAX_RATIO * height:
        new = math.ceil(width / _MAX_RATIO)
        return width, new, {"axis": "height", "share": round(height / new, 4)}
    if height > _MAX_RATIO * width:
        new = math.ceil(height / _MAX_RATIO)
        return new, height, {"axis": "width", "share": round(width / new, 4)}
    return width, height, None


def pad(content: bytes, width: int, height: int) -> bytes:
    """The source centred on a white canvas of the given size, as PNG."""
    from PIL import Image

    with Image.open(io.BytesIO(content)) as source:
        canvas = Image.new("RGB", (width, height), "white")
        canvas.paste(source.convert("RGB"), ((width - source.width) // 2, (height - source.height) // 2))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def crop(content: bytes, band: dict) -> bytes:
    """The central band of an edited padded picture, the part that was the source."""
    from PIL import Image

    with Image.open(io.BytesIO(content)) as image:
        w, h = image.size
        if band["axis"] == "height":
            side = round(h * band["share"])
            box = (0, (h - side) // 2, w, (h - side) // 2 + side)
        else:
            side = round(w * band["share"])
            box = ((w - side) // 2, 0, (w - side) // 2 + side, h)
        buffer = io.BytesIO()
        image.crop(box).save(buffer, format="PNG")
    return buffer.getvalue()


def smaller(size: str) -> str:
    """The same picture shrunk into full HD, for a server that refuses larger ones (height up to 1080)."""
    w, h = map(int, size.split("x"))
    factor = min(1.0, 1080 / h, 1920 / w)
    if factor >= 1.0:
        return size
    return f"{_to16(w * factor)}x{_to16(h * factor)}"


def steps(quality: str, *, edit: bool = False) -> int:
    """The number of steps for a quality level."""
    table = _STEPS_EDIT if edit else _STEPS
    if quality not in table:
        raise OptionError(f"unknown quality {quality!r}")
    return table[quality]


def variants(count: int, task: str) -> int:
    """How many pictures one call may ask for, OptionError beyond the limit."""
    limit = MAX_VARIANTS.get(task)
    if limit is None:
        raise OptionError(f"unknown task {task!r}")
    if not 1 <= count <= limit:
        raise OptionError(f"n must be between 1 and {limit} for {task}, but is {count}")
    return count


def image_prompt(description: str, style: str, *, no_text: bool) -> str:
    """What goes to the image model: the style first, then the subject, the no-lettering sentence last."""
    if style not in STYLES:
        raise OptionError(f"unknown style {style!r}")
    if not description.strip():
        raise OptionError("the prompt is empty")
    style_text = STYLES[style]
    parts = [f"{style_text} Subject: {description.strip()}" if style_text else description.strip()]
    if no_text:
        parts.append(NO_TEXT)
    return " ".join(parts)


# The longest an answer language may be. A name like "Brazilian Portuguese" stays well below.
_MAX_LANGUAGE = 30


def language_name(language: str) -> str:
    """The name of an answer language, OptionError for anything that is no language name.

    A code like "en" names its language, any other short plain name stands for itself,
    so a language the table does not know can still be asked for.
    """
    text = language.strip()
    if not text:
        raise OptionError("the answer language is missing")
    known = LANGUAGES.get(text.lower())
    if known:
        return known
    words = text.replace("-", " ").split()
    if len(text) > _MAX_LANGUAGE or not words or not all(word.isalpha() for word in words):
        raise OptionError(f"unknown answer language {language!r}")
    return text


def read_instruction(task: str, language: str, question: str) -> str:
    """The instruction for reading an image, in the chosen answer language."""
    if task not in TASKS:
        raise OptionError(f"unknown task {task!r}")
    name = language_name(language)
    if task == "question" and not question.strip():
        raise OptionError("a question task needs a question")
    parts = [BASE_RULES, TASKS[task], f"Respond in {name}."]
    if task == "question":
        parts.append(f"Question: {question.strip()}")
    return "\n\n".join(parts)
