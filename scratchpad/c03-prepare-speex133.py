from pathlib import Path
s = Path('scratchpad/c03-check-speex131.py').read_text(encoding='utf-8')
s = s.replace('astra-speex131', 'astra-speex133').replace('C03-voice127-private', 'C03-voice125-private').replace('astra-voice127', 'astra-voice125')
s = s.replace('C03-speex129-private', 'C03-speex132-private').replace('C03-speex130-private', 'C03-speex132-private')
s = s.replace("start = next(e for e in events if e.get('speaking'))", "start = next(e for e in events if e.get('speaking') and e['phase'] == 'direct')")
s = s.replace("loop = read(base", """ready = next(e for e in events if e['event'] == 'ready' and e['phase'] == 'direct')
crop_first = max(0, round((dt.datetime.fromisoformat(ready['utc']).timestamp()-origins['microphone'])*16000))
first_speech -= crop_first
last_speech -= crop_first
offset += crop_first
loop = read(base""")
s = s.replace("for name in ['physical_echo', 'near_only', 'physical_echo_plus_synthetic_near']:", "for name in ['physical_echo']:")
begin = s.index('    for method, signal, delay')
end = s.index("(out / 'LIMITS.json')")
s = s[:begin] + '    for alignment_phase in range(0, 512, 64):\n' + ''.join('    '+line if line.strip() else line for line in s[begin:end].splitlines(keepends=True)) + s[end:]
s = s.replace('range(0, signal.size-511, 512)', 'range(alignment_phase, signal.size-511, 512)')
s = s.replace("row = {'case': name,", "row = {'case': name, 'alignmentPhaseSamples': alignment_phase,")
s = s.replace('Existing captures127 and labelled synthetic near controls129', 'Failed direct125, fixed eight capture-frame phases0..448 step64 to test sensitivity; no tuning or best-phase selection')
with Path('scratchpad/c03-check-speex133.py').open('x', encoding='utf-8') as stream:
    stream.write(s)
