"""Original sidecar with timed thread diagnostics only; no monkeypatches."""
from pathlib import Path
import faulthandler
import os
import runpy
import json
import time
from baxy_mind.voice_output import NeuralSpeechOutput

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar168-private'
original_state = NeuralSpeechOutput._set_speaking
def observe_state(self, speaking):
    original_state(self, speaking)
    with (private/'tts-state.jsonl').open('a', encoding='utf-8') as state_log:
        state_log.write(json.dumps({'time':time.monotonic(), 'speaking':speaking, 'error':self.last_error, 'voice':self.voice_name})+'\n')
NeuralSpeechOutput._set_speaking = observe_state
with (private/'stacks168.log').open('w',encoding='utf-8') as log:
    faulthandler.dump_traceback_later(15,repeat=True,file=log)
    try:
        runpy.run_module('baxy_mind',run_name='__main__')
    finally:
        faulthandler.cancel_dump_traceback_later()
