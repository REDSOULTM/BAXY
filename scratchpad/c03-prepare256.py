"""Preserve255 and correct only the physical guard-observation interpretation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'scratchpad/c03-parity255.py').read_text(encoding='utf-8')
source = source.replace("OUT = BASE / 'astra-integration255'", "OUT = BASE / 'astra-parity256'\nOUT.mkdir(exist_ok=False)")
source = source.replace("assert not installed.exists()\nwith zipfile.ZipFile(WHEEL) as archive:\n    archive.extractall(installed)",
    "with zipfile.ZipFile(WHEEL) as archive:\n    for name in archive.namelist():\n        assert (installed / name).read_bytes() == archive.read(name)")
source = source.replace("cases = list(read(BASE / 'astra-dsp238/PREREG.json')['cases'])\nfor number in (243, 254):", "cases = []\nfor number in (254,):")
source = source.replace("'criterion': 'Exact float32 equality, every512sample block, both output views and raw echo guard. 11 frozen253 inputs plus physical254. No tolerance/gain/config change. No ASR rerun needed only if both inputs are exact.',",
    "'criterion': 'Only remaining physical254: both signals exact in every512sample block; guard compared only where recorded0/1. Sentinel -1 means uncalled, never True. Previous255 eleven full inputs remain exact. Same package/bridge/input; no tolerance or algorithm change.',")
source = source.replace("guards = data['observations'][:, 5].astype(bool)", "guards = data['observations'][:, 5]\n        assert set(guards) <= {-1, 0, 1}")
source = source.replace("            assert _looks_like_echo(raw, history) == guards[i],", "            assert guards[i] == -1 or _looks_like_echo(raw, history) == guards[i],")
source = source.replace("'guardExact': True,", "'guardExact': True, 'observedGuardsCompared': int(np.sum(guards >= 0)),")
target = ROOT / 'scratchpad/c03-parity256.py'
assert not target.exists()
target.write_text(source, encoding='utf-8', newline='\n')
