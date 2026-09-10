"""Seal the observed diagnostics and their limitations; no product changes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from baxy_mind.llm import _payload_fact_defect

BASE = ROOT / 'artifacts/comprobaciones/C03'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
OUT = BASE / 'INVENTORY_PROJECTION759'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for number in (758, 759):
    private = PRIVATE / f'C03-inventory-projection{number}-private'
    plans, results = read(private / 'planned.json'), read(private / 'results.json')
    # Validate against the unchanged observation, not the extra descriptive fields.
    prefix, tail = plans[0]['payload']['messages'][1]['content'].split('\nsituation: ', 1)
    observed, _ = json.JSONDecoder().raw_decode(tail)
    rows = []
    for plan, result in zip(plans, results, strict=True):
        assert plan['arm'] == result['arm']
        choice = result['response']['choices'][0]
        reply = choice['message']['content']
        rows.append({
            'arm': result['arm'], 'seconds': result['seconds'],
            'finish_reason': choice['finish_reason'], 'usage': result['response']['usage'],
            'within4s': result['within4s'],
            'original_validator_defect': _payload_fact_defect(reply, observed, prefix),
            'returned_identity_entries': sum(line.startswith('- ') for line in reply.splitlines()),
            'expected_identity_entries': len(observed['seen']['windows']),
            'response_sha256': hashlib.sha256(reply.encode('utf-8')).hexdigest(),
        })
    adjudication = {
        'rows': rows, 'all_responses_manually_read': True,
        'manual_verdict': (
            'Both retain20 identities. Baseline omits partial-page disclosure. Added instruction says20 visible found versus24 observed, without binding20 to the returned page. Neither accepted.'
            if number == 758 else
            'Both retain20 identities. Baseline omits partial-page disclosure. Candidate states partial20/24 but invents that these are the most recent windows. Provider does not observe recency or chronological ordering. Candidate rejected even if lexical validator accepts it.'
        ),
        'accepted_product_repairs': 0, 'survey_credit': 0,
        'private_planned_sha256': sha(private / 'planned.json'),
        'private_results_sha256': sha(private / 'results.json'),
    }
    write(BASE / f'INVENTORY_PROJECTION{number}/ADJUDICATION.json', adjudication)
    print(json.dumps({'diagnostic': number, 'rows': rows}, ensure_ascii=False))

report = '''# Modelo, integración y sobrecarga: qué está demostrado

La preocupación del dueño es correcta: una regla sin nombre de modelo también puede favorecer las formulaciones que se usaron para ajustarla. Una comparación integrada no basta para juzgar al modelo original. No afirmamos que todo BAXY esté ajustado para Qwen; sí hay pérdidas de integración demostradas que deben corregirse y separarse de sus errores nativos.

La primera comparación696–698 conservaba instrucciones de BAXY y sus860 respuestas no constituían aislamiento nativo. La corrección699 ejecutó las mismas50 tareas completas en cada uno de seis perfiles:300 respuestas sin system, herramientas ni schema de BAXY. No se dividió el panel en dos mitades. Se usaron recetas y plantillas específicas, con diferencias locales de backend, cuantización, contexto y presupuesto declaradas. Es una comparación de perfiles locales, no una equivalencia demostrada con los modelos originales BF16 ni un ranking universal. Véase [la referencia nativa699](../K2_HORIZON_NATIVE699/REPORTE699.md).

737 mantuvo hechos, backend, plantilla y sampler de K2 en57 pares, cambiando sólo pregunta directa frente a prompt de redacción BAXY. Hubo25 aciertos compartidos,14 sólo con BAXY,3 sólo directos y15 pares sin respuesta acreditable. Demuestra ganancias y pérdidas del prompt; no prueba neutralidad del resto de las capas ni variabilidad entre semillas. [Comparación737](../FACTS_PROMPT737/REPORT.md).

752B fue una regresión de producto con73 turnos y Qwen, no una nueva comparación de modelos. Dio49 acreditados,22 fallos sustantivos y2 sensibles a precisión sin acreditar. Entre los defectos: una respuesta de foco correcta fue rechazada18 veces por la gramática de BAXY; son repeticiones de un caso. [Informe752B](../STATUS_BATCH752B/REPORT.md).

## Primera pérdida localizada en el inventario

753 observó la frontera real del producto, sin alterar argumentos, resultados ni excepciones. La primera petición contenía1533 tokens de entrada; generó256, terminó por límite y tardó3,922s. El redactor gastó salida en coordenadas, tamaños y estados no pedidos antes de completar20 identidades de una página de24 ventanas observadas. Su reintento ya no disponía del presupuesto de cuatro segundos. No fue desbordamiento del contexto4096:1789 tokens totales. La ejecución terminó filtered/null. [Diagnóstico753](../COMPOSE_BOUNDARY753/DIAGNOSIS.json).

Los siguientes pares conservaron la misma observación congelada, el modelo, el backend y los ajustes. Son diagnósticos de una causa concreta, no cobertura de encuesta ni benchmarks de modelos.

| Prueba | Única intervención del par | Resultado |
|---|---|---|
|754|Añadir instrucción de concisión y alcance|Ambos brazos agotan4s; respuesta final no observada.|
|755|Repite el par con OMP/MKL4 y TOKENIZERSfalse como producto|Ambos agotan4s. Igualar esos valores no explica la diferencia de velocidad.|
|756|Observa ambos finales hasta15s, sin cambiar max256 ni referencia4s|6,484/6,828s; ambos cortados. La instrucción sola no completa la lista.|
|757|Sólo retirar detalles por ventana no pedidos; conservar20 identidades y metadatos|6,547s/corte frente a3,750s/final completo. El segundo aún omite que la lista es parcial.|
|758|Ambos con proyección de identidades; añadir la misma instrucción754 al segundo|3,453/3,422s, ambos completos. El segundo aún confunde20 encontradas con24 observadas; alcance insuficiente.|
|759|Ambos con proyección de identidades y prompt original; añadir significado factual de página|3,578/3,953s. El segundo indica lista parcial20/24 pero inventa que son las más recientes. Rechazado.|

La proyección757 reduce1533 a678 tokens de entrada y256 cortados a153 completos de salida. Se mantienen todas las entradas, repeticiones, títulos/procesos y metadatos; no se reduce el número de ventanas para mejorar el resultado. Es una mejora parcial demostrada, todavía no una reparación aceptada.759 expone además un hueco del validador si éste permite la recencia no observada; la adjudicación humana sigue rechazándola.

El servidor aislado decodificó aproximadamente44–50tokens/s frente a unos76 en753. El cwd difiere: el producto hereda el directorio del intérprete y los pares usan el directorio del backend. No se ha demostrado que sea la causa; tampoco la explican los ajustes OMP/MKL ensayados. Los tiempos dentro de cada par permiten observar esa intervención; no atribuir diferencias entre entornos sin medir sus condiciones efectivas.

El pico del servidor en757 fue3495,56MiB de VRAM y717,98MiB de RAM residente. No equivale al consumo de BAXY con UI, voz y el resto del árbol. Muestras cada250ms pueden omitir picos breves. Todos los servidores de estos diagnósticos terminaron; sesiones32057,90883 y63743 recogidas con exit0. El primer lanzamiento758 con `py` no llegó a abrir servidor: faltaba psutil en ese intérprete. Se ejecutó después con el Python registrado, sin instalar ni cambiar dependencias.

## Decisión y continuación

No se adopta ningún parche, modelo, prompt ni nuevo presupuesto por estos pares. No se concede cobertura:26 cubiertos,716 abiertos,0 no aplicables. No hay una decisión pendiente del dueño.

La siguiente reparación debe hacer explícito el significado de los datos que BAXY entrega al narrador y conservar sólo lo pertinente a la petición, manteniendo el snapshot canónico, todas las identidades y la validación de veracidad. No añadir otra formulación de concisión:754–756 no resolvieron el defecto. No aceptar recencia, orden ni otra propiedad que el proveedor no observe. Aplicar las mismas exigencias semánticas a todos los modelos, con sus plantillas y recetas propias, y verificar la primera transformación incorrecta. Después de una fuente validada, repetir la categoría completa73 y las variantes necesarias; una prueba de esta observación no cierra su familia.

Sin fuente productiva editada no corresponde otra suite ni Full. Siguen pendientes cobertura generalizada, reserva, UI real, loopback/AEC, recursos conjuntos, matriz, continuidad y Full de cierre. C03 permanece activo. Las entradas, hechos del escritorio y respuestas completas se conservan sólo en los directorios privados locales C03-compose753-private y C03-inventory-*; los artefactos públicos contienen causas, métricas y huellas.
'''
(OUT / 'REPORT.md').write_bytes(report.encode('utf-8'))

checkpoint = '''759 terminado; sesiones32057/90883/63743 recogidas exit0.757 proyección conserva20identidades/metadatos: entrada1533→678tokens; salida256cortada→153completa;6,547→3,750s, pero falta alcance parcial.758 agrega cláusula754:3,453/3,422s, todavía20encontradas vs24observadas ambiguo.759 añade semántica factual de página:3,578/3,953s; declara parcial20/24 pero inventa recencia. Rechazado incluso si validador léxico acepta. No se adopta fuente/prompt/modelo ni presupuesto. REPORT/ADJUDICATION en INVENTORY_PROJECTION759 y758. No inferencia activa.

El dueño reitera que integrar reglas afinadas paraQwen puede perjudicar otro modelo. Verificado:699 aisló300respuestas (50completas×6perfiles) sin system/tools/schemaBAXY;696–698 no lo aislaban.73757paresK2 muestra14aciertos sóloBAXY/3sólo directo, no rankinguniversal. Las pruebas actuales son atribución de producto, no descarte nativo. Quedan26/716/0, sin pregunta pendiente. Próximo: proyección factual general y verificación de propiedades de orden no observadas; no repetir cláusulas fallidas ni relajarjuicio. Producto751 intacto; no Full nuevo por diagnóstico.

'''
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes(checkpoint.encode('utf-8') + cp.read_bytes())
handoff = '''# Handoff C03 — diagnóstico759 — 2026-09-10

Objetivo íntegro en el fichero de goal activo; rama Goal-c03, main intacto. C03 sigue activo: encuesta742/rev1248,26cubiertos/716abiertos/0NA; ninguna pregunta pendiente.

Fuente vigente751, commit4d3885c72dec5499c50f41e2b9a736c9ce62ac8e; última evidencia anterior878dd054. No se editó producto en753–759. Publicar el conjunto diagnóstico y verificar remoto. WIP antiguo ajeno preservado.

Leído y adjudicado: COMPOSE_BOUNDARY753 y INVENTORY_PROMPT754/755, INVENTORY_OUTPUT756, INVENTORY_PROJECTION757/758/759. REPORT.md de759 resume método, resultados y límites; payloads/respuestas completos privados en LOCALAPPDATA/BAXY/C03-compose753-private y C03-inventory-*-private. No servidores activos;32057/90883/63743 y sesiones anteriores ya terminales recogidas.

Confirmado:753 no desborda contexto; redactor gasta max256 en geometría no pedida y corta lista20de24. Reintento agota4s.757 retirar sólo detalles no pedidos conserva20identidades y metadatos;6,547→3,750s, entrada1533→678,256tokens cortados→153completos. Aún falta revelar parcialidad.758 cláusula754 no lo resuelve.759 deriva significado factual de página; sí revela parcial20/24, pero inventa recencia. Ninguna respuesta candidata aceptada ni fuente adoptada. Ver ADJUDICATION.

Descartado: repetir instrucciones de concisión solas (754–756). OMP/MKL4 no explica44–50t/s aislado frente a76producto. cwd diferente es hipótesis, no causa demostrada.4s es límite implementado/de diagnóstico, no ley C03; C07 certifica latencia. No cambiar exámenes ni usar más espera para llamar éxito a fallos4s.

Siguiente acción: reparar la representación semántica de la página en la frontera de prosa (llm.py:3413–3466,9321–9338), preservando snapshot,20/50identidades y hechos solicitados; no otro prompt de concisión. El validador window_prose_facts.py:330–435 ya distingue count/página frente a observedCount/totalCount pero no rechaza toda recencia/orden inventada.759 acredita ese hueco; mantener adjudicación manual estricta. No adoptar proyección sin controles de alcance/orden, páginas completas/parciales/vacías y pedidos de geometría. Cada modelo usa su receta propia; verdad y catálogo compartidos. Después fuente validada, repetir categoría73, no repetirla sin cambio.

Otros bloqueos752B: dominio de inventario H0209/H0663/EN; foco correcto rechazado por gramática; lecturas omitidas/frescura; RAM total llamada disponible; interfaz-up no es Internet; CPU acumulada no es consumo actual. Sólo estos bloqueantes, antes de precisión menor. Tests de modelos simulados no acreditan modelos reales.

Validación fuente751:4194pass+121subtests; finales355pass/1skip ambiental, con solapamiento; Fastexit0. Full7 histórico:4574.NETpass/1skip agregado+16omisiones opt-in,11399Pythonpass/3skips+466subtests, exit0. No repetir por diagnóstico; Full final pendiente. Si cambia Python, actualizar declaraciones actuales STT y V8/program fingerprint407, sin tocar sellos históricos. Registro privado SHA f6f2b1ac779c767b59740c3a2da2532b53e1044596eac329597f9b8c1c20ebff intacto.

Faltan cobertura completa, reserva, UI escritorio/voz/loopback vsAEC, recursos conjuntos≤4GiB, matriz/continuidad y Full final. No cerrar/reducir goal. Mantener main y WIP ajeno. BAXY manual cerrado por petición del dueño.
'''
(BASE / 'HANDOFF.md').write_bytes(handoff.encode('utf-8'))
relevo_path = BASE / 'RELEVO_ACTIVO.json'
relevo = read(relevo_path)
relevo.update(
    confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    workStatus='inventory_diagnostics759_adjudicated_no_adoption',
    activeValidation=None,
    checkpoint=checkpoint.split('\n\n')[0],
    continuation='Repair semantic projection and unobserved-order claims before another registered73 regression; see INVENTORY_PROJECTION759/REPORT.md. No product adoption or model promotion. Goal remains active.',
    previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Captured and adjudicated projection counterfactuals757–759, isolated token waste, retained partial-scope and invented-recency failures; verified independent native methodology699/737. No source edits or survey credit.',
)
write(relevo_path, relevo)
