from pathlib import Path
import datetime
import json

base = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03'
checkpoint = base / 'CHECKPOINT.md'
archive = base / 'CHECKPOINT_HISTORICO_HASTA56.md'
assert not archive.exists()
archive.write_bytes(checkpoint.read_bytes())
state_text = '''# C03 — CHECKPOINT — causa57 en comparación — EN_CURSO

Task01a07974-2a33-7ed3-ba87-2436944e8115; continuación completa de01a074f6-9e0e-7fb3-8282-a6b706198a7e.
RamaGoal-c03;HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. WIP/ajeno/evidencia
preservados, sin commit/push, main excluida. Goal persistente activo, sin bloqueo externo.
Autoridad: C03_ASTRA_AUTORIDAD.md/C03_RESPUESTA_VERAZ.md, identidad y AGENTS.
Historia anterior íntegra: CHECKPOINT_HISTORICO_HASTA56.md y HASTA52.md.

## Actual

astra-files57-cause EN EJECUCIÓN, sesión80446; no editar fuente ni relanzar antes
de recoger RESULT.json. 188pytestpass/0skips/2,00s. Proyección de error tipado
a causa de operación fallida, sin sobreescribir cause ni cambiar éxito.
ASTRA-TRAMO-57.md. Una diferencia frente a files56-identity; mismos cinco inputs.
Recoger paired con c03-pair-registered.py sólo después de terminar.

56: resourceId se copia del único productor search/list verificado en los
registros existentes Python/App, sin decodificarlo de nuevo con el modelo.
Rechaza cero/múltiples identidades, no verificadas y known.search.
1080pytestpass/121subtests/0skips/7,02s;160integraciónpass/0skips/13s.
files56-identity:2/5 útiles (t2lectura UTF8 fiel,t5hora);79,08s,GPU3497,56MiB,
RAM5041,58MiB,registro intacto,84311exit0. No plan.ground innecesario en t2.
t1/t4 aún no explican límite; t3sin prosa. Fast integrado56/57 pendiente.

55: tipado de reason arreglado en CollectStructuredLiterals. GetString sobre
objeto causaba excepción antes de componer; ahora recorre reason conservando
razones textuales/títulos. Etiquetas de excepción en minúsculas permiten trazar
sin contenido privado. Rojo2fail/1pass;154integraciónpass/0skips/13s.
Fast55 verde,35783exit0,Release15,53s,0avisos/errores. No Full.
files55-reason:1/5 útil,80,09s,GPU3497,56MiB,RAM4893,38MiB. La causa ya llega
a composición C#, pero Python omitía error del resultado tipado. t2 tuvo ID
verificado y step_data_missing; ésa es la causa de56. No ocultar variación54/55.
PRUEBAS_TIPOS_ERROR55.md/TRAMO55_PINS.json/ASTRA55 preservan datos y fuente primaria.

54: contrato search/list->read.text concordante entre Python y kernel/App;
identificadores literales completos del usuario ya no son códigos filtrados.
Retirado chequeo snake C# duplicado. Producto2/5;178pytestpass/152integraciónpass,
0skips. Fast54 verde. PRUEBAS_ARCHIVOS53_54.md/TRAMO54_PINS.json.
52:7/7 controles hora/audio/CPU completos, incluyendo progreso y negación de fallos.
PRUEBAS_POLARIDAD52.md. No representa reserva humana ni UI. Preservar arreglos44–52.

## Siguiente owner y límites

En55 t3,situation.reason.error=invalid_utf8 quedó como payload.reason={outcome:failed}.
El primer borrador acierta UTF8, pero también aparece en el filename: no atribuirlo
a conservación causal. missing_failure veta 'reading it failed'; reintento inventa
sandbox readonly. Progreso t3 también infiere UTF8 del nombre antes de observarlo.
Después de57, tratar esos vetos con contraste de fallos afirmados/negados y
causa preservada; no otro modelo ni filtros de frases particulares.
_FAILURE_MARKERS Python aún sólo reconoce una lista corta; C#52 ya distingue
fallos negados e independientes. Reusar ese mecanismo si se confirma la necesidad.

read.text sólo acepta handles de LocalFilesystemProvider de dataRoot/filesystem-sandbox.
Los IDs de known.search NO sirven; path.ensure.absent puede borrar y NO es lookup.
CASES de files53-baseline fija fixtures e inputs: ausente absoluto, UTF8 válido,
UTF8 inválido, archivo exterior homónimo de otro dentro, hora. No sustituir por
basename ni afirmar inexistencia global por búsqueda vacía. No borrar fixtures.

## Runtime y reserva

Qwen3-4B-Instruct-2507 Q4_K_M,llama.cppb9980CUDA12.4,KVq8,ngl99,3x4096.
Manifest LOCALAPPDATA/BAXYRuntime/mind-runtime-v1.json SHA
13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Python registrado LOCALAPPDATA/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe.
Conductor no acredita UI/audio; techo conjunto final4GB con voz pendiente de medir.

Confirmación «Son turnos validos» ya registrada exclusivamente para tres textos
en ADMISIBLE_DUENO. No preguntar ni extender a742. ACLARACION_DUENO_2026-09-06.md
fija mezcla natural: español válido, sin cuotas/traducciones. Pool privado742 en
LOCALAPPDATA/BAXY/C03-real-user-pool-20260906/unique_requests.jsonl.
239 candidatos no descartados, selección100 pendiente; reusar auditorías45.
Ni paneles técnicos ni turnos de desarrollo son reserva humana fresca.

Falta cierre completo:8rutas,reserva100 congelada y100/100,averías/recuperación,
UI/voz/audio físico+recursos finales,contratosC04–C09,Full íntegro y publicación
fuera de main. Mantener EN_CURSO. No repetir Full mientras se repara.
'''.replace('ADMISIBLE_DUENO', 'ADMISIBILIDAD_DUENO_2026-09-06.md')
checkpoint.write_text(state_text, encoding='utf-8')
handoff = '''# Handoff — C03 — causa57 en comparación — 2026-09-07

Goal EN_CURSO,task01a07974-2a33-7ed3-ba87-2436944e8115,ramaGoal-c03.
Conservar WIP/ajeno/evidencia;sin commit/push;main excluida. CHECKPOINT manda.
Confirmación de los3turnos ingleses ya registrada; no volver a pedir ni extender.

ACTIVO: sesión80446,astra-files57-cause; recoger RESULT antes de editar fuente.
Después c03-pair-registered.py astra-files57-cause. Python188pass/0skips/2,00s.
57 preserva error tipado de operación fallida con _cause_in_prose; antes se perdía.
56 copia resourceId único verificado search/list, sin nueva decodificación.
1080pytestpass/121subtests/0skips;160integraciónpass/0skips. Producto56:2/5 útil.
55 arregla GetString de reason objeto en C#,traza segura y154tests/Fast verdes.
Su producto1/5 conservó variación; no atribuir estabilidad a una sola lectura.
54 resolvió contratos y filenames;52 conserva7/7 hora/audio/CPU/progreso.
ASTRA53–57/PRUEBAS_ARCHIVOS53_54/PRUEBAS_TIPOS_ERROR55 fijan literales y decisiones.

Siguiente tras57: evaluar missing_failure que veta 'reading it failed' y deja
reintento de causa falsa. C#52 ya distingue fallos afirmados/negados. No cambiar
modelo. Progreso t3 también infiere UTF8 sólo del filename: queda pendiente.
No basename exterior->interior, no globalidad de búsqueda vacía, no path.ensure.absent.
Fast integrado56/57 pendiente. No Full durante reparación. Falta cierre completo:
8rutas,100humanos frescos congelados,averías/recuperación,UI/voz/audio y4GB conjuntos,
contratosC04–C09,Full,publish fuera de main. Reserva privada742/239 sin seleccionar100;
reusar auditorías45. Sin bloqueos externos. CHECKPOINT contiene runtime/rutas.
'''
(base / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
path = base / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             checkpoint='causa57 en comparación, sesión80446; C03 completo EN_CURSO',
             continuation='Se preservan arreglos53–56; reserva100 y cierre integral pendientes.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
print('checkpoint/handoff/relevo actualizados; historia56 conservada')
