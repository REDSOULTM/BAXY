"""Tests for the GGUF filename parser used by the Field UI model header."""

from gemma4_agent.infra.model_info import parse_gguf_name


def test_gemma4_e4b_iq2():
    r = parse_gguf_name("/path/gemma-4-E4B-it-UD-IQ2_M.gguf")
    assert r == {
        "family": "gemma 4",
        "params": "4b",
        "quant": "iq2_m",
        "name_full": "gemma-4-E4B-it-UD-IQ2_M",
    }


def test_gemma4_26b():
    r = parse_gguf_name("gemma-4-26B-A4B-it-Q4_K_M.gguf")
    assert r["family"] == "gemma 4"
    assert r["params"] == "26b"
    assert r["quant"] == "q4_k_m"


def test_qwen3():
    r = parse_gguf_name("qwen3-4b-instruct-2507-q5_k_m.gguf")
    assert r["family"] == "qwen 3"
    assert r["params"] == "4b"
    assert r["quant"] == "q5_k_m"


def test_unknown():
    r = parse_gguf_name("some-weird-file.gguf")
    # spec allows either "unknown" or "some 1" depending on how strict the family regex is.
    # the current parser matches leading letters + the first digit run, so this returns
    # ("some", no-digit) → "unknown".
    assert r["family"] == "unknown"
    assert r["params"] == "unknown"
    assert r["quant"] == "unknown"
