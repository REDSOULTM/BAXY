from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

# Reconstruct the pre-COM capture source, accepting it only if PREREG144 matches.
source=(root/'src/baxy_mind/voice_capture.py').read_text(encoding='utf-8')
source=source.replace('from contextlib import ExitStack\n','').replace('from .voice_aec import _com_apartment\n\n','')
first=source.index('    def __init__')
last=source.index('    @property',first)
original_init='''    def __init__(self, stop_event: threading.Event) -> None:
        import sounddevice as sd

        api = next(
            (item for item in sd.query_hostapis() if item["name"] == "Windows WASAPI"),
            None,
        )
        if api is None or int(api["default_input_device"]) < 0:
            raise RuntimeError("wasapi_input_unavailable")
        self._stop_event = stop_event
        self._frames: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(64)
        self._error: str | None = None
        self.adc_time: float | None = None
        self._stream = sd.InputStream(
            device=int(api["default_input_device"]),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=FRAME_SAMPLES,
            extra_settings=sd.WasapiSettings(auto_convert=True),
            callback=self._callback,
        )

'''
source=source[:first]+original_init+source[last:]
first=source.index('    def __enter__')
last=source.index('    def read',first)
original_enter='''    def __enter__(self) -> WasapiCaptureStream:
        try:
            self._stream.__enter__()
        except Exception:
            self._stream.close()
            raise
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stream.__exit__(*exc)

'''
source=source[:first]+original_enter+source[last:]
prereg=json.loads((base/'astra-voice144/PREREG.json').read_text(encoding='utf-8'))
expected=prereg['sources']['src/baxy_mind/voice_capture.py']
variants=[source.encode(),source.replace('\n','\r\n').encode()]
original=next(data for data in variants if hashlib.sha256(data).hexdigest()==expected)
snapshot=base/'astra-source143-snapshot'
snapshot.mkdir(exist_ok=False)
paths=[]
for name,sha in prereg['sources'].items():
    data=original if name=='src/baxy_mind/voice_capture.py' else (root/name).read_bytes()
    assert hashlib.sha256(data).hexdigest()==sha,name
    target=snapshot/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
    paths.append(target)

paths += [base/name for name in ['ASTRA-TRAMO-143.md','ASTRA-TRAMO-147.md','PRUEBAS_CAPTURA143_157.md','RESERVA_PREVIEW155.md']]
snapshot_index=base/'astra-source147-snapshot/INDEX.json'
paths.append(snapshot_index)
for row in json.loads(snapshot_index.read_text(encoding='utf-8')):
    target=root/row['snapshot']
    assert digest(target)==row['sha256']
    paths.append(target)
private_verified=0
for number in [144,148,149,152,153,154]:
    folder=base/f'astra-voice{number}'
    names=['PREREG.json','AUDIO_SETUP.json','AUDIO_READY.json','AUDIO_RESULT.json','EVENTS.jsonl']
    if number!=144:
        names.append('RESULTS.json')
    if number in [149,152,154]:
        names.append('OBSERVATION_INDEX.json')
    if number in [152,153,154]:
        names.append('GENERATED_INDEX.json')
    paths += [folder/name for name in names]
    audio=json.loads((folder/'AUDIO_RESULT.json').read_text(encoding='utf-8'))
    assert audio['restoredExactly'] and audio['threadsStopped']
    for stream in audio['streams'].values():
        assert digest(Path(stream['privatePath']))==stream['sha256']
        private_verified+=1
    for name in [n for n in names if n.endswith('_INDEX.json')]:
        for row in json.loads((folder/name).read_text(encoding='utf-8')):
            assert digest(Path(row['privatePath']))==row['sha256']
            private_verified+=1
for number in [145,146]:
    paths.append(base/f'astra-capture{number}/RESULTS.json')
paths.append(base/'astra-analysis150/RESULTS.json')
paths += [base/'astra-phase151'/name for name in ['PREREG.json','RESULTS.json']]
for number in [156,157]:
    folder=base/f'astra-analysis{number}'
    paths += [folder/name for name in ['PREREG.json','RESULT_INDEX.json']]
    for row in json.loads((folder/'RESULT_INDEX.json').read_text(encoding='utf-8')):
        assert digest(Path(row['privatePath']))==row['sha256']
        private_verified+=1
scripts=['c03-integrate143.py','c03-reference143-class.txt','c03-prepare144.py','c03-probe145.py','c03-probe146.py',
    'c03-prepare148.py','c03-prepare149.py','c03-analyze150.py','c03-check151.py','c03-prepare152.py','c03-prepare153.py',
    'c03-prepare154.py','c03-preview155.py','c03-prepare156.py','c03-analyze-voice156.py','c03-prepare157.py','c03-analyze-voice157.py',
    'c03-snapshot147.py','c03-checkpoint157.py','c03-pin157.py']
for number in [144,148,149,152,153,154]:
    scripts += [f'c03-voice{number}.py',f'c03-capture-voice{number}.py']
paths += [root/'scratchpad'/name for name in scripts]
rows=[{'path':str(p.relative_to(root)),'sha256':digest(p),'bytes':p.stat().st_size} for p in paths]
assert len({r['path'] for r in rows})==len(rows)
target=base/'TRAMO143_157_PINS.json'
with target.open('x',encoding='utf-8') as f:
    json.dump({'state':'EN_CURSO','source':147,'privateFilesVerified':private_verified,'files':rows},f,indent=2)
assert all(digest(root/row['path'])==row['sha256'] for row in rows)
print(json.dumps({'publicPins':len(rows),'privateFilesVerified':private_verified,'reconstructed143MatchesPrereg':True}))
