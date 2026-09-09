from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-voice123'
out.mkdir(exist_ok=False)
capture = (root / 'scratchpad/c03-capture-audio121.py').read_text(encoding='utf-8')
capture = capture.replace('astra-audio121', 'astra-voice123').replace('C03-audio121-private', 'C03-voice123-private')
with (root / 'scratchpad/c03-capture-voice123.py').open('x', encoding='utf-8', newline='\n') as f:
    f.write(capture)
def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'method': 'Source119 unchanged. Actual VoiceEngine/Piper and physical speakers, default '
                    'mic+loopback privately captured. Same consumed English response in off-before, '
                    'direct, off-after phases, one VoiceEngine with normal start/stop. No App/LLM/Core '
                    'effects; transcripts only stored privately and never routed. Compare speaking '
                    'duration and actual emitted barge_in events. Do not disable/change guards; '
                    'mode difference is diagnostic isolation, not acceptance with voice off.',
          'text': 'The file read failed because the content is invalid UTF-8.',
          'phases': ['off-before', 'direct', 'off-after'],
          'hypothesis': 'PCM120 correct but physical121 incomplete: own echo may trigger barge-in '
                        'or playback may fail independently. Observe before changing either.',
          'heritage': 'biblioteca/gemma4-agent/documentacion/01_arquitectura/design/barge_in.md:1-80, '
                      '2026-06-04 design-only, not measured solution. Current voice.py:2348-2360 '
                      'cancels after3 voiced/non-echo frames; echo test samples delays at128frame steps.',
          'sources': {p: sha(root / p) for p in ['src/baxy_mind/voice.py', 'src/baxy_mind/voice_output.py',
                       'src/baxy_mind/piper_tts.py', 'src/baxy_mind/voice_aec.py']}}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
print('Physical isolation122 prepared, no recording or playback yet.')
