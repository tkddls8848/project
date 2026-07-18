from app import llm


def test_qwen_generation_payload_is_bounded():
    payload = llm._ollama_payload("질문", "qwen3.5:4b", stream=False)

    assert payload["model"] == "qwen3.5:4b"
    assert payload["stream"] is False
    assert payload["think"] is True
    assert payload["options"]["num_ctx"] == 16384
    assert payload["options"]["num_predict"] == 4096
    assert payload["keep_alive"] == "10m"


def test_streaming_payload_uses_same_generation_limits():
    payload = llm._ollama_payload("질문", "qwen3.5:4b", stream=True)

    assert payload["stream"] is True
    assert payload["options"] == {
        "num_ctx": 16384,
        "num_predict": 4096,
    }
