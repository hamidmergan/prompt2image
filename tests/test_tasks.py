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
    settings.error = "the height must be between 1 and 1080"
    core.generate("An apple", format_="16:9", size="large")
    assert [b["size"] for b in settings.bodies("/images/generations")] == ["1920x1088", "1904x1072"]


def test_a_size_that_already_fits_is_not_tried_again(settings):
    settings.statuses = [400]
    with pytest.raises(ModelError):
        core.generate("An apple", format_="1:1", size="medium")
    assert len(settings.bodies("/images/generations")) == 1


def test_a_complaint_about_something_else_is_not_tried_smaller(settings):
    settings.statuses = [400]
    settings.error = "num_inference_steps is not a known field"
    with pytest.raises(ModelError) as info:
        core.generate("An apple", format_="16:9", size="large")
    assert len(settings.bodies("/images/generations")) == 1
    # The message says what the server really complained about.
    assert "num_inference_steps" in str(info.value)


def test_the_size_that_was_used_comes_with_the_picture(settings):
    settings.statuses = [422, 200]
    settings.error = "the height must be between 1 and 1080"
    picture = core.generate("An apple", format_="16:9", size="large")[0]
    assert picture.size == "1904x1072"
    assert core.generate("An apple", format_="1:1", size="small")[0].size == "768x768"


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


def test_a_panorama_reaches_the_server_on_a_padded_canvas(settings, tmp_path):
    path = tmp_path / "panorama.png"
    path.write_bytes(png(2048, 400))
    core.edit(path, "skyline")
    form = settings.bodies("/images/edits")[0]
    with Image.open(io.BytesIO(form["image"]["content"])) as uploaded:
        # 2048x400 is beyond 4:1, so it goes onto a 2048x512 canvas before it is sent.
        assert (uploaded.width, uploaded.height) == (2048, 512)
    assert form["size"] == "2048x512"


def test_a_fixed_format_keeps_the_whole_canvas_as_the_source(tmp_path):
    path = tmp_path / "panorama.png"
    path.write_bytes(png(2048, 400))
    with Image.open(io.BytesIO(core.source_band(path, format_="1:1"))) as source:
        assert (source.width, source.height) == (2048, 512)


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
    assert body["max_tokens"] == 1500


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


def test_an_answer_without_a_picture_becomes_a_model_error(settings):
    settings.spelling = "empty"
    with pytest.raises(ModelError) as info:
        core.generate("An apple")
    assert "no image" in str(info.value)


@pytest.mark.parametrize("spelling", ["b64_json", "b64", "top_b64_json", "top_b64"])
def test_the_picture_is_found_in_every_usual_answer_shape(settings, spelling):
    settings.spelling = spelling
    settings.image = png(8, 8, "red")
    assert core.generate("An apple")[0] == settings.image


def test_a_link_instead_of_the_picture_is_a_clear_error(settings, image_file):
    settings.spelling = "url"
    with pytest.raises(ModelError) as info:
        core.generate("An apple")
    assert "link" in str(info.value)
    with pytest.raises(ModelError):
        core.edit(image_file, "blue")


def test_a_jpeg_answer_comes_back_as_a_png(settings, image_file):
    settings.raw_image = True
    settings.raw_type = "image/jpeg"
    settings.image = jpg(8, 8)
    for result in (core.edit(image_file, "blue")[0], core.generate("An apple")[0]):
        with Image.open(io.BytesIO(result)) as picture:
            assert picture.format == "PNG"


def test_an_answer_that_is_no_picture_at_all_becomes_a_model_error(settings):
    settings.raw_image = True
    settings.image = b"not a picture"
    with pytest.raises(ModelError):
        core.generate("An apple")


def test_a_refused_connection_becomes_a_model_error(closed_port, image_file, monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", closed_port)
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    monkeypatch.setenv("PROMPT2IMAGE_MAX_RETRIES", "0")
    with pytest.raises(ModelError) as info:
        core.generate("An apple")
    assert "could not be created" in str(info.value)
    with pytest.raises(ModelError):
        core.edit(image_file, "blue")
    with pytest.raises(ModelError):
        core.describe(image_file)
    with pytest.raises(ModelError):
        core.enhance("an apple")


def test_a_timeout_becomes_a_model_error(monkeypatch):
    import socket

    waiting = socket.socket()
    waiting.bind(("127.0.0.1", 0))
    waiting.listen(1)
    try:
        monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", f"http://127.0.0.1:{waiting.getsockname()[1]}/v1")
        monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
        monkeypatch.setenv("PROMPT2IMAGE_MAX_RETRIES", "0")
        with pytest.raises(ModelError):
            core.generate("An apple", timeout=0.3)
    finally:
        waiting.close()


def test_a_busy_server_is_tried_again_as_often_as_the_environment_says(settings, monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_MAX_RETRIES", "4")
    settings.statuses = [503, 503, 503, 503, 200]
    core.generate("An apple")
    assert len(settings.bodies("/images/generations")) == 5


def test_without_retries_one_attempt_is_made(settings, monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_MAX_RETRIES", "0")
    settings.statuses = [503]
    with pytest.raises(ModelError):
        core.generate("An apple")
    assert len(settings.bodies("/images/generations")) == 1


def test_the_message_names_what_the_server_said(settings, image_file, monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_MAX_RETRIES", "0")
    settings.status = 500
    settings.error = "the model is not loaded"
    with pytest.raises(ModelError) as info:
        core.describe(image_file)
    assert "the model is not loaded" in str(info.value)


def test_a_passed_client_keeps_the_edit_header_and_stays_open(settings, image_file):
    import httpx

    with httpx.Client() as client:
        core.edit(image_file, "blue", client=client)
        core.edit(image_file, "green", client=client)
    headers = [r["headers"] for r in settings.requests if r["path"].endswith("/images/edits")]
    assert [h["inference-service"] for h in headers] == ["a-model", "a-model"]


def test_an_edit_can_go_to_a_server_of_its_own(settings, other_server, image_file, monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_EDIT_BASE_URL", other_server.base_url)
    monkeypatch.setenv("PROMPT2IMAGE_EDIT_MODEL", "an-edit-model")
    core.edit(image_file, "blue")
    assert other_server.bodies("/images/edits")[0]["model"] == "an-edit-model"
    assert settings.requests == []


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
