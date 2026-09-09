"""Persist the next bounded step and keep owner artifacts alive."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
prior = (base / 'CHECKPOINT.md').read_text(encoding='utf-8')
(base / 'astra-owner-review273/CHECKPOINT268.md').write_text(prior, encoding='utf-8')
text = '''# C03 — checkpoint273 — EN_CURSO

Último tramo: DIAGNOSTICO269_273.md; sin reparación de producto nueva.
269 comparación nativa de fuente267: antes «Ya he abierto Steam.»; después
«Steam ya está abierto.»; dos pares idénticos/stop. Sigue afirmando estado sin
lectura actual: NO resuelto. Backend existente89232/puerto57485, sin efectos/UI.
270 quitar esquema de documentos E5 empeora rangos116→130 y26→35: descartado.
271 añadir app.open a shortlist28 no basta; nativo conserva antigua afirmación.
272 quitar historial tampoco selecciona, niega abrirSteam. No repetir variantes
de historia; aislar cobertura del contrato y competencia entre herramientas,
después argumento/identidad y admisión de afirmaciones. Detalles/payloads en
astra-native269, astra-retrieval270, astra-catalog271, astra-history272.

273 sesión264 autorizada revisada mediante registros:54decisiones finales,
20fallos de intento,100borradores admitidos distintos; NO equivalen a turnos
exitosos/UI. Informe privado C03-owner264-snapshot268/REVIEW273.md; hashes en
astra-owner-review273/RESULT.json. Faltan entradas completas/UI. BAXY84328 aún
oculto a bandeja, no reiniciar antes de preservar conversación en memoria.
Dueño reiteró autorización para tomar control y abrirlo: no pedir otra vez.
Sky no expone bandeja; captura a veces ventana activa distinta de objetivo.
No hacer clics inciertos ni usar397256 (ventana obsoleta). No helper UI alterno.

Cuestionario742 entregado y dueño marcándolo: http://127.0.0.1:63179/ PID101140.
SIN cierre automático. %LOCALAPPDATA%/BAXY/C03-owner-questionnaire-20260907/;
answers.json NO sobrescribir/borrar/rellenar por agente. No congelar mientras
revisa. Dos juicios independientes: autoría y capacidad esperada. Ni duplicados
ni frescura se atribuyen automáticamente. Tres ingleses admitidos antes siguen
vigentes. QA65100 cerrado; fuentes/QA/pins en tramo268. Ventana visible del
cuestionario conserva trabajo del dueño: no navegarla ni manipular sus marcas.

Fuente266: afirmación+petición corregida,2597pass0skip/ruff.267: contexto fuera
de situation,999pass0skip/ruff. Falta Fast/modelo/UI integrado; últimoFast262.
No Full durante reparación. Capacidades263 todavía catálogo incompleto,
length/timeout/extra_claim. Registro13b971… intacto; Qwen3.5 override no promovido.
Goal-c03/HEAD2bf3d4c, preservar WIP/main. Recursos2603516,66MiBGPU/4822,60MiBRAM
con captura/AEC/Piper sin ASR humano; wake sin certificar. Ocho rutas útiles,
100/100humanos frescos sin congelar/ejecutar, averías/recuperación, UI/voz/ASR/
recursos finales, perfil/runtime/instalación, continuidadC04–C09, Full verde y
publicación fuera main: pendientes íntegros. Sin bloqueo externo.
'''
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    (base / name).write_text(text, encoding='utf-8')
now = datetime.now(timezone.utc).isoformat()
path = base / 'RELEVO_ACTIVO.json'
relevo = json.loads(path.read_text(encoding='utf-8'))
relevo.update(confirmedAtUtc=now, checkpoint='273: questionnaire delivered; authorized session logs reviewed; native/context/catalog diagnostics still fail.',
    continuation='Recover owner UI transcript without resetting; isolate native app.open coverage/competition, then grounding and factual publication. Keep questionnaire server/answers intact.')
path.write_text(json.dumps(relevo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
names = ['scratchpad/c03-native269.py', 'scratchpad/c03-retrieval270.py', 'scratchpad/c03-catalog271.py',
    'scratchpad/c03-history272.py', 'scratchpad/c03-session273.py', 'scratchpad/c03-finish273.py',
    'artifacts/comprobaciones/C03/DIAGNOSTICO269_273.md']
for directory in ('astra-native269', 'astra-retrieval270', 'astra-catalog271', 'astra-history272'):
    names.extend(f'artifacts/comprobaciones/C03/{directory}/{name}' for name in ('PREREG.json', 'RESULT.json'))
names.append('artifacts/comprobaciones/C03/astra-owner-review273/RESULT.json')
pins = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
(base / 'TRAMO269_273_PINS.json').write_text(json.dumps({'utc': now, 'publicFiles': pins,
    'productSourceChanged': False, 'goalStatus': 'active'}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'pins': len(pins), 'checkpoint': 273, 'goal': 'active'}))
