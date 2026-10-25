import json
import pytest
import respx
import httpx
from unittest.mock import MagicMock
from app.llm.client import OpenAICompatClient, strip_think_tags
from app.models import AppSetting


def test_strip_think_tags():
    raw = "<think>Some private thoughts here\nstep by step</think>Here is the final answer."
    assert strip_think_tags(raw) == "Here is the final answer."


def test_strip_think_tags_empty():
    assert strip_think_tags("") == ""
    assert strip_think_tags("No think tags") == "No think tags"


@respx.mock
def test_llm_client_chat_success():
    # Mock settings service and DB
    mock_db = MagicMock()
    # Mock setting queries
    mock_db.query().filter().first.return_value = None
    mock_db.query().all.return_value = [
        AppSetting(key="llm.provider", value="groq"),
        AppSetting(key="llm.base_url", value="https://api.groq.com/openai/v1"),
        AppSetting(key="llm.model", value="llama-3.3-70b-versatile"),
        AppSetting(key="llm.api_keys", value=[{"key": "test-key-enc", "label": "test-label"}]),
    ]
    mock_db.query().scalar.return_value = 0  # daily tokens

    client = OpenAICompatClient(mock_db)
    # Mock get_decrypted_keys
    client.settings_service.get_decrypted_keys = MagicMock(
        return_value=[{"key": "gsk_12345", "label": "test-label"}]
    )

    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello, world!"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    )

    resp = client.chat([{"role": "user", "content": "hi"}], purpose="probe")
    assert resp.content == "Hello, world!"
    assert resp.prompt_tokens == 10
    assert resp.completion_tokens == 5
    assert resp.key_label == "test-label"


@respx.mock
def test_llm_client_failover_on_401():
    mock_db = MagicMock()
    mock_db.query().scalar.return_value = 0

    client = OpenAICompatClient(mock_db)
    client.settings_service.get_read_settings = MagicMock(
        return_value=MagicMock(
            llm_provider="groq",
            llm_base_url="https://api.groq.com/openai/v1",
            llm_model="test-model",
            llm_key_strategy="failover",
            llm_daily_token_cap=100000,
            llm_max_tokens_param="max_tokens",
            llm_max_output_tokens=1000,
            llm_extra_params={},
            llm_extra_headers={},
            llm_strip_reasoning=True,
            llm_timeout_s=10,
            llm_structured_mode="auto",
            llm_supports_tools=True,
        )
    )
    client.settings_service.get_decrypted_keys = MagicMock(
        return_value=[
            {"key": "bad_key", "label": "bad"},
            {"key": "good_key", "label": "good"},
        ]
    )

    # First key returns 401, second returns 200
    route = respx.post("https://api.groq.com/openai/v1/chat/completions")
    route.side_effect = [
        httpx.Response(401, text="Unauthorized"),
        httpx.Response(200, json={"choices": [{"message": {"content": "Recovered!"}}]}),
    ]

    resp = client.chat([{"role": "user", "content": "test"}], purpose="probe")
    assert resp.content == "Recovered!"
    assert resp.key_label == "good"


@respx.mock
def test_groq_output_tokens_are_clamped_to_provider_limit():
    mock_db = MagicMock()
    mock_db.query().scalar.return_value = 0

    client = OpenAICompatClient(mock_db)
    client.settings_service.get_read_settings = MagicMock(
        return_value=MagicMock(
            llm_provider="groq",
            llm_base_url="https://api.groq.com/openai/v1",
            llm_model="test-model",
            llm_key_strategy="failover",
            llm_daily_token_cap=100000,
            llm_max_tokens_param="max_tokens",
            llm_max_output_tokens=1973,
            llm_extra_params={},
            llm_extra_headers={},
            llm_strip_reasoning=True,
            llm_timeout_s=10,
            llm_structured_mode="auto",
            llm_supports_tools=True,
        )
    )
    client.settings_service.get_decrypted_keys = MagicMock(
        return_value=[{"key": "good_key", "label": "good"}]
    )
    route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )
    )

    client.chat([{"role": "user", "content": "test"}], purpose="extract")

    assert route.calls[0].request.content
    payload = json.loads(route.calls[0].request.content)
    assert payload["max_tokens"] <= 1000
