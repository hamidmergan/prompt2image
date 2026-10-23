"""Command line for the three tasks: generate, edit and describe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, options
from .core import describe, edit, enhance, generate
from .errors import ImageToolError

PROG = "prompt2image"


def _model_arguments(p: argparse.ArgumentParser, model_help: str) -> None:
    p.add_argument("--base-url", help="URL of the OpenAI-compatible server, e.g. http://localhost:11434/v1")
    p.add_argument("--model", help=model_help)
    p.add_argument("--api-key", help="API key, if the server requires one")
    p.add_argument("--timeout", type=float, help="Seconds per request")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROG,
        description="Generate, edit and describe images with any OpenAI-compatible image and vision model.",
    )
    p.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="command")

    gen = sub.add_parser("generate", help="Create an image from a prompt")
    gen.add_argument("prompt", help="What the image should show")
    gen.add_argument("-o", "--output", default="image.png", help="Output file, default image.png")
    gen.add_argument("--style", choices=options.STYLE_NAMES, default="none", help="Style of the image")
    gen.add_argument("--format", dest="format_", choices=options.FORMATS, default="1:1", help="Aspect ratio")
    gen.add_argument("--size", choices=options.SIZES, default="medium", help="Image size")
    gen.add_argument("--quality", choices=options.QUALITIES, default="standard",
                     help="Higher quality takes longer")
    gen.add_argument("-n", type=int, default=1,
                     help=f"How many images, up to {options.MAX_VARIANTS['generate']}")
    gen.add_argument("--with-text", action="store_true",
                     help="Allow lettering in the image, image models often misspell words")
    gen.add_argument("--enhance", action="store_true",
                     help="Expand the prompt with a chat model before the image is created")
    _model_arguments(gen, "Name of the image model")

    ed = sub.add_parser("edit", help="Change an image as an instruction says")
    ed.add_argument("image", help="Input image, PNG or JPG")
    ed.add_argument("prompt", help="What should change")
    ed.add_argument("-o", "--output", help="Output file, default <name>-edited.png")
    ed.add_argument("--format", dest="format_", choices=(options.SOURCE_FORMAT,) + options.FORMATS,
                    default=options.SOURCE_FORMAT, help="Aspect ratio, by default the one of the source")
    ed.add_argument("--size", choices=options.SIZES, default="medium", help="Image size")
    ed.add_argument("--quality", choices=options.QUALITIES, default="standard",
                    help="Higher quality takes longer")
    ed.add_argument("-n", type=int, default=1, help=f"How many images, up to {options.MAX_VARIANTS['edit']}")
    ed.add_argument("--max-mb", type=float, help="Largest input image in MB")
    _model_arguments(ed, "Name of the image editing model")

    desc = sub.add_parser("describe", help="Read an image with a vision model")
    desc.add_argument("image", help="Input image, PNG or JPG")
    desc.add_argument("prompt", nargs="?", default="", help="Your question about the image")
    desc.add_argument("-o", "--output", help="Write the answer to this file instead of printing it")
    desc.add_argument("--task", choices=options.TASK_NAMES, default="",
                      help="describe, text or question, by default question when you ask one")
    desc.add_argument("--language", default="en", help="Answer language, a code like en or de or a name")
    desc.add_argument("--max-tokens", type=int, help="Longest answer")
    desc.add_argument("--max-mb", type=float, help="Largest input image in MB")
    _model_arguments(desc, "Name of the vision model")

    serve = sub.add_parser("serve", help="Start the web page")
    serve.add_argument("--host", default="127.0.0.1", help="Host to listen on, default 127.0.0.1")
    serve.add_argument("--port", type=int, default=8000, help="Port, default 8000")
    serve.add_argument("--allowed-hosts", default="",
                       help="Comma separated host names the page answers for, * for any")
    return p


def _numbered(path: Path, index: int, total: int) -> Path:
    """The output file of one variant, several get a number."""
    if total == 1:
        return path
    return path.with_name(f"{path.stem}-{index + 1}{path.suffix or '.png'}")


def _write(images: List[bytes], output: Path) -> int:
    for index, data in enumerate(images):
        target = _numbered(output, index, len(images))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"Wrote {target}", file=sys.stderr)
    return 0


def _run_generate(args: argparse.Namespace) -> int:
    prompt = args.prompt
    model_prompt = ""
    if args.enhance:
        # The chat model has its own settings, with the image values as a fallback.
        model_prompt = enhance(prompt, timeout=args.timeout)
        print(model_prompt, file=sys.stderr)
    images = generate(
        prompt,
        style=args.style,
        format_=args.format_,
        size=args.size,
        quality=args.quality,
        n=args.n,
        no_text=not args.with_text,
        model_prompt=model_prompt,
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    return _write(images, Path(args.output))


def _run_edit(args: argparse.Namespace) -> int:
    source = Path(args.image)
    output = Path(args.output) if args.output else source.with_name(f"{source.stem}-edited.png")
    images = edit(
        source,
        args.prompt,
        format_=args.format_,
        size=args.size,
        quality=args.quality,
        n=args.n,
        max_mb=args.max_mb,
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    return _write(images, output)


def _run_describe(args: argparse.Namespace) -> int:
    extra = {"max_tokens": args.max_tokens} if args.max_tokens else {}
    text = describe(
        Path(args.image),
        args.prompt,
        task=args.task,
        language=args.language,
        max_mb=args.max_mb,
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        timeout=args.timeout,
        **extra,
    )
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {target}", file=sys.stderr)
    else:
        print(text)
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("The web page needs the extra [ui]: pip install 'prompt2image[ui]'", file=sys.stderr)
        return 2
    from .web.app import create_app

    hosts: Optional[List[str]] = None
    if args.allowed_hosts.strip() == "*":
        hosts = None
    elif args.allowed_hosts.strip():
        hosts = [h.strip() for h in args.allowed_hosts.split(",") if h.strip()]
    else:
        hosts = ["localhost", "127.0.0.1", "::1", f"{args.host}:{args.port}".rsplit(":", 1)[0]]
    print(f"The page is at http://{args.host}:{args.port}", file=sys.stderr)
    uvicorn.run(create_app(allowed_hosts=hosts), host=args.host, port=args.port, log_level="warning")
    return 0


_COMMANDS = {
    "generate": _run_generate,
    "edit": _run_edit,
    "describe": _run_describe,
    "serve": _run_serve,
}


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except ImageToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
