from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
folder = base / 'astra-clarification-error-guarded-qwen'
paired = json.loads((folder / 'paired.json').read_text(encoding='utf-8-sig'))
assert len(paired) == 12
assert sum(r['terminal'] == 'published_final' for r in paired) == 11
adjudication = {}
parts = ['# Prueba de guarda causal: experimento rechazado',
         'Doce turnos de desarrollo. Once publicaciones no equivalen a once aciertos. '
         'La guarda y el prompt experimentales fueron retirados; los datos permanecen intactos.']
for row in paired:
    ident = row['turnId']
    verdict = 'ÚTIL'
    reason = 'Responde al turno; no se atribuyen efectos que no se verificaron.'
    if ident in {'t1', 't4', 't7'}:
        verdict = 'REVISAR CONTINUIDAD'
        reason = 'Pregunta para aclarar volumen; falta comprobar respuesta con un nivel y continuación real.'
    if ident == 't6':
        verdict = 'FALLO'
        reason = 'composition_failed; no hay respuesta final. Bloquear la causa inventada no logró una recuperación útil.'
    if ident in {'t8', 't9'}:
        verdict = 'FALLO'
        reason = 'La respuesta no resuelve el turno actual; arrastra la cancelación/aclaración anterior.'
    adjudication[ident] = {'verdict': verdict, 'reason': reason}
    parts += [f'## {ident} — {verdict}', '**Entrada literal**\n```text\n'+row['request']+'\n```',
              '**Respuesta literal**\n```text\n'+(row['final'] or '')+'\n```',
              f"Terminal: {row['terminal']}. {reason}"]
(folder / 'ADJUDICACION.json').write_text(json.dumps(adjudication, ensure_ascii=False, indent=2), encoding='utf-8')
(folder / 'RESPUESTAS.md').write_text('\n\n'.join(parts)+'\n', encoding='utf-8')
names = ['paired.json', 'RESPUESTAS.md', 'ADJUDICACION.json', 'RESULT.json', 'PREREG.json']
(folder / 'REPORT_MANIFEST.json').write_text(json.dumps({
    'acceptance': False,
    'files': {name: hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in names},
    'literalVerification': all(row['request'] in '\n'.join(parts) and (row['final'] or '') in '\n'.join(parts) for row in paired),
}, indent=2), encoding='utf-8')
checkpoint = '''# C03 — CHECKPOINT — 2026-09-06

EN_CURSO, sin bloqueo externo. Goal-c03, HEAD
2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Main/stash ajeno intactos.
Trabajo acumulado sin commit/push; ningún proceso propio activo, sin subagentes.
AGENTS, identidad y C03_ASTRA_AUTORIDAD mandan; VRAM total BAXY≤4096 MiB.

## Hecho y evidencia

Investigación pedida: Granite registrado y Qwen base sin LoRA, conversación por
ocho capas, compositor por tres capas, aplicación integrada. Informe actualizado:
DIAGNOSTICO_POR_CAPAS_C03.md. Entradas, borradores, rechazos, prompts y hashes
en RESPUESTAS/PREREG de cada carpeta enlazada. Diagnóstico, NO aceptación fresca.
Granite ya falla desnudo. Historial puede deformar contenido. Selección de
presentación y filtros añaden rechazos falsos. Provider/kernel conservaban los
hechos de audio/cancelación: el generador los falseaba y el validador los admitía.

Correcciones conservadas: clasificar pregunta dentro del prefijo idiomático;
permitir saludo social, confirmación sin puntuación impuesta, progreso expresado
con morfología; nombres propios sólo tipados, no verbos capitalizados de entrada.
_truncated_fact_word RESTAURADO, no era la causa. No eliminar guardas enteras.
Política mixta admite español, definiciones simples y gramática menor. Piloto2
13→17/21 fue corrección de rúbrica del dueño, NO mejora del modelo.

Prueba nueve casos/modelo: astra-presentation-guards-fixed-*; Qwen9 útiles,
Granite5 útiles/1 revisión/3 fallos. Integrado astra-presentation-product-qwen:
21/21 útiles de desarrollo; GPU3497,56MiB. Los dos idiomas de entrada y mezcla
son comprendidos. El conductor NO acredita inspección gráfica ni voz.

## Experimento retirado y siguiente problema

astra-clarification-error-qwen:12/12 publicados; t6 inventa inexistencia de app.
Tres variantes usan explicit_conversation/unsupported sin lectura de existencia.
Frontera: __main__._catalog_unavailable_turn_decision:5459 trata open/abre sin
identidad autenticada como unsupported; no es una comprobación app_not_found.
Prompt aclaratorio no mejoró (astra-unsupported-evidence-qwen-base).
Guarda causal agotó respuesta (astra-unsupported-cause-qwen-base); integración
astra-clarification-error-guarded-qwen:11/12 publicados, t6 composition_failed,
t8/t9 arrastran cancelación anterior. RESPUESTAS/ADJ conservan fallos.
RETIRADOS prompt y guarda causal, junto con tests específicos de esa guarda.
No repetir intentos por frase, entrenamiento ni matrices amplias sin hipótesis.

Siguiente: resolver límite conocido y recuperación usando estado/causa tipados;
probar aclaración con respuesta concreta y continuación (hasta ahora cancelada).
No afirmar mejora por ocultar el fallo ni promover todavía Qwen.

## Validación y runtime

Fuente llm.py SHA c80241a416a41505841d1580a0adebf4b9724e5d7d908013b6e426e17a20c0aa.
Exactamente la fuente de Fast10411 TERMINAL0,0errores/0advertencias
(scratchpad/c03-presentation-guards-fast.log). Reversión confirmada por hash.
Tras reversión:148passed/0skips en2,07s: test_c03_request_preservation.py,
test_compose_contract.py, test_goal06_voice.py. Ruff formateado. Full pendiente.
Pytest está en runtime Python; Python de quality no tiene pytest.
Registro Granite intacto SHA428b6248eeb8f78bb94082eec5b59bc127a669d9c609e24251591dbcb5743181.
Qwen base Instruct2507 Q4_K_M sólo diagnóstico, sin LoRA; usa KVq8 por override.
Default productoKVq4: no promover GGUF solo y afirmar perfil idéntico.
Pico de los12turnos3499,56MiB; falta coexistencia con voz/wake.

## Falta para cerrar

Desarrollo verde;100 NUEVOS preregistrados/adjudicados,8rutas/3idiomas;
recuperación aparte, UIreal py main.py, runtime registrado reproducible sin
overrides, Full final verde, publicación propia fuera main y contratos afectados
hasta12.3. No confundir investigación concluida con C03 completado.
V1 ablation invalidado por instrumento; usarV2. Compositor sin seed explícito:
comparar borrador/final de misma llamada para atribución causal.
Piloto4 LoRA64823 terminal0,102salidas sin adjudicación nueva; LoRA PAUSADO.
No procesos pendientes por recoger. Tramo27 y reporte contienen enlaces.
'''
(base / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
(base / 'HANDOFF.md').write_text(checkpoint.replace('CHECKPOINT', 'HANDOFF', 1), encoding='utf-8')
tramo = base / 'ASTRA-TRAMO-27.md'
s = tramo.read_text(encoding='utf-8')
old = s.index('Siguiente medida en curso:')
s = s[:old] + '''Integrado75705 TERMINAL0: astra-presentation-product-qwen,21/21 útiles.
Diagnóstico adicional25921 TERMINAL0:12/12publicados pero t6 inventa inexistencia.
Prompt62830 sin mejora; guarda86417 agota respuesta. Integrado41856 TERMINAL0:
11/12publicados, t6 composition_failed y t8/t9 contaminados por diálogo previo.
Se retiraron prompt/guarda fallidos. Fuente vuelve al SHA del Fast verde indicado.
148pass tras reversión en2,07s. Datos fallidos preservados, no reinterpretados
como aprobación. CHECKPOINT y DIAGNOSTICO_POR_CAPAS_C03 actualizados.
Registro Granite intacto, Qwen no promovido. Full/100/UI siguen pendientes.
'''
tramo.write_text(s, encoding='utf-8')
print('Reporte de experimento fallido y checkpoint actualizados; 12 literales conservados.')
