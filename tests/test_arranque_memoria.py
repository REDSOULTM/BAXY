"""Uso 95 (F9, uso real 2026-11-04 12:06): llama-server could not reserve its buffers on a PC whose memory the other
programs had taken, died three times (``failed to allocate CPU buffer of size 672405504`` → ``GGML_ASSERT(buffer)
failed``, exit 0xC0000409) and the App only learnt «proceso_salio». The start's failure says the cause the server's own
log gives: the shape of ggml's allocation failure, and on which memory (the PC's RAM or the graphics card's)."""
import pytest

from baxy_mind import llm_server

CPU_ASSERT = """0.04.787.841 W load_hparams: more info: https://github.com/ggml-org/llama.cpp/issues/16842
0.04.850.412 E D:/a/llama.cpp/llama.cpp/ggml/src/ggml-backend.cpp:328: GGML_ASSERT(buffer) failed
ggml_backend_cpu_buffer_type_alloc_buffer: failed to allocate buffer of size 672405504
0.04.850.425 E ggml_backend_buft_alloc_buffer_n_default: failed to allocate CPU buffer of size 672405504
"""


class _Exited:
    def __init__(self, code: int) -> None:
        self.returncode = code

    def poll(self) -> int:
        return self.returncode


def _failed(tmp_path, monkeypatch, log: str | None, code: int = 3221226505) -> llm_server.LlmServer:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    if log is not None:
        path = server._log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(log, encoding="utf-8")
    server._process = _Exited(code)
    return server


def test_a_cpu_buffer_the_server_could_not_allocate_is_the_pcs_memory(tmp_path, monkeypatch):
    assert _failed(tmp_path, monkeypatch, CPU_ASSERT).startup_failure()["cause"] == "ram_insuficiente"


@pytest.mark.parametrize("line", [
    "ggml_backend_cuda_buffer_type_alloc_buffer: allocating 2100.00 MiB on device 0: cudaMalloc failed: out of memory\n"
    "alloc_tensor_range: failed to allocate CUDA0 buffer of size 2202009600\n",
    "ggml_vulkan: Device memory allocation of size 2202009600 failed.\n"
    "llama_model_load: error loading model: unable to allocate Vulkan0 buffer\n",
])
def test_a_device_buffer_the_server_could_not_allocate_is_the_graphics_cards_memory(tmp_path, monkeypatch, line):
    assert _failed(tmp_path, monkeypatch, "0.00.1 I srv load_model: loading model\n" + line, code=1).startup_failure() \
        == {"cause": "vram_insuficiente", "exitCode": 1, "needMb": 2100}


# uso-116 (N23): the owner wants the cause with its amount («falta tanta RAM»): the size of the buffer that did not fit is
# in the same line that says it did not, and the PC's free memory can be read. The graphics card's is not in the log.
@pytest.mark.parametrize("line, need", [
    ("ggml_backend_cuda_buffer_type_alloc_buffer: allocating 66406.25 MiB on device 0: cudaMalloc failed: out of memory\n"
     "ggml_backend_buft_alloc_buffer_n_default: failed to allocate CUDA0 buffer of size 69632000000\n", 66406),
    ("ggml_vulkan: Device memory allocation of size 2202009600 failed.\n"
     "llama_model_load: error loading model: unable to allocate Vulkan0 buffer\n", 2100),
])
def test_what_did_not_fit_on_the_graphics_card_goes_with_the_cause(tmp_path, monkeypatch, line, need):
    assert _failed(tmp_path, monkeypatch, line, code=1).startup_failure() == {
        "cause": "vram_insuficiente", "exitCode": 1, "needMb": need}


def test_what_did_not_fit_in_the_pcs_memory_goes_with_what_was_free(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_server, "free_memory_mb", lambda: 512)
    assert _failed(tmp_path, monkeypatch, CPU_ASSERT).startup_failure() == {
        "cause": "ram_insuficiente", "exitCode": 3221226505, "needMb": 641, "freeMb": 512}


def test_no_figures_are_made_up_when_the_log_gives_none(tmp_path, monkeypatch):
    log = "0.04.850.412 E D:/a/llama.cpp/llama.cpp/ggml/src/ggml-backend.cpp:328: GGML_ASSERT(buffer) failed\n"
    assert _failed(tmp_path, monkeypatch, log).startup_failure() == {
        "cause": "memoria_insuficiente", "exitCode": 3221226505}


# uso-116, seen live with the PC short of memory: the server ran out of video memory reading the prefix, and the App said
# «tiempo» (its process had not ended yet when the mind asked) and nothing about memory.
CUDA_COMPUTE = """0.31.188.856 E ggml_cuda_compute_forward: MUL_MAT failed
0.31.189.403 E CUDA error: out of memory
"""


def test_running_out_of_video_memory_while_computing_is_the_graphics_cards_memory(tmp_path, monkeypatch):
    assert _failed(tmp_path, monkeypatch, CUDA_COMPUTE, code=3221226505).startup_failure() == {
        "cause": "vram_insuficiente", "exitCode": 3221226505}


def test_a_server_still_closing_says_the_lack_of_memory_its_log_already_has(tmp_path, monkeypatch):
    server = _failed(tmp_path, monkeypatch, CUDA_COMPUTE)
    server._process = None
    assert server.startup_failure() == {"cause": "vram_insuficiente"}


def test_a_slow_server_with_nothing_in_its_log_is_still_time(tmp_path, monkeypatch):
    server = _failed(tmp_path, monkeypatch, "0.00.1 I srv load_model: loading model\n")
    server._process = None
    assert server.startup_failure() == {"cause": "tiempo"}


def test_an_assert_on_a_buffer_alone_is_memory_without_saying_which(tmp_path, monkeypatch):
    log = "0.04.850.412 E D:/a/llama.cpp/llama.cpp/ggml/src/ggml-backend.cpp:328: GGML_ASSERT(buffer) failed\n"
    assert _failed(tmp_path, monkeypatch, log).startup_failure() == {
        "cause": "memoria_insuficiente", "exitCode": 3221226505}


@pytest.mark.parametrize("log", [None, "0.00.1 E main: error: failed to load model 'x.gguf'\n"])
def test_any_other_exit_is_still_the_process_that_exited(tmp_path, monkeypatch, log):
    assert _failed(tmp_path, monkeypatch, log, code=1).startup_failure() == {"cause": "proceso_salio", "exitCode": 1}


# Uso 112, en vivo: con el GGUF ausente la mente reintentó 3 minutos sin decir la causa. Líneas de b11609, leídas el 05-11.
@pytest.mark.parametrize("line, cause", [
    ("0.00.186.699 E gguf_init_from_file: failed to open GGUF file 'x.gguf' (No such file or directory)\n", "modelo_ausente"),
    ("0.00.153.343 E gguf_init_from_reader: invalid magic characters: '????', expected 'GGUF'\n", "modelo_danado"),
])
def test_a_model_file_the_server_could_not_open_or_read_is_named(tmp_path, monkeypatch, line, cause):
    log = line + "0.00.186.710 E llama_model_load: error loading model: llama_model_loader: failed to load model from x.gguf\n"
    assert _failed(tmp_path, monkeypatch, log, code=1).startup_failure() == {"cause": cause, "exitCode": 1}


def test_memory_said_by_the_log_comes_before_a_model_file_it_could_not_load(tmp_path, monkeypatch):
    log = "E gguf_init_from_reader: x\nalloc_tensor_range: failed to allocate CPU buffer of size 1\n"
    assert _failed(tmp_path, monkeypatch, log, code=1).startup_failure()["cause"] == "ram_insuficiente"


def test_a_memory_error_in_the_mind_while_the_model_starts_is_the_pcs_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    assert server.startup_failure(MemoryError()) == {"cause": "ram_insuficiente"}
