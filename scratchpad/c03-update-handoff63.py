from pathlib import Path
import datetime
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
checkpoint = base / 'CHECKPOINT.md'
text = checkpoint.read_text(encoding='utf-8')
start = text.index('## Actual')
end = text.index('## Runtime y reserva')
text = text[:start] + '''## Actual

Fuente58 adoptada:3/5 útiles en files58-modal (t2 lectura,t3 error UTF8,t5 hora).
166 integración pass/0 skips/14s;3140 pytest pass/121 subtests/0 skips/45,45s.
Fast58 verde,93191exit0,Release16,80s,0 avisos/errores. No Full.
PRUEBAS_ARCHIVOS56_62.md/TRAMO58_62_PINS.json conservan fuente58 y nativas59–62.
59(scope) no mejora;60 causa scoped empty elimina falsa indisponibilidad pero no
concreta ámbito;61 sólo lo concreta en1/2.62 cambia hipótesis: búsqueda absoluta
no soportada. Dos respuestas explican la limitación; es simulación, no provider.

CANDIDATO63: LocalFilesystemProvider.Search rechaza Path.IsPathFullyQualified
con absolute_path_search_unsupported. No basename, no expansión de lectura ni
cambio de catálogo. Rojo proveedor1 fail/0 pass/0 skips/66ms; después8 pass/0 skips/119ms.
Integración en curso64922. Después publicar Core NativeAOT y preparar/ejecutar
scratchpad/c03-prepare-files53.py absolute -> c03-files63-absolute.py. Deben quedar
hashes del Core nuevo en PREREG; no medir con ejecutable anterior.
ASTRA-TRAMO-63.md fija hipótesis, herencia y contraste .NET10.

Arreglos53–58 preservados: contrato search/list->read.text en Python/kernel;
identificadores literales completos no se confunden con código; reason objeto
no se lee como string; IDs únicos verificados se copian sin decodificar; error
tipado se conserva como causa; modales negativos C# no exigen primera persona.
52 conserva7/7 hora/audio/CPU. Informes53_54,55,56_62 y ASTRA preservan variantes.
No repetir Fast/Full por rutina; Fast63 tras integración corresponde al cambio
de fuente. Full sólo cuando cierre C03 esté preparado.

## Pendientes de producto y límites

Evaluar files63 completo antes de adoptar. Búsqueda vacía de nombre normal aún
puede terminar step_data_missing. Progreso55 infirió UTF8 sólo del filename:
no acreditado resuelto;58 no tuvo avisos y eso no demuestra reparación.
Python _FAILURE_MARKERS todavía puede vetar fallos impersonales; no añadir filtros
de frases. Localizar payload/borrador/veto real antes de otra edición.
read.text sólo acepta IDs de LocalFilesystemProvider del filesystem-sandbox;
known.search no sirve. path.ensure.absent puede borrar: no es búsqueda.
No sustituir archivo exterior por homónimo interior ni afirmar inexistencia global.

''' + text[end:]
text = text.replace('causa57 en comparación', 'consulta absoluta63 en validación', 1)
checkpoint.write_text(text, encoding='utf-8')
(base / 'HANDOFF.md').write_text('''# Handoff — C03 — tramo63 — 2026-09-07

Goal activo, tarea01a07974-2a33-7ed3-ba87-2436944e8115, ramaGoal-c03,
HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. CHECKPOINT manda.
Conservar WIP/ajeno/evidencia; sin commit/push; main excluida.
Los tres turnos ingleses están admitidos en ADMISIBLE_DUENO (nombre exacto:
ADMISIBILIDAD_DUENO_2026-09-06.md). No volver a preguntar ni extender a742.

Fuente58:3/5 controles de archivos útiles.166 integración pass/0 skips,
3140 pytest pass/121 subtests/0 skips;Fast58 verde. Python sin cambios desde57.
PRUEBAS_ARCHIVOS56_62.md/TRAMO58_62_PINS.json fijan estado antes del cambio63.
Nativas59–61 de scope/causa vacía no bastaron;62 con causa de consulta absoluta
no admitida explica la limitación en2/2. Simulación, no aceptación del producto.

Candidato63 añade un único guard Path.IsPathFullyQualified en proveedor.Search.
8 pruebas provider pass/0 skips tras rojo1 fail. Test de integración verifica
causa tipada y recuperación por nombre. Sesión64922 en curso; luego publicar Core
NativeAOT, preparar absolute con c03-prepare-files53.py y medir los mismos5turnos.
ASTRA-TRAMO-63.md. Debe medirse ejecutable nuevo, no el anterior AOT.

Pendientes: nombre sin coincidencias, progreso que infirió UTF8 del nombre,
100 humanos frescos congelados (pool742/239; auditorías45 reutilizables),
8 rutas, averías y recuperación, UI/voz/audio real y4GB conjuntos, continuidad
C04–C09, Full verde final y publicación fuera de main. No bloqueo externo.
No Full durante reparación. No basename exterior->interior ni path.ensure.absent.
''', encoding='utf-8')
relevo = base / 'RELEVO_ACTIVO.json'
state = json.loads(relevo.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             checkpoint='consulta absoluta63 en validación; C03 completo EN_CURSO',
             continuation='Fuente58 adoptada y fijada; provider63 en validación; reserva100 y cierre integral pendientes.')
relevo.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
print('CHECKPOINT/HANDOFF/RELEVO updated')
