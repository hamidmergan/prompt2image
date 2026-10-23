# PLAN

Three commands over OpenAI-compatible endpoints:
`generate` (text to image, `/images/generations`), `edit` (image plus instruction, `/images/edits`)
and `describe` (image to text with a vision model, chat with an image attachment).
Format, size, quality, style and count are configurable.

## Decisions

- Library first, thin CLI on top, web page with `prompt2image serve`
- No default for base_url and model, api_key optional (placeholder `none`)
- Each task has its own settings (image, edit, vision, chat) and falls back to the main ones
- Plain HTTP requests to `/images/generations`, `/images/edits` and `/chat/completions`,
  because the extra fields (`num_inference_steps`, `guidance_scale`) and the size fallback need them
- Results stay in memory on the server, the page fetches them by id and downloads them
- The page only answers requests for localhost, no login

## Checklist

- [x] 0 Scaffold: repo, LICENSE (MIT), pyproject, `src/prompt2image/`, `tests/`, CI, PLAN.md, README skeleton
- [x] 1 Core: generate, edit, describe, with `config.py`, `errors.py` and prompts in English
- [x] 2 API + CLI: `generate`, `edit`, `describe`
- [x] 3 Tests with fake server, CLI, missing configuration, size check
- [x] 4 README, CHANGELOG 0.1.0, local smoke test
- [x] 5 English sweep, acceptance greps
- [x] 6 Web UI (`prompt2image serve`) and Docker
- [x] 7 Review round: error handling, retries, answer shapes, page settings, docs

## Deliberate deviations from the source

- `generate` reads the picture out of every answer shape the tool knows, the same way `edit`
  does, instead of only out of `b64_json`. A link instead of the data is the documented default
  of the OpenAI image API, and a bare `KeyError` is never the right error for it. A link answer
  is now a `ModelError` that says what the endpoint has to support.
- Every request failure is a `ModelError`, including a refused connection and a timeout. A
  library has no job wrapper above it that could catch a stray exception.
- `max_retries` does what the setting says. A busy server (408, 409, 429 and the 5xx answers)
  and a failed connection are tried again, by default twice.
- The size fallback only fires when the server complained about the size. A strict endpoint
  answers 400 for other reasons as well, and repeating the call with a smaller size would only
  double the waiting time and hide the real message.
- An answer language can be any short plain name, not only the two codes in the table, because
  the tool is used everywhere. A value that is no language name, for example a whole sentence,
  is refused before it reaches the model.
- The page has a model field per task (creating, editing, describing, expanding a prompt),
  matching the four endpoint kinds the library supports.
- `--enhance` has its own `--chat-base-url`, `--chat-model` and `--chat-api-key`, because the
  expanded prompt comes from a chat model and not from the image model.

## Known properties

- The variant chips for creating offer 1, 2, 3 and 4. Three is an addition, the limit of 4 is
  the one of the library. Editing offers 1 and 2, its own limit.
- `client=` is public on all four functions. A passed client is used as it is and stays open,
  so its own headers apply and the address, the key, the timeout and the retries of the
  settings are bypassed. The README says so.

## Open

- None
