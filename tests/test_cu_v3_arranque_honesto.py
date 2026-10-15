"""r22: the mind's llama-server startup fails with a cause, never in silence.

Measured 2026-10-09: another llama-server held ~4 GB of a 6 GB GPU, the mind's
server died while warming up, its stderr went to DEVNULL and the catalog reply
was a bare ``request_runtime_failure``. Doubles only: no real server is run.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from baxy_mind import llm_startup
from baxy_mind.tool_catalog import _require_catalog_llm_ready
from baxy_mind.__main__ import _startup_failure_reply, technical_failure_message
from baxy_mind.llm import LlmRuntime
from baxy_mind.llm_startup import LlmStartupFailure, StderrTail

CUDA_OOM = (
    "ggml_backend_cuda_buffer_type_alloc_buffer: allocating 2304.00 MiB on device 0: "
    "cudaMalloc failed: out of memory"
)


@pytest.mark.parametrize(
    ("lines", "cause"),
    [
        ([CUDA_OOM, "llama_model_load: error loading model"], "vram_insuficiente"),
        (["ggml_gallocr_reserve_n: failed to allocate CUDA0 buffer of size 1024"], "vram_insuficiente"),
        (["unable to allocate CPU buffer", "main: exiting due to model loading error"], "ram_insuficiente"),
        (["terminate called after throwing an instance of 'std::bad_alloc'"], "ram_insuficiente"),
        (["main: error: invalid argument: --foo"], "proceso_salio"),
        ([], "proceso_salio"),
    ],
)
def test_the_cause_is_read_from_the_servers_own_lines(lines: list[str], cause: str) -> None:
    assert llm_startup.cause_from_tail(lines) == cause


def test_a_kept_line_carries_no_path_of_the_person() -> None:
    line = llm_startup.scrub_line(
        "llama_model_loader: loaded meta data from C:\\Users\\usuario\\AppData\\Local\\BAXYRuntime\\m.gguf (version GGUF V3)"
    )
    assert "usuario" not in line
    assert "<ruta>" in line
    assert len(llm_startup.scrub_line("x" * 900)) == llm_startup.TAIL_LINE_CHARACTERS


@pytest.mark.parametrize(
    "raw",
    [
        "llama_model_loader: loaded meta data from C:/Users/Nombre Apellido/AppData/m.gguf (version GGUF V3)",
        "gguf_init_from_file: failed to open 'C:\\Users\\Nombre Apellido\\m.gguf': No such file",
        'main: loading model from "D:\\Mis Modelos\\Nombre Apellido\\m.gguf" now',
        "load: \\\\server\\Nombre Apellido\\m.gguf",
        "error: /home/nombre apellido/m.gguf missing",
    ],
)
def test_a_path_with_spaces_is_erased_whole(raw: str) -> None:
    line = llm_startup.scrub_line(raw)
    assert "Nombre" not in line and "Apellido" not in line and "nombre" not in line
    assert "apellido" not in line and "Mis Modelos" not in line
    assert "<ruta>" in line


def test_the_tail_is_bounded_and_kept_only_until_the_server_is_ready() -> None:
    release = threading.Event()

    def stream():
        for index in range(40):
            yield f"startup line {index}\n".encode()
        release.wait(timeout=2)
        yield b"request: something the person said\n"

    tail = StderrTail(stream())
    for _ in range(200):
        if tail.tail(wait_seconds=0.01)[-1:] == ("startup line 39",):
            break
    kept = tail.tail(wait_seconds=0.01)
    assert len(kept) == llm_startup.TAIL_LINES
    assert kept[-1] == "startup line 39"

    tail.stop_recording()
    release.set()
    assert tail.tail(wait_seconds=1.0) == ()


def test_a_model_that_cannot_fit_fails_before_launch(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"\0" * 4096)
    monkeypatch.delenv("BAXY_MIND_NGL", raising=False)
    monkeypatch.setattr(llm_startup, "free_vram_bytes", lambda: 64 * 1024 * 1024)

    with pytest.raises(LlmStartupFailure) as raised:
        llm_startup.require_vram_for(str(gguf), cpu_only=False)

    assert raised.value.cause == "vram_insuficiente"
    assert raised.value.report()["cause"] == "vram_insuficiente"


@pytest.mark.parametrize(
    ("free", "cpu_only", "layers"),
    [
        (8 * 1024 * 1024 * 1024, False, "99"),  # contracase: enough VRAM starts as before
        (None, False, "99"),  # no reading never blocks
        (0, True, "0"),  # CPU only never asks the GPU
        (0, False, "20"),  # partial offload is not the full model
    ],
)
def test_an_unmeasured_or_sufficient_vram_never_blocks(
    monkeypatch: pytest.MonkeyPatch, tmp_path, free, cpu_only: bool, layers: str
) -> None:
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"\0" * 4096)
    monkeypatch.setenv("BAXY_MIND_NGL", layers)
    asked: list[bool] = []

    def reading():
        asked.append(True)
        return free

    monkeypatch.setattr(llm_startup, "free_vram_bytes", reading)
    llm_startup.require_vram_for(str(gguf), cpu_only=cpu_only)
    assert asked == ([] if cpu_only or layers != "99" else [True])


def _bare_runtime() -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)
    runtime._request_deadline = None
    runtime._close_event = threading.Event()
    return runtime


def test_a_server_that_dies_while_warming_up_reports_its_exit_and_lines() -> None:
    runtime = _bare_runtime()
    process = MagicMock()
    process.poll.return_value = 3221225477
    process.returncode = 3221225477
    runtime._process = process
    runtime._endpoint = "http://127.0.0.1:9"
    runtime._server_stderr = StderrTail(iter([b"load_tensors: offloading 26 layers\n", CUDA_OOM.encode()]))

    with pytest.raises(LlmStartupFailure) as raised:
        runtime._wait_ready(5.0)

    failure = raised.value
    assert failure.cause == "vram_insuficiente"
    assert failure.exit_code == 3221225477
    assert failure.tail[-1].endswith("out of memory")
    assert "exit 3221225477" in str(failure)


def test_a_failed_warmup_keeps_its_cause_for_the_catalog() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._warmup_lock = threading.Lock()
    runtime._warmup_thread = None
    runtime._warmup_ready = threading.Event()
    runtime._warmup_done = threading.Event()
    runtime._ensure_started = MagicMock(
        side_effect=LlmStartupFailure("ram_insuficiente", "llama-server terminó (exit 1)", exit_code=1)
    )

    runtime.start_warmup()
    assert not runtime.wait_warmup(5.0)
    with pytest.raises(LlmStartupFailure) as raised:
        _require_catalog_llm_ready(runtime, timeout=1.0)
    assert raised.value.cause == "ram_insuficiente"
    assert raised.value.exit_code == 1


def test_a_timed_out_warmup_is_time() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._warmup_lock = threading.Lock()
    runtime._warmup_thread = None
    runtime._warmup_ready = threading.Event()
    runtime._warmup_done = threading.Event()
    runtime._ensure_started = MagicMock(side_effect=TimeoutError("llama-server no quedó listo"))

    runtime.start_warmup()
    assert not runtime.wait_warmup(5.0)
    assert runtime.startup_failure().cause == "tiempo"


def test_a_ready_model_starts_as_before() -> None:
    class ReadyRuntime:
        @staticmethod
        def wait_warmup(timeout: float) -> bool:
            return True

        @staticmethod
        def startup_failure():
            raise AssertionError("a ready model is never asked why it failed")

    _require_catalog_llm_ready(ReadyRuntime())
    _require_catalog_llm_ready(None)


def test_the_catalog_reply_keeps_its_code_and_adds_the_cause() -> None:
    failure = LlmStartupFailure(
        "proceso_salio", "llama-server terminó (exit 7)", exit_code=7, tail=("main: exiting",)
    )
    reply = _startup_failure_reply("12", failure)

    assert reply == {
        "type": "error",
        "id": "12",
        "code": "request_failed",
        "message": technical_failure_message("catalog.configure", "runtime"),
        "startup": {"cause": "proceso_salio", "exitCode": 7, "tail": ["main: exiting"]},
    }
    assert reply["message"] == "request_runtime_failure"


def test_an_unknown_cause_is_refused() -> None:
    with pytest.raises(ValueError):
        LlmStartupFailure("lo_que_sea", "x")


def test_the_apps_startup_line_is_not_a_reply_of_baxy_for_the_decider() -> None:
    from baxy_mind import operation_floor
    from baxy_mind.semantic import decider

    lines = operation_floor.floor_data()["mindStartup"]
    assert set(lines) == {"vram_insuficiente", "ram_insuficiente", "proceso_salio", "tiempo", "iniciando"}
    for line in lines.values():
        assert line["es"] and line["en"]
        assert decider._is_composition_failure(line["es"])
        assert decider._is_composition_failure(line["en"])
    assert not decider._is_composition_failure("Abrí Paint.")
