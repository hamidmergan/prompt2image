"""The web page and its routes, against the fake server."""

import io

import pytest
from PIL import Image

from conftest import jpg, png

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from prompt2image.web.app import create_app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(create_app(allowed_hosts=["testserver"]))


def _file(name="picture.png"):
    return {"image": (name, png(), "image/png")}


def test_the_page_is_served(client):
    answer = client.get("/")
    assert answer.status_code == 200 and "Create image" in answer.text
    assert "Edit image" in answer.text and "Describe image" in answer.text


def test_the_static_files_are_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_the_options_carry_the_tables_the_page_needs(client):
    data = client.get("/api/options").json()
    assert data["formats"] == ["1:1", "16:9", "4:3", "3:4", "9:16"]
    assert data["sizes"] == ["small", "medium", "large"]
    assert data["qualities"] == ["draft", "standard", "high"]
    assert data["tasks"] == ["describe", "text", "question"]
    assert data["pixels"]["16:9"]["large"] == "1920x1088"
    assert data["variants"] == {"generate": 4, "edit": 2}
    assert data["source_format"] == "source"
    assert set(data["quick_edits"]) == {"white", "sketch", "no_text", "vivid"}


def test_without_settings_the_page_says_so(client):
    assert client.get("/api/options").json()["configured"] == {
        "image": False, "edit": False, "vision": False, "chat": False}


def test_with_settings_the_page_says_so(settings, client):
    assert client.get("/api/options").json()["configured"]["image"] is True


def test_generate_returns_an_image_that_can_be_fetched(settings, client):
    answer = client.post("/api/generate", data={"prompt": "a red bicycle", "format": "16:9", "size": "small"})
    assert answer.status_code == 200
    data = answer.json()
    assert len(data["images"]) == 1 and data["size"] == "1024x576"
    picture = client.get(f"/api/image/{data['images'][0]}")
    assert picture.status_code == 200 and picture.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(picture.content)) as image:
        assert image.format == "PNG"


def test_generate_passes_the_options_on(settings, client):
    client.post("/api/generate", data={"prompt": "a red bicycle", "style": "photo", "quality": "high",
                                       "variants": "2", "no_text": "false"})
    bodies = settings.bodies("/images/generations")
    assert len(bodies) == 2
    assert bodies[0]["num_inference_steps"] == 50
    assert bodies[0]["prompt"].startswith("Photorealistic photograph")
    assert "no writing" not in bodies[0]["prompt"]


def test_the_settings_on_the_page_win(server, client, monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://nowhere/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "other")
    answer = client.post("/api/generate", data={"prompt": "a red bicycle", "base_url": server.base_url,
                                                "model": "from-the-page"})
    assert answer.status_code == 200
    assert server.bodies("/images/generations")[0]["model"] == "from-the-page"


def test_enhance_asks_the_chat_model(settings, client):
    settings.answer = "A red racing bicycle on a brick wall"
    answer = client.post("/api/enhance", data={"prompt": "a bike"})
    assert answer.json()["prompt"] == "A red racing bicycle on a brick wall"


def test_edit_keeps_the_source_for_before_and_after(settings, client):
    answer = client.post("/api/edit", data={"prompt": "make it blue"}, files=_file())
    data = answer.json()
    assert answer.status_code == 200 and len(data["images"]) == 1
    assert client.get(f"/api/image/{data['source']}").status_code == 200
    assert settings.bodies("/images/edits")[0]["prompt"] == "make it blue"


def test_the_page_reports_the_size_that_was_used(settings, client):
    settings.statuses = [422, 200]
    settings.error = "the height must be between 1 and 1080"
    data = client.post("/api/generate", data={"prompt": "a bike", "format": "16:9", "size": "large"}).json()
    assert data["size"] == "1904x1072" and data["sizes"] == ["1904x1072"]


def test_an_uploaded_jpg_keeps_its_own_content_type(settings, client):
    data = client.post("/api/edit", data={"prompt": "make it blue"},
                       files={"image": ("photo.jpg", jpg(), "image/jpeg")}).json()
    assert client.get(f"/api/image/{data['source']}").headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/image/{data['images'][0]}").headers["content-type"] == "image/png"


def test_the_chat_model_from_the_page_reaches_the_chat_endpoint(server, client, monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", server.base_url)
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "an-image-model")
    client.post("/api/enhance", data={"prompt": "a bike", "model": "a-chat-model"})
    assert server.bodies("/chat/completions")[0]["model"] == "a-chat-model"


def test_the_page_has_a_model_field_for_every_task(client):
    page = client.get("/").text
    for field in ("set-model", "set-edit-model", "set-vision-model", "set-chat-model"):
        assert f'id="{field}"' in page
    script = client.get("/static/app.js").text
    for kind in ("image", "edit", "vision", "chat"):
        assert f'withSettings(new FormData(), "{kind}")' in script


def test_the_upload_hint_takes_the_limit_from_the_settings(client):
    assert "20 MB" not in client.get("/").text
    assert "max_image_mb} MB" in client.get("/static/app.js").text


def test_describe_answers_with_text(settings, client):
    settings.answer = "A white square."
    answer = client.post("/api/describe", data={"task": "describe", "language": "de"}, files=_file())
    assert answer.json()["text"] == "A white square."
    text = settings.bodies("/chat/completions")[0]["messages"][0]["content"][0]["text"]
    assert "Respond in German." in text


def test_a_question_without_a_task_counts_as_a_question(settings, client):
    answer = client.post("/api/describe", data={"prompt": "How many people?"}, files=_file())
    assert answer.json()["task"] == "question"
    text = settings.bodies("/chat/completions")[0]["messages"][0]["content"][0]["text"]
    assert "Question: How many people?" in text


def test_a_bad_option_becomes_a_400(settings, client):
    answer = client.post("/api/generate", data={"prompt": "a red bicycle", "style": "cubism"})
    assert answer.status_code == 400 and "cubism" in answer.text


def test_a_missing_setting_becomes_a_400_naming_the_variable(client):
    answer = client.post("/api/generate", data={"prompt": "a red bicycle"})
    assert answer.status_code == 400 and "PROMPT2IMAGE_BASE_URL" in answer.text


def test_a_file_that_is_not_an_image_is_refused(settings, client):
    answer = client.post("/api/describe", files={"image": ("note.txt", b"hello", "text/plain")})
    assert answer.status_code == 400 and "PNG and JPG" in answer.text


def test_an_unknown_image_is_a_404(client):
    assert client.get("/api/image/0123456789abcdef").status_code == 404


def test_an_unknown_host_is_refused():
    other = TestClient(create_app(allowed_hosts=["example.test"]))
    assert other.get("/").status_code == 400


def test_a_foreign_origin_is_refused(client):
    assert client.get("/", headers={"origin": "http://evil.test"}).status_code == 403
    assert client.get("/", headers={"origin": "http://testserver"}).status_code == 200
