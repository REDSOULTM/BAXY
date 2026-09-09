from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-voice139'
out.mkdir(exist_ok=False)
capture = (root / 'scratchpad/c03-capture-voice138.py').read_text(encoding='utf-8').replace('138', '139')
with (root / 'scratchpad/c03-capture-voice139.py').open('x', encoding='utf-8') as f:
    f.write(capture)
driver = (root / 'scratchpad/c03-voice138.py').read_text(encoding='utf-8').replace('138', '139')
observer = '''
import numpy as np
import sounddevice as sd
import baxy_mind.voice as voice_module
import baxy_mind.voice_aec as aec_module
original_stream = sd.InputStream
original_process = voice_module.EchoCanceller.process
original_vad = voice_module.SileroVad.process
original_resample = aec_module._resample
reads, processes, vads, callbacks = [], [], [], []
raw_blocks, clean_blocks, references, loop_blocks = [], [], [], []

class ObservedStream:
    def __init__(self, *args, **kwargs):
        self.inner = original_stream(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(self.inner, name)
    def __enter__(self):
        self.inner.__enter__()
        return self
    def __exit__(self, *args):
        return self.inner.__exit__(*args)
    def read(self, samples):
        result = self.inner.read(samples)
        loop = engine._loopback._stream
        reads.append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'monotonic':time.monotonic(), 'micTime':self.inner.time,
                      'micLatency':self.inner.latency, 'micReadAvailable':self.inner.read_available,
                      'loopTime':loop.get_time(), 'loopLatency':loop.get_input_latency()})
        return result

def observe_process(self, mic, reference):
    result = original_process(self, mic, reference)
    processes.append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'readIndex':len(reads)-1, 'callbacksSeen':len(callbacks)})
    raw_blocks.append(mic.copy()); references.append(reference.copy()); clean_blocks.append(result[0].copy())
    return result

def observe_vad(self, frame):
    result = original_vad(self, frame)
    vads.append({'probability':result, 'rms':float(np.sqrt(np.mean(frame**2)))})
    return result

def observe_resample(audio, rate):
    result = original_resample(audio, rate)
    callbacks.append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'monotonic':time.monotonic(), 'samples':len(result)})
    loop_blocks.append(result.copy())
    return result

sd.InputStream = ObservedStream
voice_module.EchoCanceller.process = observe_process
voice_module.SileroVad.process = observe_vad
aec_module._resample = observe_resample
'''
driver = driver.replace('engine = VoiceEngine(transcript, event)', observer+'\nengine = VoiceEngine(transcript, event)')
driver = driver.replace('    engine.shutdown()\n', '''    engine.shutdown()
    sd.InputStream = original_stream
    voice_module.EchoCanceller.process = original_process
    voice_module.SileroVad.process = original_vad
    aec_module._resample = original_resample
    np.savez_compressed(private / 'timing139.npz', raw=raw_blocks, clean=clean_blocks,
                        reference=references, loop=np.concatenate(loop_blocks) if loop_blocks else np.array([]))
    (private / 'timing139.json').write_text(json.dumps({'reads':reads,'processes':processes,
        'vads':vads,'callbacks':callbacks},indent=2),encoding='utf-8')
    print(json.dumps({'reads':len(reads),'processes':len(processes),'callbacks':len(callbacks)}),flush=True)
''')
with (root / 'scratchpad/c03-voice139.py').open('x', encoding='utf-8') as f:
    f.write(driver)
sources = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in [
    'src/baxy_mind/voice.py','src/baxy_mind/voice_aec.py','src/baxy_mind/speex_aec.py','assets.manifest.json']}
prereg = {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':sources,
          'phases':['direct'],'text':'The file read failed because the content is invalid UTF-8.',
          'method':'Observe integrated136 exact AEC pairs/clean/VAD, microphone stream clock/latency/backlog and loopback callback blocks. Wrappers return original values; no shadow VAD or candidate modifications. Actual physical output, private capture and no transcript routing. Instrumentation can affect timing, so this is diagnostic.',
          'hypothesis':'138 fails while134 shadowed prototype passed despite137 DSP bit parity. Determine whether latest512 repeats/skips reference and whether reference is causal relative to microphone.'}
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
print('139 prepared; no playback yet.')
