"""Read-only Windows endpoint AEC capability probe; never starts audio."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/astra-aec-capability210"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-aec-capability210-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
source = ROOT / "scratchpad/c03-aec-capability210.cpp"
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

save(OUT / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(),
    "purpose": "Same six initialized streams as 209, changing only props.Options to RAW; compare effect list and HRESULTs",
    "roles": ["console", "multimedia", "communications"],
    "categories": ["other", "communications"],
    "rawRequested": True, "audioStarted": False, "recording": False, "globalSettingsChanged": False,
    "sourceSha256": digest(source), "driverSha256": digest(Path(__file__)),
    "source": "https://github.com/microsoft/Windows-classic-samples/blob/main/Samples/AcousticEchoCancellation/cpp/AECCapture.cpp",
    "productSourceSha256": digest(ROOT / "src/baxy_mind/voice_capture.py"),
    "interpretation": "Services/effects describe initialized endpoint streams, not physical cancellation performance. Missing services preclude this integration route on that endpoint."
})
build = PRIVATE / "build.cmd"
exe = PRIVATE / "probe210.exe"
build.write_text(
    '@echo off\ncall "C:\\Program Files (x86)\\Microsoft Visual Studio\\2022\\BuildTools\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul\n'
    f'cl /nologo /std:c++17 /EHsc /W4 /D_WIN32_WINNT=0x0A00 "{source}" /Fe:"{exe}" /Fo:"{PRIVATE / "probe210.obj"}" /link ole32.lib uuid.lib\n'
    'exit /b %errorlevel%\n', encoding="utf-8")
with (OUT / "BUILD.log").open("w", encoding="utf-8") as log:
    compilation = subprocess.run(["cmd.exe", "/d", "/c", str(build)], stdout=log, stderr=subprocess.STDOUT, timeout=120)
if compilation.returncode:
    raise RuntimeError(f"compilation failed {compilation.returncode}")
run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
(PRIVATE / "STDOUT.jsonl").write_text(run.stdout, encoding="utf-8")
(OUT / "STDERR.txt").write_text(run.stderr, encoding="utf-8")
run.check_returncode()
rows = [json.loads(line) for line in run.stdout.splitlines()]
assert len(rows) == 6
for row in rows:
    if "endpointId" in row:
        row["endpointIdSha256"] = hashlib.sha256(row.pop("endpointId").encode()).hexdigest()
save(OUT / "RESULTS.json", {"rows": rows, "processExitCode": run.returncode,
     "exeSha256": digest(exe), "privateStdoutSha256": digest(PRIVATE / "STDOUT.jsonl")})
save(OUT / "COMPLETE.json", {"utc": datetime.now(timezone.utc).isoformat(), "exitCode": 0})
print(json.dumps(rows))
