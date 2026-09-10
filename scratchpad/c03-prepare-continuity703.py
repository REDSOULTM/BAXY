"""Pin the continuity candidate before the complete product regression."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-continuity-source703'
out.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = ['src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/MindPlanSession.cs',
         'src/Baxy.App/UserMessagePolicy.cs', 'src/Baxy.App/PlannerExecutionSupport.cs',
         'tests/Baxy.Integration.Tests/MindPlanSessionTests.cs',
         'tests/Baxy.Integration.Tests/MindShellEndToEndTests.cs']
old = json.loads((base / 'astra-machine-actor-source702/RESULT.json').read_text(encoding='utf-8'))
assert all(sha(root / p) == expected for p, expected in old['sources'].items())
focal = Path(os.environ['TEMP']) / 'c03-continuity703-focal.log'
assert 'Superado:    18' in focal.read_text(encoding='utf-8-sig')
(out / 'FOCAL.log').write_bytes(focal.read_bytes())
record = {'utc': datetime.now(timezone.utc).isoformat(), 'adopted': False,
          'parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'sources': {name: sha(root / name) for name in paths},
          'python_tree_sha256': old['python_tree_sha256'], 'python_files': old['python_files'],
          'design': 'Use the ordinary independent typed turn decision once before interpreting unrelated text as a confirmation reply. Explicit private routes stay private. A self-contained request may retire only an unstarted, non-reconciliation confirmation, resolving its durable retry identity before clearing the plan. Reuse that transition for explicit cancellation. Keep fragments, exact confirm/cancel, uncertain effects and reconciliation on their existing bound path. No risk-policy, model, sampler, Python, or catalog changes.',
          'inheritance': ['MainWindowViewModel pending clarification path and independent turn decision',
                          'MindClarificationPolicy.IsSelfContainedRequest',
                          'MindPlanSession explicit cancellation and durable outbox resolution',
                          'PendingMindPlanExecution.CanAbandonConfirmation',
                          'product702: wrong tabs selection and39subsequent requests captured by pending confirmation'],
          'focal': {'passed': 18, 'skipped': 0, 'scope': 'Initial integration tests before four additional durable-state permutations and stronger replacement identity assertions.'},
          'validation_next': 'Owners for plan session, shell, planner boundaries and real field conductor, then Fast. Product704 uses the unchanged73inputs/order/criteria of689/694/702 with a separate transparent observer. No automatic coverage from tests or family membership.',
          'limits': 'No claim of resolving uncertain effects by abandoning them. No blanket Sensitive/External policy change. The contract fixture covers existing semantic families, not50new model intents. Full693 is baseline only; Full final still required.',
          'goal_complete': False, 'new_coverage': 0}
(out / 'PREREG.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
hook = root / 'scratchpad/c03-status704-hook/sitecustomize.py'
hook.parent.mkdir(exist_ok=False)
data = (root / 'scratchpad/c03-status702-hook/sitecustomize.py').read_bytes()
assert data.count(b'C03-status-batch702-private') == 1
hook.write_bytes(data.replace(b'C03-status-batch702-private', b'C03-status-batch704-private'))
state = json.loads((base / 'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), workStatus='continuity703_owners_running',
             checkpoint='703candidato:C# distingue objetivo nuevo de confirmación con decisión reutilizada y retirada segura del outbox.18focalespass; dueñas ampliadas yFast en sesión5175. No adoptado, sin nueva cobertura.',
             continuation='Recoger5175 y logsTEMP/c03-continuity703-{owners,fast}.log. No reiniciar por timeout. Con verde ejecutar producto704mismos73turnos; fuente703preregistrada. Revisión y adopción después de evidencia, sin cambiar políticaSensitive/External.',
             activeValidation={'name': 'continuity703_owners_then_fast', 'sessionId': 5175, 'status': 'running_exec_handle'},
             previousGoalTurnClassification='progress',
             previousGoalTurnClassificationReason='702publicada7ceeef70/4d55b449;703implementa continuidad compartida y pasó18controlesfocales, validación ampliada en curso.')
(base / 'RELEVO_ACTIVO.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n## Candidato703 — continuidad de confirmación\n\nReutiliza decisión ordinaria del turno nuevo y clasificación de objetivo autocontenido; no ejecuta ni confirma el plan anterior. Sólo retira confirmación sin inicio ni efecto incierto, resolviendo outbox y store mediante la transición existente de cancelación.18focalespass/0skip; se añadieron4controles de persistencia/incertidumbre y binding reforzado para la validación ampliada5175. No cambiaPython/modelo/riesgo/catálogo. Producto704mismos73pendiente. Encuesta26/716/0 yC03activo.\n')
print({'source703_pinned': True, 'observer704_isolated': True, 'owners_session': 5175})
