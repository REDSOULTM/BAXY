from datetime import datetime, timezone
import json
from pathlib import Path

folder = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03'
checkpoint = '''# C03 — checkpoint400 — EN_CURSO

Goal completo activo. Goal-c03, HEAD 2bf3d4c; conservar WIP, main y evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY manual cerrado.
Modelos, producto y pruebas cerrados; handles399/400 terminaron exit0.
Encuesta original y servidor101140 intactos. Instrucciones consolidadas del
2026-09-08:16 mensajes directos y742 registros rev1248; automáticos excluidos.

Última fuente .NET393: consultas explícitas de nombre guardado ES/EN usan
memory.recall privado exact/name. Focal20pass; seis dueñas1996pass0skip;
Fast verde, build17,97s. Producto393b:1útil1parcial4fallos/6 sintéticos:
lee Jordan pero dice que no hay recuerdos o «Mi nombre es Jordan»; consulta
genérica lee Jordan persistido en vez de Álvaro del diálogo. DeclaraciónÁlvaro
no sobrescribió memoria; su respuesta salió inglesa. RESULT/PINS completos.

Python395 conserva presentation_history en reintento de chat. Dueñas1343pass,
Fast1,52s. Averías394:2/5→4/5+parcial; implementación396:5/5, pero idénticos
payloads produjeron distinta fraseÁlvaro. Conservar variación, no certificar estabilidad.
Python397 es la fuente actual: guardia de idioma ignora tilde aislada de nombre
sin evidencia léxica española; frases me llamo/te llamas/se llama con límites
de palabra. Baseline7fail12pass; control de substring2fail19pass. Final21pass,
cinco dueñas1364pass0skip6,14s; Fast verde/build1,22s0warnings0errors.
398 mente completa:5/8 útiles,3fallos (guardado inventado, sujetoLina, observación
llamas). José inglés sigue metadata mixed. No declarar393bT4 resuelto sólo por idioma.

399/400 rechazados, sin fuente ni promoción. Ocho payloads fijos, mismoQwen3.5-4B,
backendb9980, max_tokens1024;399 compara off0/on512 conT0:3/8→3/8+parcial.
400 cambia sólo sampler al thinking general recomendado:5/8, pero regresa
recuerdo de sesión, invierte sujetoLina y agota lecturaEN con texto interno.
GPU pico3175,5625MiB; RAM3880,71/3906,91/3905,92MiB respectivamente;
duración8,015/40,86/48,578s. Sin infracciones, manifiesto registrado intacto.
RESULT/PINS astra-thinking399 y astra-thinking400 completos. No repetir perfiles,
semillas ni presupuestos comparables buscando una corrida favorable.

Siguiente401: medir contrato existente facts.requiredFacts con el valor privado
realmente proyectado, sin nuevo prompt, caché de nombre ni roles de tool ya
rechazados347. UserMessagePolicy.RequiredStructuredLiterals2531 conserva reason/title
pero omite records; ModelMessageComposer91–109 transporta requiredFacts; compose
llm9110–9475 lo valida ya. Reusar harness378b para reconstruir hechos y afirmar
igualdad del primer payload baseline393b. Controles otras entidades, vacío y
redacción; valor retenido no prueba sujeto correcto. No401 preparado aún.

Descartes previos:3909B2/4 sin mejora;391prompt5/8→4/8;392resolvedorcontextual5/10
confunde tercero/usuario y persistencia;376catálogo público de memoria rechazado.
No reabrir sin dato nuevo. Investigación y RESULT/PINS por tramo; historial
CHECKPOINT_400_ANTES_401.md y CHECKPOINT_393_ANTES_397.md.

Falta C03 íntegro: resolver ocho rutas/base encuesta y fallos264 (0 requisitos
validados finales); congelar100 humanos frescos con procedencia/contexto (0
certificados); averías/recuperación; UI real, voz física/ASR/wake y recursos
conjuntos≤4GB; runtime/instalación/contratosC04–C09; Full final verde y publicación.
Sin bloqueo externo, porcentaje/plazo inventado ni cierre parcial.
'''
handoff = '''# Handoff C03 — 2026-09-08 — checkpoint400 — EN_CURSO

Completar todo C03 según C03_ASTRA_AUTORIDAD.md y C03_RESPUESTA_VERAZ.md.
Goal-c03/2bf3d4c, WIP ajeno y propio conservado, main intacta. No agentes ni
Full durante reparación. BAXY manual cerrado; modelos/productos/pruebas cerrados.
Encuesta final742/rev1248 y16 mensajes directos consolidados; automáticos excluidos.

Última fuente: .NET393(nombre explícitamente guardado)1996pass0skip/Fast17,97s;
Python395(historial en retry)1343pass/Fast1,52s; Python397(idioma/tilde y frases
con límites)1364pass0skip6,14s/Fast1,22s. No Full ni promoción. RESULT/PINS por tanda.
393b producto1útil1parcial4fallos: memoria devuelveJordan pero composición niega
lectura/invierte sujeto; genérico fuerza persistenciaJordan sobre contextoÁlvaro.
398 mente5/8: idioma mejora pero persisten sujeto y falso guardado.
399 thinking5123/8+parcial,400sampler recomendado5/8 con regresión; rechazar ambos.
LecturaEN agota1024tokens con contenido interno, sujetoLina incorrecto y memoria
de sesión regresa. GPU3175,56MiB/RAM≈3906MiB; modelo registrado intacto.

No repetir prompt391, resolvedor392, catálogo público376, tool roles347,
perfil/semillas399–400 ni9B390 sin dato nuevo. Conservar diferencias entre
3944/5+parcial y3965/5 pese a payloads idénticos: variación de inferencia.

Siguiente: diagnóstico401 reutilizando facts.requiredFacts. Leer
UserMessagePolicy.cs:2531/2563 y ModelMessageComposer.cs:91; sólo reason/title
cruzan contrato literal, no records. Medir valor proyectado único en compositor
real, con baseline idéntico393b, controles valores nuevos/vacío/redactado.
Harness scratchpad/c03-cancel-scope378b.py reconstruye facts y verifica payload.
Sin source401 aún; retener literal no prueba sujeto correcto ni resuelve genérico.

Cierre pendiente: ocho rutas/base encuesta/fallos264;100humanos frescos0certificados;
averías, UI/voz física/recursos conjuntos, runtime/instalación/contratosC04–C09,
Full verde y publicación. CHECKPOINT.md manda; no goal completo/bloqueado.
'''
(folder / 'CHECKPOINT.md').write_text(checkpoint, encoding='utf-8')
(folder / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
path = folder / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8-sig'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
             checkpoint='400 closed. Python397 owners1364pass0skip/Fast1.22s; NET3931996pass0skip/Fast17.97s.399/400 reasoning profiles rejected. No model/product/test active; runtime unchanged.',
             continuation='Next401: measure existing requiredFacts with projected memory value against actual393b baseline, new values and empty/redacted controls. No new prompt/name cache/tool roles. Full C03 remains active.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
