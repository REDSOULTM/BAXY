"""Observe185 using paired UTC saved with state; no late clock reconstruction."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
content=(root/'scratchpad/c03-observe184.py').read_text(encoding='utf-8')
content=content.replace('183','185').replace('184','186')
content=content.replace("intervals.append((event['time'], end['time']))", "intervals.append((dt.datetime.fromisoformat(event['utc']).timestamp(), dt.datetime.fromisoformat(end['utc']).timestamp()))")
start=content.index('clock_samples = []')
end=content.index('manifest_path = ',start)
content=content[:start]+"clock_samples = []\noffset = 0.0\n"+content[end:]
content=content.replace("185 speaking state has monotonic only; map with wall-minus-monotonic measured now on same boot. Assumes no intervening wall clock jump. Use one second margin each side and preserve boundaries/energy. Recognition and normalization are diagnostic, not proof of human input or complete fidelity.", "185 speaking state has paired UTC recorded in the process. Map directly to capture streamReadyUtc with one second margin each side; neither API time is exact first audible sample. Recognition and normalization are diagnostic, not proof of human input or complete fidelity.")
with (root/'scratchpad/c03-observe186.py').open('x',encoding='utf-8') as handle:
    handle.write(content)
print('186 observer prepared; no post-decision185 snapshot exists because no interruption occurred.')
