"""Where the address, the model and the key come from, and what is said when they are missing."""

import pytest

from prompt2image import core
from prompt2image.config import CHAT, EDIT, IMAGE, PLACEHOLDER_API_KEY, VISION, endpoint, max_image_mb
from prompt2image.errors import ConfigError


def test_without_an_address_and_a_model_the_error_names_both():
    with pytest.raises(ConfigError) as info:
        endpoint(IMAGE)
    assert "PROMPT2IMAGE_BASE_URL" in str(info.value) and "PROMPT2IMAGE_MODEL" in str(info.value)
    assert "--base-url" in str(info.value) and "--model" in str(info.value)


def test_the_error_names_the_kind_of_model_that_is_needed():
    with pytest.raises(ConfigError) as info:
        endpoint(VISION)
    assert "vision model" in str(info.value)


def test_an_argument_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://env/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "env-model")
    point = endpoint(IMAGE, base_url="http://argument/v1", model="argument-model")
    assert point.base_url == "http://argument/v1" and point.model == "argument-model"


@pytest.mark.parametrize("kind, prefix", [(EDIT, "EDIT_"), (VISION, "VISION_"), (CHAT, "CHAT_")])
def test_a_kind_has_its_own_variables_and_falls_back_to_the_main_ones(monkeypatch, kind, prefix):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://main/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "main-model")
    assert endpoint(kind).model == "main-model"
    monkeypatch.setenv(f"PROMPT2IMAGE_{prefix}MODEL", "own-model")
    assert endpoint(kind).model == "own-model"
    assert endpoint(IMAGE).model == "main-model"


def test_without_a_key_a_placeholder_stands_in(monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://server/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    assert endpoint(IMAGE).api_key == PLACEHOLDER_API_KEY


def test_a_key_from_the_environment_is_used(monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://server/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    monkeypatch.setenv("OPENAI_API_KEY", "from-openai")
    assert endpoint(IMAGE).api_key == "from-openai"
    monkeypatch.setenv("PROMPT2IMAGE_API_KEY", "own")
    assert endpoint(IMAGE).api_key == "own"


def test_the_placeholder_key_sends_no_header(monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://server/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    with core.make_client(endpoint(IMAGE)) as client:
        assert "authorization" not in client.headers
    with core.make_client(endpoint(IMAGE, api_key="secret")) as client:
        assert client.headers["authorization"] == "Bearer secret"


def test_a_missing_v1_part_is_added(monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    assert core.api_base(endpoint(IMAGE, base_url="http://server")) == "http://server/v1"
    assert core.api_base(endpoint(IMAGE, base_url="http://server/v1/")) == "http://server/v1"


def test_creating_waits_longer_than_reading(monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://server/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    assert endpoint(IMAGE).timeout > endpoint(VISION).timeout


@pytest.mark.parametrize("value", ["0", "-1"])
def test_a_timeout_of_zero_does_not_count(monkeypatch, value):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://server/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    monkeypatch.setenv("PROMPT2IMAGE_TIMEOUT", value)
    with pytest.raises(ConfigError):
        endpoint(IMAGE)


def test_a_timeout_that_is_not_a_number_names_its_variable(monkeypatch):
    monkeypatch.setenv("PROMPT2IMAGE_BASE_URL", "http://server/v1")
    monkeypatch.setenv("PROMPT2IMAGE_MODEL", "a-model")
    monkeypatch.setenv("PROMPT2IMAGE_TIMEOUT", "soon")
    with pytest.raises(ConfigError) as info:
        endpoint(IMAGE)
    assert "PROMPT2IMAGE_TIMEOUT" in str(info.value)


def test_the_largest_input_image_comes_from_the_environment(monkeypatch):
    assert max_image_mb() == 20
    monkeypatch.setenv("PROMPT2IMAGE_MAX_IMAGE_MB", "5")
    assert max_image_mb() == 5
    assert max_image_mb(1) == 1
    with pytest.raises(ConfigError):
        max_image_mb(0)


def test_an_unknown_kind_does_not_count():
    with pytest.raises(ConfigError):
        endpoint("audio")
