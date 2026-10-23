"""What the three tasks send to the server and what they make of its answer."""

import io

import pytest
from PIL import Image

from prompt2image import core
from prompt2image.errors import InputError, ModelError, OptionError
from prompt2image.prompts import NO_TEXT

from conftest import jpg, png


def test_generate_sends_size_and_steps(settings):
    core.generate("An apple", format_="16:9", size="medium", quality="standard")
    body = settings.bodies("/images/generations")[0]
    assert body["size"] == "1344x768" and body["num_inference_steps"] == 28
    assert body["response_format"] == "b64_json" and body["n"] == 1


def test_generate_sends_style_subject_and_the_no_lettering_sentence(settings):
    core.generate("An apple", style="photo")
    prompt = settings.bodies("/images/generations")[0]["prompt"]
    assert prompt.startswith("Photorealistic photograph") and "Subject: An apple" in prompt
    assert prompt.endswith(NO_TEXT)


def test_an_expanded_prompt_replaces_the_short_one(settings):
    core.generate("An apple", model_prompt="A red apple on an oak table, soft window light")
    prompt = settings.bodies("/images/generations")[0]["prompt"]
    assert "oak table" in prompt and "An apple" not in prompt


def test_if_the_server_refuses_the_size_it_is_tried_smaller(settings):
    """A server can answer that the height must be between 1 and 1080."""
    settings.statuses = [422, 200]
    core.generate("An apple", format_="16:9", size="large")
    assert [b["size"] for b in settings.bodies("/images/generations")] == ["1920x1088", "1904x1072"]


def test_a_size_that_already_fits_is_not_tried_again(settings):
    settings.statuses = [400]
    with pytest.raises(ModelError):
        core.generate("An apple", format_="1:1", size="medium")
    assert len(settings.bodies("/images/generations")) == 1


def test_every_variant_is_a_request_of_its_own(settings):
    images = core.generate("An apple", n=3)
    assert len(images) == 3 and len(settings.bodies("/images/generations")) == 3


def test_too_many_variants_do_not_count(settings):
    with pytest.raises(OptionError):
        core.generate("An apple", n=5)


def test_edit_sends_the_calculated_size_and_the_steps(settings, tmp_path):
    path = tmp_path / "tall.png"
    path.write_bytes(png(576, 1024))
    core.edit(path, "blue", size="small", quality="draft")
    form = settings.bodies("/images/edits")[0]
    assert form["size"] == "576x1024" and form["num_inference_steps"] == "15"
    assert form["guidance_scale"] == "3.5" and form["n"] == "1"


def test_edit_names_the_model_in_the_header_too(settings, image_file):
    core.edit(image_file, "blue")
    headers = [r["headers"] for r in settings.requests if r["path"].endswith("/images/edits")][0]
    assert headers["inference-service"] == "a-model"


def test_a_fixed_format_wins_over_the_source(settings, tmp_path):
    path = tmp_path / "tall.png"
    path.write_bytes(png(300, 900))
    core.edit(path, "blue", format_="1:1", size="medium")
    assert settings.bodies("/images/edits")[0]["size"] == "1024x1024"


def test_edit_takes_an_image_answer_as_it_is(settings, image_file):
    settings.raw_image = True
    settings.image = png(8, 8, "red")
    result = core.edit(image_file, "blue")[0]
    with Image.open(io.BytesIO(result)) as answer:
        assert (answer.width, answer.height) == (8, 8)


def test_a_padded_panorama_comes_back_as_its_band(settings, tmp_path):
    path = tmp_path / "panorama.png"
    path.write_bytes(png(2048, 400))
    settings.raw_image = True
    settings.image = png(2048, 512)
    result = core.edit(path, "skyline")[0]
    with Image.open(io.BytesIO(result)) as band:
        # The canvas was 4:1, so the source is 400 of 512 rows.
        assert band.width == 2048 and band.height == 400


def test_the_source_of_a_padded_panorama_is_kept_without_its_white_band(tmp_path):
    path = tmp_path / "panorama.png"
    path.write_bytes(png(2048, 400))
    with Image.open(io.BytesIO(core.source_band(path))) as source:
        assert (source.width, source.height) == (2048, 400)


def test_a_normal_source_is_kept_unchanged(image_file):
    assert core.source_band(image_file) == image_file.read_bytes()


def test_describe_sends_the_instruction_and_a_length_limit(settings, image_file):
    settings.answer = "Four people."
    assert core.describe(image_file, task="describe", language="de") == "Four people."
    body = settings.bodies("/chat/completions")[0]
    text = body["messages"][0]["content"][0]["text"]
    assert "Respond in German." in text
    # The general prompt asks for detail and the language of the image, both would override the task.
    assert "same language as the primary text" not in text
    assert body["max_tokens"] > 0


def test_describe_attaches_the_picture_as_a_data_url(settings, image_file):
    core.describe(image_file)
    part = settings.bodies("/chat/completions")[0]["messages"][0]["content"][1]
    assert part["image_url"]["url"].startswith("data:image/png;base64,")


def test_a_jpg_is_attached_as_a_jpeg(settings, tmp_path):
    path = tmp_path / "picture.jpg"
    path.write_bytes(jpg())
    core.describe(path)
    part = settings.bodies("/chat/completions")[0]["messages"][0]["content"][1]
    assert part["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_a_prompt_without_a_task_counts_as_a_question(settings, image_file):
    core.describe(image_file, "How many people?")
    text = settings.bodies("/chat/completions")[0]["messages"][0]["content"][0]["text"]
    assert "Question: How many people?" in text


def test_without_a_prompt_the_picture_is_described(settings, image_file):
    core.describe(image_file)
    text = settings.bodies("/chat/completions")[0]["messages"][0]["content"][0]["text"]
    assert "Describe the image in detail" in text


def test_an_own_instruction_replaces_the_task(settings, image_file):
    core.describe(image_file, instruction="Write alternative text.")
    text = settings.bodies("/chat/completions")[0]["messages"][0]["content"][0]["text"]
    assert text == "Write alternative text."


def test_the_general_instruction_is_there_for_a_call_without_a_task():
    text = core.general_instruction("de")
    assert "Transcribe all visible text verbatim" in text and "Respond in German." in text


def test_enhance_asks_a_chat_model_and_strips_the_quotes(settings):
    settings.answer = '"A red apple on an oak table."'
    assert core.enhance("apple") == "A red apple on an oak table."
    body = settings.bodies("/chat/completions")[0]
    assert body["messages"][0]["role"] == "system" and body["temperature"] == 0.6


def test_an_empty_prompt_does_not_reach_the_server(settings):
    with pytest.raises(OptionError):
        core.enhance("   ")
    with pytest.raises(OptionError):
        core.edit(b"x", "   ")
    assert settings.requests == []


def test_a_failing_server_becomes_a_model_error(settings, image_file):
    settings.status = 500
    with pytest.raises(ModelError):
        core.describe(image_file)


def test_an_answer_without_a_picture_becomes_a_model_error(settings, monkeypatch, image_file):
    settings.raw_image = False
    monkeypatch.setattr(core, "_payload", lambda response: {"data": []})
    with pytest.raises(ModelError):
        core.generate("An apple")


@pytest.mark.parametrize("name, content", [
    ("picture.gif", png()),
    ("picture.png", b""),
    ("picture.png", b"not an image at all"),
])
def test_a_bad_input_picture_is_refused(settings, tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(InputError):
        core.describe(path)


def test_a_picture_beyond_the_limit_is_refused(settings, image_file):
    with pytest.raises(InputError):
        core.describe(image_file, max_mb=0.00001)
