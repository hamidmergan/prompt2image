from pathlib import Path

import prompt2image

ROOT = Path(__file__).resolve().parents[1]


def test_version():
    assert prompt2image.__version__ == "0.1.0"


def test_the_image_leaves_the_tests_and_the_hidden_folders_out():
    lines = {line.strip() for line in (ROOT / ".dockerignore").read_text().splitlines()}
    assert {"tests/", "private/", ".env", ".*/"} <= lines
