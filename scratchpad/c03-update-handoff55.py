from pathlib import Path
import datetime
import json

base = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03'
handoff = '''# Handoff — C03 completo — 2026-09-07 — 2bf3d4c

EN_CURSO. Task01a07974-2a33-7ed3-ba87-2436944e8115, ramaGoal-c03.
Preservar WIP/ajeno/evidencia, sin commit/push, main excluida. No reiniciar campaña.
Autoridad: C03_ASTRA_AUTORIDAD.md; CHECKPOINT manda. Archivo histórico anterior:
HANDOFF_HISTORICO_HASTA51.md. La confirmación «Son turnos validos» de los tres
textos ingleses ya está en ADMISIBLE_DUENO; no preguntar ni extenderla al pool742.

ACTIVO55: sesión95521, build App y astra-files55-trace. Recoger RESULT y shell-trace
turn.error, no relanzar ni editar fuente mientras corra. Sólo cambia la etiqueta
tipo/método de excepción a minúsculas para respetar el sanitizador; antes perdía
el diagnóstico como invalid. No mensajes privados de excepción. ASTRA-TRAMO-55.md.

Adoptado54 incluye contrato53: search/list -> filesystem.read.text y autoridad
resourceId concordantes Python/kernel/App. Los IDs de known.search no sirven.
Prosa54 conserva tokens completos que el usuario escribió frente al veto
snake/dotted. Retirado chequeo snake duplicado C#. Otros códigos siguen vetados.
files54-literals:2/5 útiles (lectura UTF8 fiel y hora), frente a1/5 en53.
t1/t4 siguen con result_unverified; t3composition_failed. No causa útil acreditada.
74,09s,GPU3497,56MiB,RAM5322,07MiB,registro intacto,83342exit0.
178pytestpass/0skips/2,23s;152integraciónpass/0skips/12s,61427exit0.
Contrato53:12kernelpass/0skips/48ms+88integraciónpass/0skips/4s.
Fast54 verde,97644exit0,Release17,00s,0avisos/errores. No Full.
PRUEBAS_ARCHIVOS53_54.md/TRAMO54_PINS.json conservan literales y huellas.

52 sigue acreditando7/7 controles hora/audio/CPU incluyendo progreso; no reserva.
Runtime Qwen3-4B-Instruct-2507 Q4_K_M,KVq8,ngl99,3x4096,registro intacto.
No cambiar modelo para un borrador fiel vetado o una excepción del producto.

Siguiente: identificar excepción55 y resolver error/scope. No sustituir archivo
exterior por homónimo del sandbox; no usar path.ensure.absent (puede borrar).
Falta cierre completo:8rutas,reserva100 humana fresca congelada,averías/recuperación,
UI/voz/audio físico+recursos finales,contratosC04–C09,Full y publicar fuera de main.
Pool privado742,239 candidatos no descartados: reusar auditorías45, no reejecutarlas.
No bloqueo externo. Conductor no acredita UI/audio ni uso humano real.
'''.replace('ADMISIBLE_DUENO', 'ADMISIBILIDAD_DUENO_2026-09-06.md')
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             checkpoint='tramo54 adoptado; diagnóstico de excepción55 en curso, sesión95521',
             continuation='C03 completo EN_CURSO; 2/5 controles de archivo y 7/7 de reloj no sustituyen el cierre.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
print('handoff/relevo actualizados; goal sigue activo')
