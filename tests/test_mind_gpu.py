"""Encargo 8 (2026-11-02): BAXY on an AMD or Intel GPU (Vulkan) as on an NVIDIA one (CUDA). The installation picks the
llama-server folder by the GPU's PCI vendor, the mind verifies the folder's GPU backend by SHA-256 and starts the server
with that backend's settings. The machines here are simulated: PCI ids as Windows gives them."""
import hashlib
import json
import re
from pathlib import Path

import pytest

from baxy_mind import gpu, llm_server
from baxy_mind.llm_server import declared_backend

NVIDIA = r"PCI\VEN_10DE&DEV_2520&SUBSYS_00000000&REV_A1\4&0000000&0&0009"
AMD_IGPU = r"PCI\VEN_1002&DEV_1638&SUBSYS_00000000&REV_C5\4&0000000&0&0041"
AMD = r"PCI\VEN_1002&DEV_7480&SUBSYS_00000000&REV_CF\6&0000000&0&00000019"
INTEL = r"PCI\VEN_8086&DEV_A780&SUBSYS_00000000&REV_04\3&0000000&0&10"
VIRTUAL = r"ROOT\DISPLAY\0000"


@pytest.mark.parametrize("adapters,backend", [
    ([NVIDIA], "cuda"),
    ([AMD_IGPU, NVIDIA, VIRTUAL], "cuda"),  # a laptop's integrated GPU beside the NVIDIA one: CUDA
    ([AMD], "vulkan"),
    ([AMD_IGPU, AMD], "vulkan"),
    ([INTEL], "vulkan"),
    ([INTEL, AMD], "vulkan"),
    ([VIRTUAL], "cpu"),  # only virtual displays: no GPU to compute on
    ([], "cpu"),
])
def test_the_backend_follows_the_gpus_pci_vendor(adapters: list[str], backend: str) -> None:
    assert gpu.backend(adapters) == backend


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def builds(tmp_path: Path) -> Path:
    declaration = {"schema": "baxy.llama-server.v1", "files": ["llama-server.exe"], "builds": {"stock": {
        "sha256": {"llama-server.exe": _sha(b"stock")},
        "backends": {"cuda": {"ggml-cuda.dll": _sha(b"cuda")}, "vulkan": {"ggml-vulkan.dll": _sha(b"vulkan")}},
    }}}
    path = tmp_path / "llama_server.v1.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")
    return path


def _folder(tmp_path: Path, name: str, contents: dict[str, bytes]) -> str:
    folder = tmp_path / name
    folder.mkdir()
    for file, data in {"llama-server.exe": b"stock", "ggml-cpu-x64.dll": b"cpu", **contents}.items():
        (folder / file).write_bytes(data)
    return str(folder / "llama-server.exe")


def test_the_folders_gpu_backend_is_its_declared_dll(tmp_path: Path, builds: Path) -> None:
    assert declared_backend(_folder(tmp_path, "c", {"ggml-cuda.dll": b"cuda"}), "stock", builds) == "cuda"
    assert declared_backend(_folder(tmp_path, "v", {"ggml-vulkan.dll": b"vulkan"}), "stock", builds) == "vulkan"
    assert declared_backend(_folder(tmp_path, "n", {}), "stock", builds) == "cpu"


def test_an_undeclared_backend_dll_does_not_start(tmp_path: Path, builds: Path) -> None:
    server = _folder(tmp_path, "other", {"ggml-vulkan.dll": b"another vulkan"})
    with pytest.raises(RuntimeError, match=r"ggml-vulkan\.dll [0-9a-f]{12} is not stock's"):
        declared_backend(server, "stock", builds)


def test_a_folder_of_two_gpu_backends_does_not_start(tmp_path: Path, builds: Path) -> None:
    # llama.cpp would load both and use the first that sees the GPU: the settings would not be the backend's.
    server = _folder(tmp_path, "both", {"ggml-cuda.dll": b"cuda", "ggml-vulkan.dll": b"vulkan"})
    with pytest.raises(RuntimeError, match="two GPU backends"):
        declared_backend(server, "stock", builds)


def test_every_build_declares_the_cuda_and_vulkan_dlls_of_b11609() -> None:
    declaration = json.loads(llm_server.BUILDS.read_text(encoding="utf-8"))
    for build in declaration["builds"].values():
        assert build["backends"] == {
            "cuda": {"ggml-cuda.dll": "7b01bba16c434444de9ea7d58303ab5aee84e369da5fc6b06f49c96fd6a4279e"},
            "vulkan": {"ggml-vulkan.dll": "7f11df4165a0d64d3da78219256c077505fc3617027de69642204e87843ed73a"}}


def test_the_installation_registers_the_folder_of_the_machines_backend(tmp_path: Path, builds: Path) -> None:
    cuda = _folder(tmp_path, "cuda", {"ggml-cuda.dll": b"cuda"})
    vulkan = _folder(tmp_path, "vulkan", {"ggml-vulkan.dll": b"vulkan"})
    chosen = gpu.choose([AMD], [cuda, vulkan], builds)
    assert (chosen["backend"], chosen["server"]) == ("vulkan", vulkan)
    chosen = gpu.choose([AMD_IGPU, NVIDIA], [cuda, vulkan], builds)
    assert (chosen["backend"], chosen["server"]) == ("cuda", cuda)


def test_no_folder_of_the_machines_backend_is_said_with_each_folders(tmp_path: Path, builds: Path) -> None:
    cuda = _folder(tmp_path, "cuda", {"ggml-cuda.dll": b"cuda"})
    broken = _folder(tmp_path, "broken", {"ggml-vulkan.dll": b"not the declared one"})
    chosen = gpu.choose([AMD], [cuda, broken], builds)
    assert chosen["backend"] == "vulkan" and chosen["server"] is None
    assert chosen["servers"][cuda] == "cuda"
    assert "is not stock's" in chosen["servers"][broken]


def test_the_command_prints_the_choice(tmp_path: Path, builds: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(llm_server, "BUILDS", builds)
    vulkan = _folder(tmp_path, "vulkan", {"ggml-vulkan.dll": b"vulkan"})
    assert gpu.main(["--pci", AMD, "--pci", VIRTUAL, vulkan]) == 0
    assert json.loads(capsys.readouterr().out)["server"] == vulkan
    assert gpu.main(["--pci", NVIDIA, vulkan]) == 1  # nothing to register: the registration fails with the reply


def _command(monkeypatch, tmp_path: Path, **kwargs) -> list[str]:
    launched: list[list[str]] = []

    class Process:
        def __init__(self, command, **_kwargs) -> None:
            launched.append(command)

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(llm_server.subprocess, "Popen", Process)
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **_k: type("T", (), {"start": lambda self: None})())
    llm_server.LlmServer("model.gguf", "llama-server.exe", **kwargs).start()
    return launched[0]


def _attention(command: list[str]) -> tuple[str, str, str]:
    return command[command.index("-ctk") + 1], command[command.index("-ctv") + 1], command[command.index("-fa") + 1]


@pytest.mark.parametrize("backend", ["cuda", "cpu", "vulkan"])
def test_the_cache_is_q8_0_with_flash_attention_on_every_backend(tmp_path: Path, monkeypatch, backend: str) -> None:
    # uso-60: Vulkan's f16 cache (encargo 8) did not fit the 4 GB with the prefix (llm_server.kv_types).
    monkeypatch.delenv("BAXY_RENEW_KV", raising=False)
    assert _attention(_command(monkeypatch, tmp_path, backend=backend)) == ("q8_0", "q8_0", "on")


def test_baxy_renew_kv_still_decides_the_cache_on_vulkan(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_RENEW_KV", "q8_0")
    assert _attention(_command(monkeypatch, tmp_path, backend="vulkan")) == ("q8_0", "q8_0", "on")
    monkeypatch.setenv("BAXY_RENEW_KV", "f16")  # and llama.cpp checks the GPU runs the attention
    assert _attention(_command(monkeypatch, tmp_path, backend="vulkan")) == ("f16", "f16", "auto")


def test_the_mind_starts_the_server_with_its_folders_backend(tmp_path: Path, monkeypatch) -> None:
    from baxy_mind import __main__ as sidecar

    given: dict = {}

    class Server:
        def __init__(self, *args, **kwargs) -> None:
            given.update(kwargs)
            raise RuntimeError("stop here")

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", str(tmp_path / "llama-server.exe"))
    monkeypatch.setattr(sidecar, "declared_build", lambda server: "b11609")
    monkeypatch.setattr(sidecar, "declared_backend", lambda server, build: "vulkan")
    monkeypatch.setattr(sidecar, "LlmServer", Server)
    assert sidecar.main() == 2
    assert given["backend"] == "vulkan"


@pytest.mark.parametrize("wanted,told", [("vulkan", False), ("cuda", True), ("", False)])
def test_a_folder_that_is_not_the_backend_the_app_chose_does_not_start(monkeypatch, capsys, tmp_path, wanted, told) -> None:
    """uso-101: llama-server.exe is the same file in both folders of a store's package, so its hash does not tell the
    backend; the App says which it chose (BAXY_MIND_LLAMA_BACKEND) and the mind holds the folder's DLL to it."""
    from baxy_mind import __main__ as sidecar

    reached = []

    class Server:
        def __init__(self, *args, **kwargs) -> None:
            reached.append(kwargs["backend"])
            raise RuntimeError("stop here")

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", str(tmp_path / "llama-server.exe"))
    monkeypatch.setenv("BAXY_MIND_LLAMA_BACKEND", wanted)
    monkeypatch.delenv("BAXY_MIND_LLAMA_REMOTE", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda server: "b11609")
    monkeypatch.setattr(sidecar, "declared_backend", lambda server, build: "vulkan")
    monkeypatch.setattr(sidecar, "LlmServer", Server)
    assert sidecar.main() == 2
    assert reached == ([] if told else ["vulkan"])
    assert ("is vulkan, not the cuda" in capsys.readouterr().err) is told


def test_the_app_and_the_installation_read_the_same_vendors() -> None:
    """The store's package picks in the App (MindRuntimeDiscovery.GpuBackends, before Python starts), the installation
    here (gpu.BACKENDS): the same vendors, the same backends."""
    source = (Path(__file__).parent.parent / "src" / "Baxy.App" / "MindRuntimeDiscovery.cs").read_text(encoding="utf-8")
    table = source[source.index("GpuBackends ="):]
    table = table[:table.index("};")]
    found = {vendor.lower(): backend for vendor, backend in re.findall(r'\[0x([0-9A-Fa-f]{4})\] = "(\w+)"', table)}
    assert found == gpu.BACKENDS
