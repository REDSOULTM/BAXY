"""Record independently useful OS evidence while preserving Full's sealed source."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'PROCESS_REPAIR796'
pins = json.loads((out / 'SOURCE_PINS.json').read_text(encoding='utf-8-sig'))
assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == digest for p, digest in pins.items())
note = ('Full796 sigue confirmado vivo en39408;17pins intactos,contratos60pass e integraciónen curso. '
        'Se obtuvo evidencia nueva paraH0675: EX2Windows mide memoria residente privada; '
        'probe desechable8MiB→delta8.392.704bytes,0,0192–0,0316ms. AppDiagnosticInfo sólo appsconpaquete; '
        'membresíaWin32/auxiliares siguependiente. APP_MEMORY_FINDING.md. Sin editarcandidato,28/714/0.')
p = base / 'CHECKPOINT.md'
p.write_text(note + '\n\n' + p.read_text(encoding='utf-8-sig'), encoding='utf-8')
p = base / 'RELEVO_ACTIVO.json'
state = json.loads(p.read_text(encoding='utf-8-sig'))
state.update(checkpoint=note, confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
             previousGoalTurnClassification='progress',
             previousGoalTurnClassificationReason='Previous turn implemented and sealed17source repair796 with3248Pythonpass/Fast0 and launched completeFull39408. Current turn verified the same handle live and obtained native private-working-set evidence for remaining app-memory blocker.')
p.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
p = base / 'HANDOFF.md'
text = p.read_text(encoding='utf-8-sig')
text += ('\nRO útil mientrasFull corre: APP_MEMORY_FINDING.md + PRIVATE_WORKING_SET_PROBE.json enPROCESS_REPAIR796. '
         'Windows26200 soporta K32GetProcessMemoryInfo/EX2(96bytes),PrivateWorkingSetSize;probe8MiB detectado8.392.704bytes,'
         '0,0192–0,0316ms. Totalworking-set incluyecompartidas, no sumarcomoRAMfísicaúnica. '
         'AppDiagnosticInfo/GetResourceGroups sóloappsconpaquete; noresuelveWin32. Fuenteactual Applications sóloacreditaventanasvisibles/recibos, '
         'sinparentPID/membresíacompleta. Se mantieneH0675abierto.17pins intactos;39408 siguevivo, no reiniciar.\n')
p.write_text(text, encoding='utf-8')
print(note)
