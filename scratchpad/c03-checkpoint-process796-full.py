"""Persist active Full and exact restart instructions without touching its source."""
from datetime import datetime, timezone
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
note = ('796 candidato17fuentes selladas;3248Pythonpass0skip,Fast0,provider6pass e integración33pass antes del último límiteApp. '
        'Full inicial85398abortado al detectar declaraciones actuales obsoletas; log conservado,no pass. '
        'Declaraciones actualizadas,programa4079a0462f7,V8control5pass. Full completo activo39408/full-final.log; '
        'no editar fuente.797 preparado mismos50casos795, exige Full0. Qwen elegido;28/714/0,sinadopción.')
p = base / 'CHECKPOINT.md'
p.write_text(note + '\n\n' + p.read_text(encoding='utf-8-sig'), encoding='utf-8')
p = base / 'RELEVO_ACTIVO.json'
state = json.loads(p.read_text(encoding='utf-8-sig'))
state.update(checkpoint=note, confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
             workStatus='process796_full_running',
             activeValidation={'name': 'process796_complete_full', 'session': 39408,
                               'log': 'artifacts/comprobaciones/C03/PROCESS_REPAIR796/full-final.log',
                               'source_immutable': True, 'source_pins': 17},
             continuation='Poll39408; preserve source until terminal. Read Full outcome. If green, run prepared c03-process-batch797.py with registeredQwen, then adjudicate50 against frozen795 criteria and publish adopted796 only with valid evidence. No new model comparisons.')
p.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(base / 'HANDOFF.md').write_text('''# Handoff C03 — proceso796 / Full activo39408

Goal activo en Goal-c03. Objetivo attachment58161a42/SHA621020a31266e98d043b07f214e8a8c6c3cb48f1287d27e411bf805402dadb86. Main intacto5f572ee1; HEAD público65761a14 (793). Encuesta742/rev1248 y WIP ajeno intactos:28cubiertos/714abiertos/0NA. BAXY manual cerrado. Qwen3-4B-Instruct2507Q4_K_M elegido; no comparar modelos otra vez.

**ACTIVO: Full796 sesión39408**, salida PROCESS_REPAIR796/full-final.log; al terminar escribe FULL_EXIT.json. No editar17fuentes selladas hasta terminal. Pollmisma39408, no relanzar por tiempo. Full7 previo tardó1543s/26min; integración9m40s. Full inicial85398 terminó1poraborto deliberado: detectamos tres declaraciones de fuenteactual aún ligadas793; logfull.log+FULL_INITIAL_ABORT.json preservados,no pass. Declaraciones ya actualizadas sin tocar corpus/recibos/veredictoshistóricos; controlV8:5pass0,57s. No más pruebas activas:5115falló compilación de fixtureDictionary,87384provider6pass,5896318pass,6405733pass,80153rojo12fallos,867903248pass,22675Fast0; todas recogidas.

**795 baseline:**50/50terminales,4pass/46fail;48385terminal0 recogida. REPORT/ADJUDICATION privados/literales en LOCALAPPDATA/BAXY/C03-process-batch795-private/review.json y RESPUESTAS.md; públicos PROCESS_BATCH795.4pass:H0169,H0669,memory_rank-01 y06.3.42GiBVRAM/2.39GiBRAM del árbol sinUI/voz;258,594s,sinviolaciones. Los fallos no son evaluación nativa del modelo.

**796 candidato NO adoptado:**CPU actual mediante delta150ms y denominador lógicoWindows; conteo observado separado de filas;PID y50filas conservados por Kernel y App (límite48k); reconocimiento de consultas/count/rank ES/EN/mezcla; cardinales/métricas cerradas no se pierden en normalizador; proyección expresaCPUactual yMBresidentes.17pins ysnapshot privadoC03-process-source796-private en PROCESS_REPAIR796/SOURCE_PINS.json; initial14behaviorpins conservados. PROGRAM407=9a0462f762eeb763ffb676f5330ce67706a80e0388c636ad1bada16f30a1421c.3248Pythonpass0skip/89,31s;Fast0/Release22,87s;provider6pass0skip;33integración antes de último límiteApp; Full comprueba candidato final. Se movió prueba negativa Qué proceso me come tanta RAM a positiva porque ya hay operación compatible; negativos de biología/definición/pasado/negación conservados. AgentesRO terminaron; PIDs factual no está prohibido por los filtros de prosa.

**Siguiente:** recoger39408 y leerrojosconcretos sihay. SiFull0, ejecutar pythonregistrado -Xutf8 scratchpad/c03-process-batch797.py; ya preparado, no rerunpreparers. Usa mismo panel795con50casos/9humanos+41variantes, pins796+764, manifiestoQwen igual, perfilprivadonuevo797, recursosguardados. ExigeFull0 al arrancar. Auditor scratchpad/c03-review-process797.py conservaformato795. No editarfuente durante797. Adjudicar todos contraobservacionesfrescas antes depromover y actualizarcoverage. App-memory aún carece de membresía/agregación: no acreditarlo conunproceso. Fuente796requiere publicaciónconFullverde y mejora real.

**Después:** hay116abiertos con léxicoapps/ventanas y77audio/media (grupos solapables,no cobertura), ver CONTINUATION.md. CierreC03 aún requiere742generalizados,reserva100,UIreal,loopback/AEC,recursosconjuntos≤4GiB,matriz/continuidadC04–C09 yFullfinal. Source declaration refresh scripts c03-seal-process796-declarations.py y resealer original no se rerunean. PreservarWIPajeno, publicarpathsexplícitos, mainintacto.
''', encoding='utf-8')
print(note)
