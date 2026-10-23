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
- [x] 1 Core: generate, edit, describe; `config.py`, `errors.py`, prompts in English
- [x] 2 API + CLI: `generate`, `edit`, `describe`
- [x] 3 Tests with fake server, CLI, missing configuration, size check
- [x] 4 README, CHANGELOG 0.1.0, local smoke test
- [x] 5 English sweep, acceptance greps
- [x] 6 Web UI (`prompt2image serve`) and Docker

## Open

- None
