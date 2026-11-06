"""uso-51 (2026-11-03, «aumentar el contexto»; the owner's budget: 4 GB of VRAM for all of BAXY): how the mind starts
llama-server for the most context inside it (src/baxy_mind/llm_server.py: kv_types, default_context, slots), as
measured on the PC (ft_v1/c5/INFORME_51.md) and, for Vulkan's slots, on an RX 7600 (ft_v1/c5/AMD_TUKIPC_0311.md)."""
import pathlib


def _context(command: list[str]) -> int:
    return int(command[command.index("-c") + 1])


def test_on_cuda_the_output_matrix_in_ram_leaves_77k_cells_of_q8_0_in_the_4_gb(tmp_path: pathlib.Path, monkeypatch) -> None:
    # Measured on the PC (INFORME_51.md): q8_0 took 4,000 MiB at 53,248 cells. Qwen3.5-4B ties its output to the token
    # embedding (token_embd.weight, Q6_K, 497 MiB); kept on the CPU it frees 496 MiB, and 77,824 cells take 4,032.
    # q4_0 would fit more but lost the gate's close calls, so q8_0 stays. Vulkan and the CPU keep what was measured there.
    from test_mind_gpu import _command

    for name in ("BAXY_RENEW_KV", "BAXY_RENEW_OUTPUT_CPU"):
        monkeypatch.delenv(name, raising=False)
    cuda = _command(monkeypatch, tmp_path, backend="cuda")
    assert (cuda[cuda.index("-ctk") + 1], cuda[cuda.index("-ctv") + 1], _context(cuda)) == ("q8_0", "q8_0", 77824)
    assert cuda[cuda.index("-ot") + 1] == r"token_embd\.weight=CPU"
    cpu = _command(monkeypatch, tmp_path, backend="cpu")
    assert _context(cpu) == 53248 and "-ot" not in cpu
    assert _context(_command(monkeypatch, tmp_path, backend="cuda", context=40960)) == 40960


def test_each_cache_and_output_place_keeps_the_context_that_fits_it(tmp_path: pathlib.Path, monkeypatch) -> None:
    # Each written token costs ~9 ms more with the output in RAM: BAXY_RENEW_OUTPUT_CPU=0 goes back to the GPU and to
    # the 53,248 cells that fit there. Another cache asked for (BAXY_RENEW_KV) keeps the cells measured for it.
    from test_mind_gpu import _command

    monkeypatch.delenv("BAXY_RENEW_KV", raising=False)
    monkeypatch.setenv("BAXY_RENEW_OUTPUT_CPU", "0")
    cuda = _command(monkeypatch, tmp_path, backend="cuda")
    assert "-ot" not in cuda and _context(cuda) == 53248
    monkeypatch.setenv("BAXY_RENEW_KV", "q4_0")
    assert _context(_command(monkeypatch, tmp_path, backend="cuda")) == 86016
    monkeypatch.delenv("BAXY_RENEW_OUTPUT_CPU")
    assert _context(_command(monkeypatch, tmp_path, backend="cuda")) == 122880
    monkeypatch.setenv("BAXY_RENEW_KV", "q8_0,q4_0")  # no cells measured for a mixed cache: as before
    assert _context(_command(monkeypatch, tmp_path, backend="cuda")) == 53248


def test_on_vulkan_the_server_has_three_slots_on_one_unified_cache(tmp_path: pathlib.Path, monkeypatch) -> None:
    # Measured on an RX 7600 (AMD_TUKIPC_0311.md): with one or two slots the prefix read at 244 tokens/s and the decode
    # at 21; with «-np 3 -kvu» at 946 and 33, the same 22 decisions, +76 MiB. The mind still uses slot 0 alone, and with
    # the unified cache that slot sees the whole context.
    from test_mind_gpu import _command

    vulkan = _command(monkeypatch, tmp_path, backend="vulkan")
    assert vulkan[vulkan.index("-np") + 1] == "3" and "-kvu" in vulkan
    for backend in ("cuda", "cpu"):
        command = _command(monkeypatch, tmp_path, backend=backend)
        assert command[command.index("-np") + 1] == "1" and "-kvu" not in command


def test_on_vulkan_a_q8_0_cache_of_61k_cells_stays_inside_the_4_gb(tmp_path: pathlib.Path, monkeypatch) -> None:
    # uso-60, measured on the RX 7600 (b11609, INFORME_60.md): the f16 cache took 4,460 MiB of the GPU at 53,248 cells
    # (4,548 by llama.cpp's count), past the 4 GB, and those cells leave the history ~1k tokens beside the 48.8k-token
    # prefix. The f16 cache does not fit 4 GB with the prefix at all; q8_0 does: 61,440 cells take 3,916 MiB, and a q8_0
    # cache past 1 GiB (62,464 cells or more) goes to a path ~4 times slower. The output matrix stays on the GPU: in RAM
    # it halved the decode here (27 → 13.5 tokens/s) and read the prompt 4 times slower. Whatever the GPU's memory.
    from test_mind_gpu import _attention, _command

    for name in ("BAXY_RENEW_KV", "BAXY_RENEW_OUTPUT_CPU", "BAXY_RENEW_CTX"):
        monkeypatch.delenv(name, raising=False)
    vulkan = _command(monkeypatch, tmp_path, backend="vulkan")
    assert _attention(vulkan) == ("q8_0", "q8_0", "on") and _context(vulkan) == 61440
    assert "-ot" not in vulkan
    monkeypatch.setenv("BAXY_RENEW_OUTPUT_CPU", "1")
    assert "-ot" not in _command(monkeypatch, tmp_path, backend="vulkan")
    monkeypatch.setenv("BAXY_RENEW_KV", "f16")  # asked for: faster reads, the 53,248 cells it had (4,460 MiB)
    f16 = _command(monkeypatch, tmp_path, backend="vulkan")
    assert _attention(f16) == ("f16", "f16", "auto") and _context(f16) == 53248


def test_a_cut_on_vulkan_leaves_what_its_slower_cache_reads_in_time(tmp_path: pathlib.Path, monkeypatch) -> None:
    # The q8_0 cache on the RX 7600 reads the history past the prefix at ~174 tokens/s (f16 527, CUDA ~1,440): the
    # 6,144 tokens a cut may leave on CUDA would take ~35 s against the decision's 24. On Vulkan with a quantized K a cut
    # leaves at most 2,048 (~12 s); with f16, CUDA and the CPU, REREAD_TOKENS as before.
    from baxy_mind import llm_server
    from baxy_mind.llm_server import REREAD_TOKENS

    monkeypatch.delenv("BAXY_RENEW_KV", raising=False)
    assert llm_server.LlmServer("m.gguf", "llama-server.exe", backend="vulkan").reread_tokens == 2048
    for backend in ("cuda", "cpu"):
        assert llm_server.LlmServer("m.gguf", "llama-server.exe", backend=backend).reread_tokens == REREAD_TOKENS
    monkeypatch.setenv("BAXY_RENEW_KV", "f16")
    assert llm_server.LlmServer("m.gguf", "llama-server.exe", backend="vulkan").reread_tokens == REREAD_TOKENS


def test_the_mind_takes_its_backends_context_unless_baxy_renew_ctx_says_another(tmp_path: pathlib.Path, monkeypatch) -> None:
    from baxy_mind import __main__ as sidecar

    given: dict = {}

    class Server:
        def __init__(self, *args, **kwargs) -> None:
            given.update(kwargs)
            raise RuntimeError("stop here")

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", str(tmp_path / "llama-server.exe"))
    monkeypatch.setattr(sidecar, "declared_build", lambda server: "b11609")
    monkeypatch.setattr(sidecar, "declared_backend", lambda server, build: "cuda")
    monkeypatch.setattr(sidecar, "LlmServer", Server)
    monkeypatch.delenv("BAXY_RENEW_CTX", raising=False)
    assert sidecar.main() == 2 and given["context"] is None  # LlmServer's default_context
    monkeypatch.setenv("BAXY_RENEW_CTX", "40960")
    assert sidecar.main() == 2 and given["context"] == 40960
