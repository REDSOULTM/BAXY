"""Compare upstream3857 alone atop the same215 observer; no installation."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXP = Path("D:/BAXYRuntime/experiments/voice/sherpa205")
SOURCE = EXP / "source"
BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "astra-normalize216"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-normalize216-private"
PRIVATE.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
def git(*args):
    return subprocess.check_output(["git", "-C", str(SOURCE), *args])
owners = ["sherpa-onnx/csrc/offline-recognizer-transducer-nemo-impl.h",
          "sherpa-onnx/csrc/offline-transducer-greedy-search-nemo-decoder.cc",
          "sherpa-onnx/csrc/math.cc", "sherpa-onnx/csrc/math-test.cc"]
assert git("diff", "--name-only").decode().splitlines() == [owners[0]]
before = {name: (SOURCE / name).read_bytes() for name in owners}
for name, content in before.items():
    (PRIVATE / (Path(name).name + ".before")).write_bytes(content)
upstream = read(OUT / "upstream.json")
assert upstream["merged"] and upstream["head"]["sha"] == "a0ba8800cf8580782a9cc9566659ff61f729d76d"
save(OUT / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "method": "Same215 observer plus exact merged upstream3857 math.cc/math-test.cc patch. Native near-constant/constant witnesses before/after; four exact214 recognition/feature controls, then broad controls without choosing by output. No epsilon/gain/sampler/model changes. External source restored; no install.",
    "upstreamHead": upstream["head"]["sha"], "mergeCommit": upstream["merge_commit_sha"],
    "upstreamPatchSha256": sha(OUT / "upstream.patch"),
    "before": {name: hashlib.sha256(value).hexdigest() for name, value in before.items()},
    "witnessSha256": sha(ROOT / "scratchpad/c03-normalize216.cpp"),
})
def witness(label):
    exe = PRIVATE / f"witness-{label}.exe"
    build = PRIVATE / f"witness-{label}.cmd"
    build.write_text(
        '@echo off\ncall "C:\\Program Files (x86)\\Microsoft Visual Studio\\2022\\BuildTools\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul\n'
        f'cl /nologo /O2 /EHsc /std:c++17 /I"{SOURCE}" /I"{EXP / "build/_deps/eigen-src"}" "{ROOT / "scratchpad/c03-normalize216.cpp"}" "{SOURCE / owners[2]}" /Fe:"{exe}" /Fo:"{PRIVATE}/"\n'
        'exit /b %errorlevel%\n', encoding="utf-8")
    with (OUT / f"WITNESS-{label}-BUILD.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(["cmd.exe", "/d", "/c", str(build)], stdout=log, stderr=subprocess.STDOUT, timeout=120)
    assert result.returncode == 0
    result = json.loads(subprocess.check_output([str(exe)], timeout=30))
    save(OUT / f"WITNESS-{label}.json", result)
    assert result["constantMax"] <= 1e-6
    assert (result["nearConstantMax"] > 1000) if label == "before" else (result["nearConstantMax"] < 100)

try:
    witness("before")
    git("apply", "--reverse", str(ROOT / "runtime_wheels/sherpa-nemo-stream-decoder.patch"))
    git("apply", str(BASE / "astra-native-trace215-retry/instrumentation.patch"))
    git("apply", "--check", str(OUT / "upstream.patch"))
    git("apply", str(OUT / "upstream.patch"))
    witness("after")
    (OUT / "combined-observer.patch").write_bytes(git("diff", "--", *owners))
    with (OUT / "BUILD.log").open("w", encoding="utf-8") as log:
        result = subprocess.run([
            "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe",
            "--build", str(EXP / "build"), "--config", "Release", "--target", "_sherpa_onnx", "-j", "2"],
            stdout=log, stderr=subprocess.STDOUT, timeout=600)
    assert result.returncode == 0
    bundle = EXP / "bundle-normalize216"
    bundle.mkdir(exist_ok=False)
    binaries = []
    for folder in [EXP / "build/bin/Release", EXP / "build/lib/Release"]:
        for path in folder.iterdir():
            if path.suffix.lower() in {".dll", ".pyd"}:
                target = bundle / path.name
                shutil.copy2(path, target)
                binaries.append({"path": str(target), "sha256": sha(target)})
    save(OUT / "BUILD_COMPLETE.json", {"exitCode": 0, "binaries": binaries})
finally:
    assert set(git("diff", "--name-only").decode().splitlines()) <= set(owners)
    for name, content in before.items():
        (SOURCE / name).write_bytes(content)
    save(OUT / "SOURCE_RESTORED.json", {name: sha(SOURCE / name) for name in owners})
print("Upstream normalization witness and observer build finished; external source restored.", flush=True)
