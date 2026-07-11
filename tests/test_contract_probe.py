from __future__ import annotations

import base64

import pytest

from plva_proxy.contract_probe import (
    COMPLETIONS_URL,
    MODEL_ID,
    ContractError,
    build_chat_payload,
    find_ready_model,
    summarize_completion,
    summarize_sse,
)

SYNTHETIC_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_build_chat_payload_uses_exact_model_and_synthetic_data_url() -> None:
    payload = build_chat_payload(SYNTHETIC_PNG, stream=False)

    assert payload["model"] == MODEL_ID == "Hcompany/Holo3-35B-A3B"
    assert payload["stream"] is False
    image_url = payload["messages"][-1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert base64.b64decode(image_url.partition(",")[2]) == SYNTHETIC_PNG
    assert "api_key" not in repr(payload).lower()


def test_contract_constants_use_current_overshoot_v1beta_endpoint() -> None:
    assert COMPLETIONS_URL == "https://api.overshoot.ai/v1beta/chat/completions"


def test_find_ready_model_requires_exact_ready_entry() -> None:
    document = {
        "data": [
            {"id": MODEL_ID, "status": "ready", "object": "model"},
            {"id": "nearby-model", "status": "ready", "object": "model"},
        ]
    }

    assert find_ready_model(document) == document["data"][0]

    with pytest.raises(ContractError, match="not advertised"):
        find_ready_model({"data": []})

    with pytest.raises(ContractError, match="not ready"):
        find_ready_model({"data": [{"id": MODEL_ID, "status": "loading"}]})


@pytest.mark.parametrize(
    ("message", "expected_mode"),
    [
        ({"role": "assistant", "content": '{"tool_call": {}}'}, "content"),
        ({"role": "assistant", "content": None, "tool_calls": [{"id": "call_1"}]}, "tool_calls"),
    ],
)
def test_summarize_completion_records_shape_not_content(
    message: dict[str, object], expected_mode: str
) -> None:
    sensitive_content = "synthetic-sensitive-marker"
    message = dict(message)
    if expected_mode == "content":
        message["content"] = sensitive_content
    document = {
        "id": "completion-id",
        "object": "chat.completion",
        "model": MODEL_ID,
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }

    summary = summarize_completion(document)

    assert summary.response_keys == ("choices", "id", "model", "object", "usage")
    assert summary.message_mode == expected_mode
    assert summary.model == MODEL_ID
    assert sensitive_content not in repr(summary)


def test_summarize_sse_reports_delta_shape_and_done_without_retaining_text() -> None:
    raw = b"".join(
        [
            b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"synthetic-sensitive-marker"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]
    )

    summary = summarize_sse(raw)

    assert summary.event_count == 2
    assert summary.done is True
    assert summary.delta_keys == ("content", "role")
    assert summary.has_tool_call_delta is False
    assert "synthetic-sensitive-marker" not in repr(summary)


def test_summarize_sse_fails_closed_on_malformed_data_event() -> None:
    with pytest.raises(ContractError, match="invalid SSE JSON"):
        summarize_sse(b"data: {not-json}\n\n")
