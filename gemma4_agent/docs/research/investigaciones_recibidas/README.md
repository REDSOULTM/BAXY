# Investigaciones recibidas — dejá acá las respuestas de Claude

RED: pegá cada investigación que te devuelva Claude en un archivo `.md` en ESTA
carpeta, nombrado igual que el prompt que la originó, así el agente la encuentra
y la aplica sin confusión.

## Cómo nombrar cada archivo (importante)
Usá el MISMO número/tema que el prompt. Ejemplos:

| Prompt enviado | Pegá la respuesta en |
|---|---|
| PROMPT_RESEARCH_1_toolcalling_structured.md | `investigaciones_recibidas/1_toolcalling.md` |
| PROMPT_RESEARCH_2_memoria_personalizacion.md | `investigaciones_recibidas/2_memoria.md` |
| PROMPT_RESEARCH_3_verificacion_recovery.md | `investigaciones_recibidas/3_verificacion.md` |
| PROMPT_RESEARCH_4_contexto_multiturno.md | `investigaciones_recibidas/4_contexto.md` |
| PROMPT_RESEARCH_5_aprendizaje_proactivo.md | `investigaciones_recibidas/5_jarvis.md` |
| PROMPT_RESEARCH_6_estabilidad_no_crash.md | `investigaciones_recibidas/6_estabilidad.md` |
| PROMPT_RESEARCH_7_nlu_comandos_ambiguos.md | `investigaciones_recibidas/7_nlu.md` |
| PROMPT_RESEARCH_8_automatizacion_gui_desktop.md | `investigaciones_recibidas/8_gui.md` |

(El número al principio del nombre es lo que importa — el agente mapea por número.)

## Cuando vuelvas a pedir que las apliquemos, decí algo como:
"Aplicá la investigación 1" o "ya dejé la 1, 5 y 7 en investigaciones_recibidas,
empezá por la 1".

## Metodología que el agente seguirá al aplicar cada una (regla de RED)
1. Leer la investigación + el código real del subsistema.
2. Verificar que cada afirmación es cierta en NUESTRO build/entorno (los informes
   ya fallaron en ≥4 detalles: -ub, ctx-checkpoints, n_swa, FR-CoT-en-Gemma).
3. Definir gate (qué se mide, criterio de éxito) ANTES de tocar.
4. Cambio mínimo → medir con scripts/smoke_e2e.py BAJO vram4 → commit si mejora.
5. Si dudoso: opt-in (flag, default OFF). Si rompe: revertir + documentar.

Ver PROMPT_RESEARCH_INDEX.md para la tabla completa de los 8 temas.
