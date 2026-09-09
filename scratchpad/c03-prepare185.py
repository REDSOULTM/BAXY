"""Prepare post-decision snapshot of experimental DTLN false interruption."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-sidecar185'
out.mkdir(exist_ok=False)
prior = json.loads((base/'astra-sidecar183/PREREG.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest() == h for p,h in prior['sourceFiles'].items())
prior.update(method='Same physical sequence183, DTLN128 binding182, product172 unchanged. Add only one snapshot AFTER first emitted barge_in using caller locals and current model state. No per-frame taps. TTS state now also records UTC. Diagnostic, not acceptance or proof of comparable stochastic Piper waveform.',
             reason='183 one false interruption;184 preserved audio confirms first Spanish time truncated. Inspect exact post-decision clean/raw/reference, ring and model states before changing algorithms or thresholds.')
(out/'PREREG.json').write_text(json.dumps(prior, ensure_ascii=False, indent=2), encoding='utf-8')
for name in ['c03-capture183.py','c03-sidecar183.py','c03-sidecar183-entry.py']:
    content = (root/'scratchpad'/name).read_text(encoding='utf-8').replace('183','185')
    if name.endswith('-entry.py'):
        old = (root/'scratchpad/c03-sidecar169-entry.py').read_text(encoding='utf-8')
        snapshot = old[old.index('import inspect'):old.index("with (private/'stacks169.log')")].replace('169','185')
        snapshot = snapshot.replace("np.savez(private/'barge185.npz', **arrays)",
            "canceller = values['canceller']\n        for name in ('_near', '_far', '_out', '_mic_delay', '_previous_reference'):\n            arrays['dtln'+name] = np.asarray(getattr(canceller, name)).copy()\n        for index, state in enumerate(canceller._states):\n            arrays[f'dtln_state{index}'] = state.copy()\n        metadata.update(aecSha256=canceller.sha256, utc=datetime.now(timezone.utc).isoformat())\n        np.savez(private/'barge185.npz', **arrays)")
        content = content.replace('import time\n', 'import time\nfrom datetime import datetime, timezone\n')
        content = content.replace("{'time':time.monotonic(), 'speaking':speaking", "{'time':time.monotonic(), 'utc':datetime.now(timezone.utc).isoformat(), 'speaking':speaking")
        content = content.replace("with (private/'stacks185.log')", snapshot+"with (private/'stacks185.log')")
    elif name == 'c03-sidecar183.py':
        content = content.replace("names=['messages.jsonl'", "names=['messages.jsonl'")
        content = content.replace('    indexes=[]', "    names.extend(name for name in ['barge185.npz','barge185.json'] if (private/name).is_file())\n    indexes=[]")
    with (root/'scratchpad'/name.replace('183','185')).open('x', encoding='utf-8') as handle:
        handle.write(content)
note='''# Actualización184 — contenido183 adjudicado;185 preparado

184 sesión91987 recogida exit0,16lecturas Parakeet CPU6beam8 sin pistas.
183 saludo completo en mic crudo;primera horaES truncada;EN completa en ambos
crudos;últimaES completa sólo loopback crudo(mic dice «Son las diez»).
Normalizar no mejora siempre. PREREG184 conserva ventanas y limitación de reloj:
UTC se estima con offset wall/monotonic actual; márgenes1s, no aceptación humana.
185 preparado: misma secuencia, DTLN128, snapshot sólo tras primer barge_in;
sin taps porframe ni cambios de producto/umbrales. Recoger señales exactas antes
de variar algoritmo.182/183/184 todavía pendientes de pins conjuntos.
Turno anterior: progreso por recoger183 y registrar evento/cierre; no cierreC03.

'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    path=base/name
    path.write_text(note+path.read_text(encoding='utf-8'),encoding='utf-8')
path=base/'RELEVO_ACTIVO.json'
state=json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='184 completo16lecturas:183 primeraES truncada;EN/últimaES completas en loopback crudo. No aceptación.',continuation='185 preparado: snapshot tras primerbarge con DTLN128; mismo producto172/umbrales.')
path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('185 prepared; source172 hashes verified;184 complete; no product change.')
