from pathlib import Path
import json
import shutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
result = json.loads((base / 'astra-public-host3/RESULT.json').read_text(encoding='utf-8'))
assert result['exitCode'] == 0 and result['registrationUnchanged']
assert '2819 passed' in (root / 'scratchpad/c03-tranche41-owner.log').read_text(encoding='utf-8')
assert 'source_quality_gate_passed: mode=Fast' in (root / 'scratchpad/c03-tranche41-fast.log').read_text(encoding='utf-8')
checkpoint = base / 'CHECKPOINT.md'
archive = base / 'CHECKPOINT_HISTORICO_HASTA_40_Y_REANUDACION_41.md'
if not archive.exists():
    shutil.copyfile(checkpoint, archive)
state = f'''# C03 — CHECKPOINT — tramo41 completado, goal EN_CURSO

Goal-c03, HEAD2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49. Sin commit/push;
main/ajenos intactos. Sin bloqueo externo. La referencia a tramo32 del goal es
histórica. Respetar C03_ASTRA_AUTORIDAD.md, identidad y techo total4096MiB.

## Fuente y mediciones vigentes

La candidata AUTO es ahora default de llm.py y evita el guardia de tipo secundario.
No está aceptada como solución completa: negación compuesta y seguimiento fallan.
Contrato nativo sigue rechazando truncación, operaciones ajenas y argumentos.
Presupuesto256 evita un agotamiento, pero native-budget13 todavía da Steam/Microsoft,
SSID/contraseña, hora falsa tras restricción y fallos de interpretación/composición.

Ablación factorial12: políticas × historial, mismo Qwen/configuración. Sin historial
ajeno y con políticas, Steam/SSID correctos; quitar políticas trunca varias salidas.
Se hereda request_topic para limitar sólo el contexto de generación en definiciones
nuevas de un tema simple; historial almacenado y temas/referencias conocidos quedan.
definition-context7 demuestra Steam/SSID correctos,5/7útiles. Seguimiento SSID falla
antes de chat en observation_not_recital: _catalog_answers_the_request decide
web.search sin historial. DNS: chat correcto, hostwww.google.com vetado como código;
recomposición acaba peor. Estas dos causas están capturadas, no son hipótesis vagas.

Verificadores Python y App reparados para hosts explícitos http(s)/www; códigos
externos al host y demás fugas siguen bloqueados. public-host3 exit0,
{result['elapsedSeconds']}s,GPU{result['gpuPeakMiB']:.2f}MiB,registro intacto.
Su dictamen y todas las respuestas están en PRUEBAS_SELECTOR_Y_CONTEXTO_C03.md.

## Validación / procesos

Siete suitesPython:2819pass,0skip,53,66s (64620terminal0).
.NET C03FactPreservation+Goal06VisibleVoice:45pass,0skip,3s (22559terminal0).
Fast72324terminal0,build21,32s,0errores/avisos. Ruff/diffcheck verdes.
No Full ni UI41; últimaUI29 no certifica este candidato. Todos los procesos propios
de medición cerrados:52417,27371,81526,85133. Sin dos LLM simultáneos.
Pines: llm a9a4d61a022ba227a623d5bdf6bbb5013ad8fd6659c6158d60d276d98b80c763;
main943b077761c897ef6f6904b5d6339bc400c6ffd67b01d6b0f545981e73f08a23;
STT afed307eeea1956f3e75b2a97ebb756292ddc0696e1380a1d5c6854b3a54525b.
Runtime Qwen3-4B-Instruct-2507Q4_K_M, llama.cppb9980CUDA12.4,KVq8,3×4096slots,
ngl99; registroSHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.

## Siguiente acción

Resolver el flujo de alcance/contexto completo en __main__.py:6210 y
effect_intent.unresolved_compound_contract. No reponer sólo el parche de cláusulas39
ni el guardia de tipo descartado40. La primaria puede acertar y observation_not_recital
volver a degradarla. Un contrato genérico de negación impide horaES; una cláusula
social EN se cuenta como efecto desconocido. No quitar garantías por cardinalidad.
La nativa aún puede abstenerse mal con catálogo/historial de producto.

Faltan desarrollo, detalle/truncación,100reservados/procedencia/autoría/contexto,
ocho rutas,averías/recuperación/UI/recursos,contratos posteriores,Full/publicación.
No convertir5/7o3/3 de controles consumidos en porcentaje del goal.
Retirar ramas nativas legacy inalcanzables en _decide_turn al adoptar candidata.
Backup pre-candidata: scratchpad/c03-native-primary-before/llm.py y
test_turn_policy.py. No revertir otros cambios acumulados.

Detalle: ASTRA-TRAMO-41.md. Investigación heredada: INVESTIGACION_MODELO_C03.md,
INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md. Histórico del antiguo checkpoint
conservado en CHECKPOINT_HISTORICO_HASTA_40_Y_REANUDACION_41.md; no releerlo entero.
'''
checkpoint.write_text(state, encoding='utf-8')
(base / 'HANDOFF.md').write_text(state, encoding='utf-8')
p = base / 'ASTRA-TRAMO-41.md'
s = p.read_text(encoding='utf-8')
s = s.replace('Fast72324 en curso al escribir esta nota.', 'Fast72324 terminal0, build21,32s,0errores/avisos.')
s = s.replace('Public-host3 preparado, pendiente\n  de que Fast termine para ejecutar el binario recién construido.',
              f"Public-host3 completado: exit0,{result['elapsedSeconds']}s,GPU{result['gpuPeakMiB']:.2f}MiB,registro intacto; ver dictamen literal.")
p.write_text(s, encoding='utf-8')
