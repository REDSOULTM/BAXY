"""Build an isolated native observer, restoring external source in finally."""
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
OUT = ROOT / "artifacts/comprobaciones/C03/astra-native-trace215-retry"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-native-trace215-retry-private"
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
owners = ["sherpa-onnx/csrc/offline-recognizer-transducer-nemo-impl.h",
          "sherpa-onnx/csrc/offline-transducer-greedy-search-nemo-decoder.cc"]
before = {name: (SOURCE / name).read_bytes() for name in owners}
for name, content in before.items():
    (PRIVATE / (Path(name).name + ".before")).write_bytes(content)
expected_patch = (ROOT / "runtime_wheels/sherpa-nemo-stream-decoder.patch").read_bytes()
patch = subprocess.check_output(["git", "-C", str(SOURCE), "diff", "--", owners[0]])
assert patch == expected_patch
assert not subprocess.check_output(["git", "-C", str(SOURCE), "diff", "--", owners[1]])

header = before[owners[0]].decode()
marker = '    Ort::Value x = PadSequence(model_->Allocator(), features_pointer, 0);'
assert header.count(marker) == 1
header = header.replace(marker, '''    const std::string trace_prefix = ss[0]->GetOption("baxy_trace_prefix");
    const auto dump_tensor = [&trace_prefix](const Ort::Value &tensor, const char *stage) {
      if (trace_prefix.empty()) return;
      auto info = tensor.GetTensorTypeAndShapeInfo();
      auto shape = info.GetShape();
      std::ofstream dimensions(trace_prefix + "." + stage + ".shape");
      for (auto d : shape) dimensions << d << " ";
      std::ofstream binary(trace_prefix + "." + stage + ".f32", std::ios::binary);
      binary.write(reinterpret_cast<const char *>(tensor.GetTensorData<float>()),
                   info.GetElementCount() * sizeof(float));
      if (!dimensions || !binary) throw std::runtime_error("diagnostic_dump_failed");
    };
''' + marker + '\n    dump_tensor(x, "features");')
marker = '    Ort::Value encoder_out = Transpose12(model_->Allocator(), &t[0]);'
assert header.count(marker) == 1
header = header.replace(marker, marker + '\n    dump_tensor(encoder_out, "encoder");')
decoder = before[owners[1]].decode().replace("\r\n", "\n")
decoder = decoder.replace('#include <iterator>', '#include <iterator>\n#include <cmath>\n#include <fstream>\n#include "sherpa-onnx/csrc/offline-stream.h"')
old = '''static OfflineTransducerDecoderResult DecodeOneTDT(
    const float *p, int32_t num_rows, int32_t num_cols,
    OfflineTransducerNeMoModel *model, float blank_penalty) {'''
new = '''static OfflineTransducerDecoderResult DecodeOneTDT(
    const float *p, int32_t num_rows, int32_t num_cols,
    OfflineTransducerNeMoModel *model, float blank_penalty, OfflineStream *trace_stream) {
  const std::string trace_prefix = trace_stream ? trace_stream->GetOption("baxy_trace_prefix") : "";
  std::ofstream trace;
  if (!trace_prefix.empty()) {
    trace.open(trace_prefix + ".joiner.tsv");
    trace.precision(9);
    trace << "t\\ty\\tskip\\tvocab\\tblank_logit\\tbest_nonblank\\tnonfinite\\n";
  }'''
assert decoder.count(old) == 1
decoder = decoder.replace(old, new)
marker = '''    if (y != blank_id) {
      ans.tokens.push_back(y);
      ans.timestamps.push_back(t);
      ans.durations.push_back(skip);'''
assert decoder.count(marker) == 1
decoder = decoder.replace(marker, '''    if (trace.is_open()) {
      int nonfinite = 0;
      for (int j = 0; j < output_size; ++j) nonfinite += !std::isfinite(p_logit[j]);
      trace << t << "\\t" << y << "\\t" << skip << "\\t" << vocab_size << "\\t"
            << p_logit[blank_id] << "\\t"
            << *std::max_element(token_logits, token_logits + blank_id) << "\\t"
            << nonfinite << "\\n";
    }
''' + marker)
decoder = decoder.replace('OfflineStream ** /*ss = nullptr*/, int32_t /*n= 0*/)',
                          'OfflineStream **ss, int32_t n)')
old = 'ans[i] = DecodeOneTDT(this_p, this_len, dim2, model_, blank_penalty_);'
assert decoder.count(old) == 1
decoder = decoder.replace(old, 'ans[i] = DecodeOneTDT(this_p, this_len, dim2, model_, blank_penalty_, (ss && i < n) ? ss[i] : nullptr);')
modified = {owners[0]: header.encode(), owners[1]: decoder.encode()}
save(OUT / "PREREG.json", {
    "utc": datetime.now(timezone.utc).isoformat(), "scriptSha256": sha(Path(__file__)),
    "method": "Observation-only external native build based on207 patch. Dump feature/encoder float tensors and TDT joiner choices to per-stream prefix. Four exact214 windows; assert previous native texts unchanged. Do not install. Restore exact external source after build, no tuning/inference changes.",
    "before": {name: hashlib.sha256(value).hexdigest() for name, value in before.items()},
    "instrumented": {name: hashlib.sha256(value).hexdigest() for name, value in modified.items()},
    "inputs": json.loads((ROOT / "artifacts/comprobaciones/C03/astra-native-boundary214/PREREG.json").read_text(encoding="utf-8"))["inputs"],
})
try:
    for name, content in modified.items():
        (SOURCE / name).write_bytes(content)
    (OUT / "instrumentation.patch").write_bytes(subprocess.check_output(["git", "-C", str(SOURCE), "diff", "--", *owners]))
    with (OUT / "BUILD.log").open("w", encoding="utf-8") as log:
        run = subprocess.run([
            "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe",
            "--build", str(EXP / "build"), "--config", "Release", "--target", "_sherpa_onnx", "-j", "2"],
            stdout=log, stderr=subprocess.STDOUT, timeout=600)
    assert run.returncode == 0, run.returncode
    bundle = EXP / "bundle-trace215"
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
    restored = {}
    for name, content in before.items():
        assert (SOURCE / name).read_bytes() == modified[name]
        (SOURCE / name).write_bytes(content)
        restored[name] = sha(SOURCE / name)
    save(OUT / "SOURCE_RESTORED.json", restored)
print("Isolated observer built; external sources restored; installed runtime unchanged.", flush=True)
