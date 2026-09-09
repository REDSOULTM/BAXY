"""Experimental DTLN128 binding, same sidecar and state-only observer."""
from pathlib import Path
import faulthandler
import os
import runpy
import json
import time
from datetime import datetime, timezone
from baxy_mind.voice_output import NeuralSpeechOutput
import baxy_mind.voice as voice_module
from dtln_stream182 import EchoCanceller
voice_module.EchoCanceller = EchoCanceller
voice_module.resolve_echo_canceller_library = lambda: Path('D:/BAXYRuntime/experiments/voice/dtln179')

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar185-private'
original_state = NeuralSpeechOutput._set_speaking
def observe_state(self, speaking):
    original_state(self, speaking)
    with (private/'tts-state.jsonl').open('a', encoding='utf-8') as state_log:
        state_log.write(json.dumps({'time':time.monotonic(), 'utc':datetime.now(timezone.utc).isoformat(), 'speaking':speaking, 'error':self.last_error, 'voice':self.voice_name})+'\n')
NeuralSpeechOutput._set_speaking = observe_state
import inspect
import numpy as np
from baxy_mind.voice import VoiceEngine

original_emit = VoiceEngine._emit
observed_barge = False
def observe_emit(self, event, **fields):
    global observed_barge
    original_emit(self, event, **fields)
    if event != 'barge_in' or observed_barge:
        return
    observed_barge = True
    caller = inspect.currentframe().f_back
    try:
        values = caller.f_locals
        arrays = {name: np.asarray(values[name]).copy() for name in ('mono', 'echo_microphone', 'echo_reference', 'history', 'frame')}
        metadata = {'time': time.monotonic(), 'caller': caller.f_code.co_name, 'referenceCursor': values['reference_cursor'], 'micAdcTime': values['stream'].adc_time, 'probability': float(values['probability']), 'energy': float(values['energy']), 'noiseFloor': float(values['noise_floor']), 'bargeFrames': values['barge_frames']}
        with self._loopback._condition:
            arrays['loopback_ring'] = self._loopback._ring.copy()
            metadata.update(loopbackWritten=self._loopback._written, loopbackOrigin=self._loopback._origin_time, loopbackError=self._loopback.last_error)
        canceller = values['canceller']
        for name in ('_near', '_far', '_out', '_mic_delay', '_previous_reference'):
            arrays['dtln'+name] = np.asarray(getattr(canceller, name)).copy()
        for index, state in enumerate(canceller._states):
            arrays[f'dtln_state{index}'] = state.copy()
        metadata.update(aecSha256=canceller.sha256, utc=datetime.now(timezone.utc).isoformat())
        np.savez(private/'barge185.npz', **arrays)
        (private/'barge185.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    finally:
        del caller
VoiceEngine._emit = observe_emit

with (private/'stacks185.log').open('w',encoding='utf-8') as log:
    faulthandler.dump_traceback_later(15,repeat=True,file=log)
    try:
        runpy.run_module('baxy_mind',run_name='__main__')
    finally:
        faulthandler.cancel_dump_traceback_later()
