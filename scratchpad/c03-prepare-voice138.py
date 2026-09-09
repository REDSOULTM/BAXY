from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-voice138'
out.mkdir(exist_ok=False)
for original, target in [('c03-voice125.py', 'c03-voice138.py'), ('c03-capture-voice125.py', 'c03-capture-voice138.py')]:
    text = (root / 'scratchpad' / original).read_text(encoding='utf-8').replace('125', '138')
    with (root / 'scratchpad' / target).open('x', encoding='utf-8') as f:
        f.write(text)
sources = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in [
    'src/baxy_mind/voice.py', 'src/baxy_mind/voice_output.py', 'src/baxy_mind/piper_tts.py',
    'src/baxy_mind/voice_aec.py', 'src/baxy_mind/speex_aec.py', 'assets.manifest.json']}
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'sources':sources,
          'phases':['direct'], 'text':'The file read failed because the content is invalid UTF-8.',
          'method':'Unmodified integrated source136 VoiceEngine/Piper, actual speaker/microphone/loopback, same consumed phrase and direct mode134. No wrappers, PCM injection, shadow VAD, App/LLM/Core or transcript routing. Captures private; volume restore in finally.',
          'criteria':'Actual complete audio with no own barge-in, native AEC active/hash reported during ready and inactive after shutdown. Compare to134 without conflating with UI or human near-voice acceptance.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, indent=2), encoding='utf-8')
print('138 prepared; no playback yet.')
