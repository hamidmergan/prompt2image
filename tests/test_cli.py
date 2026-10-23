"""The command line against the fake server."""

import pytest
from PIL import Image

from prompt2image.cli import main

from conftest import png


def test_generate_writes_the_picture(settings, tmp_path, capsys):
    target = tmp_path / "bike.png"
    assert main(["generate", "a red bicycle", "-o", str(target)]) == 0
    assert target.read_bytes() == settings.image
    assert "Wrote" in capsys.readouterr().err


def test_generate_passes_style_format_size_and_quality(settings, tmp_path):
    target = tmp_path / "bike.png"
    main(["generate", "a red bicycle", "-o", str(target), "--style", "flat", "--format", "4:3",
          "--size", "large", "--quality", "high"])
    body = settings.bodies("/images/generations")[0]
    assert body["size"] == "1664x1248" and body["num_inference_steps"] == 50
    assert body["prompt"].startswith("Flat vector illustration")


def test_several_variants_are_numbered(settings, tmp_path):
    target = tmp_path / "bike.png"
    assert main(["generate", "a red bicycle", "-o", str(target), "-n", "2"]) == 0
    assert (tmp_path / "bike-1.png").exists() and (tmp_path / "bike-2.png").exists()
    assert not target.exists()


def test_with_text_leaves_the_no_lettering_sentence_out(settings, tmp_path):
    main(["generate", "a sign", "-o", str(tmp_path / "a.png"), "--with-text"])
    assert "no writing" not in settings.bodies("/images/generations")[0]["prompt"]


def test_enhance_asks_a_chat_model_first(settings, tmp_path):
    settings.answer = "A red racing bicycle leaning on a brick wall"
    main(["generate", "a red bicycle", "-o", str(tmp_path / "a.png"), "--enhance"])
    assert settings.bodies("/chat/completions")
    assert "brick wall" in settings.bodies("/images/generations")[0]["prompt"]


def test_edit_writes_next_to_the_source_by_default(settings, image_file):
    assert main(["edit", str(image_file), "make it blue"]) == 0
    assert (image_file.parent / "picture-edited.png").exists()
    assert settings.bodies("/images/edits")[0]["prompt"] == "make it blue"


def test_edit_takes_its_own_output_name(settings, image_file, tmp_path):
    target = tmp_path / "blue.png"
    assert main(["edit", str(image_file), "make it blue", "-o", str(target)]) == 0
    assert target.exists()


def test_describe_prints_the_answer(settings, image_file, capsys):
    settings.answer = "A white square."
    assert main(["describe", str(image_file)]) == 0
    assert capsys.readouterr().out.strip() == "A white square."


def test_describe_writes_a_file_when_asked(settings, image_file, tmp_path):
    settings.answer = "A white square."
    target = tmp_path / "answer.txt"
    assert main(["describe", str(image_file), "-o", str(target)]) == 0
    assert target.read_text(encoding="utf-8").strip() == "A white square."


def test_describe_takes_a_question_and_a_language(settings, image_file):
    main(["describe", str(image_file), "How many people?", "--language", "de"])
    text = settings.bodies("/chat/completions")[0]["messages"][0]["content"][0]["text"]
    assert "Question: How many people?" in text and "Respond in German." in text


def test_without_settings_the_error_says_what_to_set(tmp_path, capsys):
    assert main(["generate", "a red bicycle", "-o", str(tmp_path / "a.png")]) == 2
    error = capsys.readouterr().err
    assert "PROMPT2IMAGE_BASE_URL" in error and "PROMPT2IMAGE_MODEL" in error


def test_a_missing_file_is_a_clear_error(settings, tmp_path, capsys):
    assert main(["describe", str(tmp_path / "gone.png")]) == 2
    assert "Error" in capsys.readouterr().err


def test_an_unsupported_file_type_is_refused(settings, tmp_path, capsys):
    path = tmp_path / "picture.gif"
    path.write_bytes(png())
    assert main(["describe", str(path)]) == 2
    assert "PNG and JPG" in capsys.readouterr().err


def test_a_failing_server_is_reported(settings, tmp_path, capsys):
    settings.status = 500
    assert main(["generate", "a red bicycle", "-o", str(tmp_path / "a.png")]) == 2
    assert "Error" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["generate", "x", "--style", "cubism"], ["generate", "x", "--format", "2:1"]])
def test_an_unknown_option_is_refused_by_the_help(argv):
    with pytest.raises(SystemExit):
        main(argv)


def test_the_output_folder_is_created(settings, tmp_path):
    target = tmp_path / "pictures" / "bike.png"
    assert main(["generate", "a red bicycle", "-o", str(target)]) == 0
    assert target.exists()


def test_a_written_picture_can_be_opened(settings, tmp_path):
    settings.image = png(32, 16)
    target = tmp_path / "bike.png"
    main(["generate", "a red bicycle", "-o", str(target)])
    with Image.open(target) as image:
        assert (image.width, image.height) == (32, 16)
