"""Experimental DTLN128 binding, same sidecar and state-only observer."""
from pathlib import Path
import faulthandler
import os
import runpy
import json
import time
from baxy_mind.voice_output import NeuralSpeechOutput
import baxy_mind.voice as voice_module
from dtln_stream182 import EchoCanceller
voice_module.EchoCanceller = EchoCanceller
voice_module.resolve_echo_canceller_library = lambda: Path('D:/BAXYRuntime/experiments/voice/dtln179')

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar183-private'
original_state = NeuralSpeechOutput._set_speaking
def observe_state(self, speaking):
    original_state(self, speaking)
    with (private/'tts-state.jsonl').open('a', encoding='utf-8') as state_log:
        state_log.write(json.dumps({'time':time.monotonic(), 'speaking':speaking, 'error':self.last_error, 'voice':self.voice_name})+'\n')
NeuralSpeechOutput._set_speaking = observe_state
with (private/'stacks183.log').open('w',encoding='utf-8') as log:
    faulthandler.dump_traceback_later(15,repeat=True,file=log)
    try:
        runpy.run_module('baxy_mind',run_name='__main__')
    finally:
        faulthandler.cancel_dump_traceback_later()
