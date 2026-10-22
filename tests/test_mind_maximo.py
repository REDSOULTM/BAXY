"""BAXY Renew al máximo, tanda 1 (artifacts/renew/maximo/MAXIMO.md): resources and latency without changing decisions.
Each test holds one lever, so it can be measured and withdrawn on its own."""
from pathlib import Path


def test_the_model_server_keeps_no_prompt_cache_in_ram_and_ten_checkpoints(tmp_path: Path, monkeypatch) -> None:
    # 3.3: the cache in RAM held nothing (no prompt fit its 1,536 MiB) and 32 checkpoints cost ~1.6 GB of RAM.
    from baxy_mind import llm_server
    launched: list[list[str]] = []

    class Process:
        def __init__(self, command, **kwargs) -> None:
            launched.append(command)

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(llm_server.subprocess, "Popen", Process)
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **kwargs: type("T", (), {"start": lambda self: None})())
    llm_server.LlmServer("model.gguf", "llama-server.exe").start()
    command = launched[0]
    assert command[command.index("-cram") + 1] == "0"
    assert command[command.index("-ctxcp") + 1] == "10"
    assert "-cms" not in command and "--checkpoint-min-step" not in command
