from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-analyze-voice135.py').read_text(encoding='utf-8')
source=source.replace('135','156').replace('134','154')
source=source.replace('for phase in ["direct"]:', 'for phase in json.loads((source / "PREREG.json").read_text(encoding="utf-8"))["phases"]:')
source=source.replace('        windows = {}', '''        generated = next(r for r in json.loads((source / "GENERATED_INDEX.json").read_text(encoding="utf-8")) if r["phase"] == phase)
        generated_path = Path(generated["privatePath"])
        assert hashlib.sha256(generated_path.read_bytes()).hexdigest() == generated["sha256"]
        generated_audio = np.load(generated_path)
        generated_audio = resample_poly(generated_audio, 16000, generated["sampleRate"])
        row["generatedTranscript"] = transcribe(generated_audio)
        row["expectedFixture"] = json.loads((source / "PREREG.json").read_text(encoding="utf-8"))["texts"][phase]
        windows = {}''')
(root/'scratchpad/c03-analyze-voice156.py').write_text(source,encoding='utf-8')
print('Offline analyzer156 prepared from135; six154 fixtures with generated+physical tracks.')
