from pathlib import Path

import prompt2image

ROOT = Path(__file__).resolve().parents[1]


def test_version():
    assert prompt2image.__version__ == "0.1.0"


def test_a_result_carries_the_size_it_was_made_with():
    picture = prompt2image.Picture(b"bytes", "768x768")
    assert picture == b"bytes" and picture.size == "768x768"


def test_the_image_leaves_the_tests_and_the_hidden_folders_out():
    lines = {line.strip() for line in (ROOT / ".dockerignore").read_text().splitlines()}
    assert {"tests/", "private/", ".env", ".*/"} <= lines
