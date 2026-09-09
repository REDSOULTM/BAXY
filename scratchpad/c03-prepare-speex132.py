from pathlib import Path
source = Path('scratchpad/c03-speex130.py').read_text(encoding='utf-8')
source = source.replace('astra-speex130', 'astra-speex132').replace('C03-speex130-private', 'C03-speex132-private')
source = source.replace('C03-voice127-private', 'C03-voice125-private').replace('astra-voice127', 'astra-voice125')
source = source.replace('Existing physical capture and labelled PCM controls', 'Existing failed125 direct capture and labelled PCM controls')
source = source.replace("started = next(e for e in events if e.get('speaking'))", "started = next(e for e in events if e.get('speaking') and e['phase'] == 'direct')")
source = source.replace('near = np.zeros_like(mic)', '''
ready = next(e for e in events if e['event'] == 'ready' and e['phase'] == 'direct')
ended = next(e for e in events if e.get('speaking') is False and e['monotonic'] > started['monotonic'])
crop_first = max(0, round((dt.datetime.fromisoformat(ready['utc']).timestamp() - origins['microphone']) * 16000))
crop_last = min(mic.size, round((dt.datetime.fromisoformat(ended['utc']).timestamp() - origins['microphone'] + 1) * 16000))
mic, reference = mic[crop_first:crop_last], reference[crop_first:crop_last]
speech_start -= crop_first
near = np.zeros_like(mic)''')
source = source.replace("'Existing physical127 microphone/loopback; no playback'", "'Existing failed125 direct microphone/loopback; crop from ready to speaking-end+1s, excludes off-before adaptation; no playback'")
source = source.replace("'methods': ['aec_residual']", "'methods': ['raw', 'aec_residual']")
source = source.replace("for method in ['aec_residual']:", "for method in ['raw', 'aec_residual']:")
with Path('scratchpad/c03-speex132.py').open('x', encoding='utf-8') as stream:
    stream.write(source)
