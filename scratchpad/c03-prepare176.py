"""Prepare a native observer of AEC3 linear and residual stages, not a repair."""
from pathlib import Path
import hashlib
import json
import shutil
import datetime as dt

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-linear176'
out.mkdir(exist_ok=False)
original=Path('D:/BAXYRuntime/experiments/voice/webrtc174/source/pywebrtc_audio-0.2.0')
target=Path('D:/BAXYRuntime/experiments/voice/webrtc176')
target.mkdir(exist_ok=False)
source=target/'source'
shutil.copytree(original,source)
path=source/'bindings/webrtc_audio_bindings.cpp'
text=path.read_text(encoding='utf-8')
first=text.index('class EchoCanceller {')
last=text.index('class NoiseSuppressor',first)
block=text[first:last]
block=block.replace('    std::unique_ptr<webrtc::AudioBuffer> near_buf_;','    std::unique_ptr<webrtc::AudioBuffer> near_buf_;\n    std::unique_ptr<webrtc::AudioBuffer> linear_buf_;')
block=block.replace('webrtc::EchoCanceller3Config config;', 'webrtc::EchoCanceller3Config config;\n        config.filter.export_linear_aec_output = true;')
block=block.replace('aec_->ProcessCapture(near_buf_.get(), nullptr, false);','aec_->ProcessCapture(near_buf_.get(), linear_buf_.get(), false);')
anchor='        near_buf_ = std::make_unique<webrtc::AudioBuffer>('
assert block.count(anchor)==1
block=block.replace(anchor,'        linear_buf_ = std::make_unique<webrtc::AudioBuffer>(16000, num_channels, 16000, num_channels, 16000, num_channels);\n\n'+anchor)
anchor='    int get_stream_delay_ms() const'
assert block.count(anchor)==1
block=block.replace(anchor,'''    py::array_t<float> last_linear_frame() const {
        py::array_t<float> output(160 * num_channels_);
        buffer_to_float(linear_buf_.get(), 160, num_channels_, output.mutable_data());
        return output;
    }

    py::dict diagnostic_metrics() const {
        auto values = aec_->GetMetrics();
        py::dict result;
        result["echo_return_loss"] = values.echo_return_loss;
        result["echo_return_loss_enhancement"] = values.echo_return_loss_enhancement;
        result["delay_ms"] = values.delay_ms;
        result["active"] = aec_->ActiveProcessing();
        return result;
    }

'''+anchor)
text=text[:first]+block+text[last:]
anchor='        .def("reset", &EchoCanceller::reset)'
assert text.count(anchor)==1
text=text.replace(anchor,anchor+'\n        .def("last_linear_frame", &EchoCanceller::last_linear_frame)\n        .def("diagnostic_metrics", &EchoCanceller::diagnostic_metrics)')
path.write_text(text,encoding='utf-8')
(out/'PREREG.json').write_text(json.dumps({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
    'hypothesis':'Locate loss before or after residual suppression in failed mixed control174. No tuning: export upstream linear output and metrics from the same native call.',
    'method':'Local source build of downloaded0.2.0; set export_linear_aec_output=true solely for observation; same16k10ms defaultAEC. Compare final output to wheel174 before attributing stages; record build differences and preserve source.',
    'originalSourceSha256':hashlib.sha256((original/'bindings/webrtc_audio_bindings.cpp').read_bytes()).hexdigest(),
    'diagnosticSourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    'source':str(source),'controls':'Same174 native echo, synthetic near-only and mix; ASR raw/normalized on the same window. No physical playback, no product or runtime changes.',
    'rejectedOption':'conservative_initial_phase=true extends initial active-render duration from2.5s to5s and audibility confidence from0.8s to1.5s; not evidence of improved near speech. Do not tune by name.'},indent=2),encoding='utf-8')
print(str(source))
