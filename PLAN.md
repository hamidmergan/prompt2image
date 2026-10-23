# PLAN

Three commands over OpenAI-compatible endpoints:
`generate` (text to image, `/images/generations`), `edit` (image plus instruction, `/images/edits`)
and `describe` (image to text with a vision model, chat with an image attachment).
Format, size, quality, style and count are configurable.

## Decisions

- Library first, thin CLI on top, web page with `prompt2image serve`
- No default for base_url and model; api_key optional (placeholder `none`)

## Checklist

- [x] 0 Scaffold: repo, LICENSE (MIT), pyproject, `src/prompt2image/`, `tests/`, CI, PLAN.md, README skeleton
- [ ] 1 Core: generate, edit, describe; `config.py`, `errors.py`, prompts in English
- [ ] 2 API + CLI: `generate`, `edit`, `describe`
- [ ] 3 Tests with fake server, CLI, missing configuration, size check
- [ ] 4 README, CHANGELOG 0.1.0, local smoke test
- [ ] 5 English sweep, acceptance greps
- [ ] 6 Web UI (`prompt2image serve`) and Docker

## Open

- None yet
