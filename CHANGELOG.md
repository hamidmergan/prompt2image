# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-23

### Added

- `generate`: a picture from a prompt, with style, aspect ratio, size, quality and up to four variants
- `edit`: a picture changed by an instruction, keeping the aspect ratio of the source by default
- `describe`: a picture read by a vision model, as a description, a text transcription or an answer to a question
- `enhance`: a short idea expanded into a detailed prompt by a chat model
- Command line `prompt2image generate`, `edit` and `describe`
- Settings per task from arguments, flags or environment variables, with a fallback to the main values
