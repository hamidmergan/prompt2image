# prompt2image

A lightweight Python utility to generate, edit and describe images with a model of your choice. It talks to any server with an OpenAI-compatible API.

prompt2image has three commands:

- `generate` sends a prompt to an image model and writes the picture
- `edit` sends a picture and an instruction and writes the changed picture
- `describe` sends a picture to a vision model and prints what it reads

## Prerequisites

- Python 3.9 or newer
- A server with an OpenAI-compatible API (for example Ollama, vLLM, LM Studio, a university server or a cloud provider)
- For `generate` and `edit`: an **image model** on `/images/generations` and `/images/edits`
- For `describe`: a **vision-capable model** on `/chat/completions`. A text-only model is not enough.
- An API key is optional. Many self-hosted servers do not need one.

The three tasks can live on different servers, each has its own settings.

If you run your own model, your pictures stay on your own network. Nothing leaves your machine or data center.

## Installation

```bash
pip install prompt2image
```

Alternatively, you can install it from the source:

```bash
git clone https://github.com/hamidmergan/prompt2image.git
cd prompt2image
pip install .
```

## Usage

### Command-Line

Create a picture:

```bash
prompt2image generate "a red bicycle" -o bike.png --base-url http://localhost:11434/v1 --model your-image-model
```

Pick a style, an aspect ratio, a size and a quality level:

```bash
prompt2image generate "a red bicycle" -o bike.png --style photo --format 16:9 --size large --quality high
```

Ask for several variants. Each one is a request of its own and the files are numbered `bike-1.png`, `bike-2.png`:

```bash
prompt2image generate "a red bicycle" -o bike.png -n 2
```

Let a chat model expand a short idea into a detailed prompt first. The expanded text is printed on stderr:

```bash
prompt2image generate "a red bicycle" -o bike.png --enhance
```

Change an existing picture:

```bash
prompt2image edit bike.png "make it blue" -o blue.png
```

Without `-o` the result is written next to the source as `bike-edited.png`. By default the result keeps the aspect ratio of the source. Use `--format` for a fixed one.

Read a picture:

```bash
prompt2image describe bike.png
prompt2image describe bike.png --task text
prompt2image describe bike.png "How many people are in the picture?" --language de
```

Without a task, a question of your own is answered and a call without one gives a description. The answer is printed, `-o answer.txt` writes it to a file instead.

Errors appear on stderr. The exit code is 2 if the call failed.

### Python API

```python
from prompt2image import generate, edit, describe

images = generate(
    "a red bicycle",
    style="photo",
    format_="16:9",
    size="large",
    base_url="http://localhost:11434/v1",
    model="your-image-model",
)
open("bike.png", "wb").write(images[0])

blue = edit("bike.png", "make it blue", base_url=..., model=...)
open("blue.png", "wb").write(blue[0])

text = describe("bike.png", base_url=..., model="your-vision-model")
print(text)
```

`generate` and `edit` return a list of PNG bytes, one entry per variant. `describe` returns the answer as text. `enhance("a red bicycle")` returns a detailed prompt from a chat model.

Every unknown option, every bad input picture and every failing server raises an error from `prompt2image.errors`: `ConfigError`, `OptionError`, `InputError` or `ModelError`. All four inherit from `ImageToolError`.

### Options

| Option | Values | Default |
| --- | --- | --- |
| `style` / `--style` | `none`, `photo`, `illustration`, `sketch`, `watercolor`, `3d`, `flat` | `none` |
| `format_` / `--format` | `1:1`, `16:9`, `4:3`, `3:4`, `9:16`, and `source` for `edit` | `1:1`, `source` for `edit` |
| `size` / `--size` | `small`, `medium`, `large` (about 0.6, 1 and 2 megapixels) | `medium` |
| `quality` / `--quality` | `draft`, `standard`, `high` (steps of the image model) | `standard` |
| `n` / `-n` | up to 4 for `generate`, up to 2 for `edit` | 1 |
| `no_text` / `--with-text` | leave lettering out of the picture, image models often misspell words | leave it out |
| `task` / `--task` | `describe`, `text`, `question` | from the question |
| `language` / `--language` | `en`, `de` or the name of a language | `en` |

Format and size give fixed pixels, for example `16:9` and `large` give `1920x1088`. All sides are multiples of 16. If a server refuses a size, the same picture is tried once more shrunk into full HD. A very wide or tall source for `edit` goes onto a 4:1 canvas first, because many servers refuse extreme ratios, and the result is cut back to the band that was the source.

### Settings

Order: argument, then environment variable, then default. Each task has its own variables and falls back to the main ones, so one server for everything needs only `PROMPT2IMAGE_BASE_URL` and `PROMPT2IMAGE_MODEL`.

| Argument / flag | Environment variable | Default |
| --- | --- | --- |
| `base_url` / `--base-url` | `PROMPT2IMAGE_BASE_URL` | none, required |
| `model` / `--model` | `PROMPT2IMAGE_MODEL` | none, required |
| `api_key` / `--api-key` | `PROMPT2IMAGE_API_KEY` (then `OPENAI_API_KEY`) | optional |
| `timeout` / `--timeout` | `PROMPT2IMAGE_TIMEOUT` | 300 seconds for images, 60 for text |
| `max_mb` / `--max-mb` | `PROMPT2IMAGE_MAX_IMAGE_MB` | 20 |

The editing model, the vision model and the chat model read their own variables first:

| Task | Variables |
| --- | --- |
| `generate` | `PROMPT2IMAGE_BASE_URL`, `PROMPT2IMAGE_MODEL`, `PROMPT2IMAGE_API_KEY` |
| `edit` | `PROMPT2IMAGE_EDIT_BASE_URL`, `PROMPT2IMAGE_EDIT_MODEL`, `PROMPT2IMAGE_EDIT_API_KEY` |
| `describe` | `PROMPT2IMAGE_VISION_BASE_URL`, `PROMPT2IMAGE_VISION_MODEL`, `PROMPT2IMAGE_VISION_API_KEY` |
| `--enhance` | `PROMPT2IMAGE_CHAT_BASE_URL`, `PROMPT2IMAGE_CHAT_MODEL`, `PROMPT2IMAGE_CHAT_API_KEY` |

If the address or the model is missing, the error names the flag and the variable to set.

## Limitations

Quality depends on the chosen model. Image models often misspell words, so lettering is asked to stay out of the picture by default. Not every server supports `/images/edits`, and the number of steps is passed as `num_inference_steps`, which some servers ignore. Input pictures are PNG or JPG, up to 20 MB. Results are always PNG.

## Running Tests

```bash
pip install -e ".[test]"
pytest
```

The tests run against a local fake server and need no real model.

## License

MIT
