"""Experimental DTLN streaming adapter; no imports from product point here."""
from pathlib import Path
import hashlib
import json
import sys
import threading
import numpy as np

sys.path.insert(0, 'D:/BAXYRuntime/experiments/voice/dtln179/python')
from ai_edge_litert.interpreter import Interpreter


class EchoCanceller:
    def __init__(self, units=128):
        if units not in (128, 512):
            raise ValueError('unsupported_diagnostic_model')
        stage = 179 if units == 128 else 180
        self.library_path = Path(f'D:/BAXYRuntime/experiments/voice/dtln{stage}')
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / f'artifacts/comprobaciones/C03/astra-dtln{stage}/DOWNLOADS.json').read_text(encoding='utf-8'))
        models = [self.library_path / f'dtln_aec_{units}_{i}.tflite' for i in (1, 2)]
        hashes = []
        for path in models:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == next(r['sha256'] for r in manifest if Path(r['path']) == path)
            hashes.append(actual)
        self.sha256 = hashlib.sha256(''.join(hashes).encode('ascii')).hexdigest()
        self._owner = threading.get_ident()
        self._models = [Interpreter(model_path=str(p), num_threads=1) for p in models]
        for model in self._models:
            model.allocate_tensors()
        self._inputs = [m.get_input_details() for m in self._models]
        self._outputs = [m.get_output_details() for m in self._models]
        self._states = [np.zeros(details[1]['shape'], np.float32) for details in self._inputs]
        self._near = np.zeros(512, np.float32)
        self._far = np.zeros(512, np.float32)
        self._out = np.zeros(512, np.float32)
        self._mic_delay = np.zeros(384, np.float32)
        self._previous_reference = None
        # Match author's three prepended zero hops, whose outputs are discarded.
        for _ in range(3):
            self._hop(np.zeros(128, np.float32), np.zeros(128, np.float32))

    def _check(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError('echo_canceller_wrong_thread')
        if self._models is None:
            raise RuntimeError('echo_canceller_closed')

    def _hop(self, near, far):
        self._near[:-128] = self._near[128:]
        self._near[-128:] = near
        self._far[:-128] = self._far[128:]
        self._far[-128:] = far
        spectrum = np.fft.rfft(np.squeeze(self._near)).astype('complex64')
        magnitude = np.abs(spectrum).reshape(1, 1, -1).astype('float32')
        far_spectrum = np.fft.rfft(np.squeeze(self._far)).astype('complex64')
        far_magnitude = np.abs(far_spectrum).reshape(1, 1, -1).astype('float32')
        one, two = self._models
        one.set_tensor(self._inputs[0][0]['index'], magnitude)
        one.set_tensor(self._inputs[0][2]['index'], far_magnitude)
        one.set_tensor(self._inputs[0][1]['index'], self._states[0])
        one.invoke()
        mask = one.get_tensor(self._outputs[0][0]['index'])
        self._states[0] = one.get_tensor(self._outputs[0][1]['index'])
        estimated = np.fft.irfft(spectrum * mask).reshape(1, 1, -1).astype('float32')
        two.set_tensor(self._inputs[1][1]['index'], self._states[1])
        two.set_tensor(self._inputs[1][0]['index'], estimated)
        two.set_tensor(self._inputs[1][2]['index'], self._far.reshape(1, 1, -1).astype('float32'))
        two.invoke()
        block = two.get_tensor(self._outputs[1][0]['index'])
        self._states[1] = two.get_tensor(self._outputs[1][1]['index'])
        self._out[:-128] = self._out[128:]
        self._out[-128:] = 0
        self._out += np.squeeze(block)
        return self._out[:128].copy()

    def process(self, microphone, reference):
        self._check()
        near = np.asarray(microphone, dtype=np.float32).reshape(-1)
        history = np.asarray(reference, dtype=np.float32).reshape(-1)
        if near.size != 512 or history.size != 4512:
            raise ValueError('echo_canceller_frame_size_invalid')
        if not np.isfinite(near).all() or not np.isfinite(history).all():
            raise ValueError('echo_canceller_nonfinite_audio')
        far = history[-512:] / 32768
        clean = np.concatenate([self._hop(near[i:i+128], far[i:i+128]) for i in range(0,512,128)])
        if not np.isfinite(clean).all() or np.max(np.abs(clean)) > 1:
            raise RuntimeError('echo_canceller_output_invalid')
        raw = np.r_[self._mic_delay, near]
        if self._previous_reference is None:
            self._previous_reference = np.r_[np.zeros(512, np.float32), history[:-512]]
        paired_history = np.r_[self._previous_reference, history[-512:]][:-384][-4512:]
        self._mic_delay = raw[512:].copy()
        self._previous_reference = history.copy()
        return clean, raw[:512] * 32768, paired_history

    def close(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError('echo_canceller_wrong_thread')
        self._models = None
