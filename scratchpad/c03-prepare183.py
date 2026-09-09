from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-sidecar183';out.mkdir(exist_ok=False)
prior=json.loads((base/'astra-sidecar173/PREREG.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in prior['sourceFiles'].items())
prior.update(method='Same physical four outputs173, full JSONL/LLM sidecar/environment, state-only observer. Experimental replacement of EchoCanceller binding with DTLN128 streaming182; status resolver points to experimental model directory, SHA covers both weights. Product source/thresholds/wake unchanged. No synthetic near injection here; this tests false interruption, not positive double-talk or final acceptance.',
             reason='182 exact PCM parity and384sample alignment on3cases for both128/512.128 has p99 up to4.11ms per32ms,512 up to22.22ms; choose128 for bounded physical diagnostic, not accepted runtime.',
             experimentSha256=hashlib.sha256((root/'scratchpad/dtln_stream182.py').read_bytes()).hexdigest())
(out/'PREREG.json').write_text(json.dumps(prior,indent=2,ensure_ascii=False),encoding='utf-8')
for name in ['c03-capture173.py','c03-sidecar173.py','c03-sidecar173-entry.py']:
    text=(root/'scratchpad'/name).read_text(encoding='utf-8').replace('173','183')
    if name.endswith('-entry.py'):
        text=text.replace('"""Original sidecar with timed thread diagnostics only; no monkeypatches."""','"""Experimental DTLN128 binding, same sidecar and state-only observer."""')
        text=text.replace('from baxy_mind.voice_output import NeuralSpeechOutput',
            "from baxy_mind.voice_output import NeuralSpeechOutput\nimport baxy_mind.voice as voice_module\nfrom dtln_stream182 import EchoCanceller\nvoice_module.EchoCanceller = EchoCanceller\nvoice_module.resolve_echo_canceller_library = lambda: Path('D:/BAXYRuntime/experiments/voice/dtln179')")
    elif name=='c03-sidecar173.py':
        text=text.replace('Product source172 with main prepare_resampler, no diagnostic preimport.', 'Product source172 with experimental DTLN128 binding182, no source modification.')
        text=text.replace("(out/'STOP_AUDIO').touch(exist_ok=False)","(out/'STOP_AUDIO').touch(exist_ok=True)")
        # Also stop the bounded audio observer when the driver fails inside try.
        text=text.replace("    (out/'INDEX.json').write_text(json.dumps(indexes,indent=2),encoding='utf-8')", "    (out/'INDEX.json').write_text(json.dumps(indexes,indent=2),encoding='utf-8')\n    (out/'STOP_AUDIO').touch(exist_ok=True)")
    with (root/'scratchpad'/name.replace('173','183')).open('x',encoding='utf-8') as f:f.write(text)
note='''# Actualización182 — adaptador continuo verificado;183 preparado

182 sesión47659exit0: seis comparaciones PCM idénticas a179/180;384muestras de
retardo/alineación verificada, propiedad de hilo/cierre/entrada inválida pasan.
128 p99≤4,11ms por32ms;512 p99≤22,22ms. Sin fuente/runtime cambiados.
183 preparado: mismo fullsidecar173/cuatro salidas, binding experimental DTLN128
y observador sóloestado, sin taps porframe. Comparar falsas interrupciones y
contenido físico. No aceptación de entrada humana ni del fallo de mezcla179.
Turno anterior clasificado progreso: comparaciones174–181 cambiaron estrategia.

'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8')
p=base/'RELEVO_ACTIVO.json';state=json.loads(p.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='182 completo:6paridadesPCM,retardo384 y lifecycle pasan. Producto172 intacto.',continuation='183 preparado, prueba física cuatro salidas173 con DTLN128 experimental; conservar fallo de mezcla y resto C03 íntegro.')
p.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('183 prepared;182 verified; no own processes running before capture.')
