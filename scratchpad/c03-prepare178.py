"""One upstream-informed AEC gain assumption contrast, same acceptance criteria."""
from pathlib import Path
import hashlib
import json
import shutil
import datetime as dt

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-gain178'
out.mkdir(exist_ok=False)
original=Path('D:/BAXYRuntime/experiments/voice/webrtc176/source')
folder=Path('D:/BAXYRuntime/experiments/voice/webrtc178')
folder.mkdir(exist_ok=False)
source=folder/'source'
shutil.copytree(original,source)
path=source/'bindings/webrtc_audio_bindings.cpp'
text=path.read_text(encoding='utf-8')
anchor='        config.filter.export_linear_aec_output = true;'
assert text.count(anchor)==2
text=text.replace(anchor,anchor+'\n        config.ep_strength.default_gain = 0.1f;')
path.write_text(text,encoding='utf-8')
library=Path('D:/BAXYRuntime/experiments/voice/webrtc176/build/vendor/webrtc_audio/Release/webrtc_audio_static.lib')
assert library.is_file()
cmake=source/'CMakeLists.txt'
text=cmake.read_text(encoding='utf-8')
assert text.count('add_subdirectory(vendor/webrtc_audio)')==1
text=text.replace('add_subdirectory(vendor/webrtc_audio)',f'add_library(webrtc_audio_static STATIC IMPORTED)\nset_target_properties(webrtc_audio_static PROPERTIES IMPORTED_LOCATION "{library.as_posix()}")')
cmake.write_text(text,encoding='utf-8')
(out/'PREREG.json').write_text(json.dumps({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
 'difference':'Only EchoCanceller ep_strength.default_gain from1.0 to0.1; export of linear output/metrics identical176. Reuse exactly176 native static library; rebuild bindings only. No VAD/energy/count/echo guard threshold changes.',
 'hypothesis':'Before usable linear adaptation, conservative estimated echo power can mask near speech. Compare modern upstream low-gain assumption without per-recording fit.',
 'primary':'https://webrtc.googlesource.com/src/+/refs/heads/main/modules/audio_processing/aec3/residual_echo_estimator.cc',
 'primaryBlob':'29776e88e941905af90d88011488fba25aa0dbc2','consulted':'2026-09-07',
 'primaryMechanism':'GetEarlyReflectionsDefaultModeGain/GetLateReflectionsDefaultModeGain use0.1 in named field trials. Older extraction has one common ep_strength.default_gain, squared for nonlinear R2. This is a hypothesis transfer, not identical current upstream nor a default recommendation.',
 'staticLibrarySha256':hashlib.sha256(library.read_bytes()).hexdigest(),'bindingSha256':hashlib.sha256(path.read_bytes()).hexdigest(),
 'criteria':'Same five174 signal controls plus linear/final near transcriptions. All outputs retained. Echo must remain rejected and near words preserved; do not adopt a zero-echo/missing-near tradeoff. If insufficient, no gain sweep.',
 'limits':'Offline synthetic mixed control, not human/physical acceptance; registered runtime and product source unchanged.'},indent=2),encoding='utf-8')
print('178 prepared; native implementation reused by hash, one config difference.')
