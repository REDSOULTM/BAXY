# C03 — tramo33: configuración documentada y propósito del conocimiento

2026-09-06. Goal-c03, HEAD 2bf3d4c5406b7bf1c230f7cbb0b2c3de6d74fc49.
C03 EN_CURSO. El tramo anterior consolidó instrucciones y activó el goal;
este tramo produce evidencia nueva y una reparación, por tanto es progreso.

## Investigación y decisión

Se contrastaron ficha Qwen3-4B-Instruct-2507, generation_config, tokenizer oficial,
paper de Qwen3 y servidor llama.cpp b9980. Experiencia de usuario reproducible:
issue 20809, b8429/Vulkan; su workaround --reasoning off ya existe en BAXY.
Las fuentes, límites y revisión exacta están en INVESTIGACION_MODELO_C03.md.

`astra-qwen-documented-profile/` contiene 69 llamadas reales al servidor:
54 de conversación (6 casos × 3 capas × 3 perfiles/semillas) y 15 de primaria
(5 casos × 3). Perfil greedy seed0 frente a Qwen documentado seeds0/17.
LlmRuntime sólo inicia/cierra; no hay wrapper de chat, validadores o reintentos
en las llamadas directas. Las capas posteriores usan mensajes preparados por
BAXY; se especifica la distinción. No hay efectos del PC ni aceptación fresca.
84,89 s, GPU 3497,56 MiB, RAM 3612,91 MiB, proceso 30161 terminal0.

Props confirma contexto 4096/slot, tres slots y defaults de sampling distintos
de los recomendados. Template GGUF tiene lógica thinking que el oficial no tiene;
los dos renders simples comparados son iguales, no se ha demostrado degradación
causada por ese delta. Se conserva el template y el registro.

No promover muestreo: no corrige volumen contextual ni negación y añade una
afirmación de volumen ya bajado sin lectura. Steam con servidor solo genera
explicación, pero corta a512 y puede inventar detalles. La negación simple ya
falla sin BAXY; con sus prompts además puede aparecer SIEMPRE. No culpar a una
sola capa. Las 69 salidas están completas en PRUEBAS_MODELO_DOCUMENTADO_C03.md;
el informe no afirma adjudicación exhaustiva de cada hecho como aceptación.

## Reparación implementada

`llm._conversation_presentation_shape`: knowledge no puede convertirse en
observation_ack por heurísticas de adverbios/sustantivos. La petición literal
«ahora explicame que es Steam» se convertía en una confirmación atribuida al
usuario y recibía 64 tokens. Ahora conserva política de conocimiento y128.
El seguimiento conserva su contrato; no se añade una lista de frases, respuestas
fijas, otra capa o autoridad para ejecutar. Tres pruebas de frontera guardan
petición, política, presupuesto y una sola llamada con prefijos temporales ES/EN.

`astra-knowledge-owner-live/`: los mismos seis casos conocidos por chat normal,
con wrapper/guardas y perfil existente; 7,44 s, GPU3495,56 MiB, RAM2819,95 MiB.
Steam recibe explicación útil; capital, agua y no-subir se conservan. Audio
no-silenciar sigue incorrecto. Aire conserva respuesta principal correcta pero
añade una afirmación problemática sobre H₂O; se deja NO CERRADO en el dictamen.
No se ejecutaron acciones; no acredita UI. Proceso terminal0, registro intacto.

## Validación

- `pytest tests/test_turn_policy.py tests/test_compose_contract.py tests/test_c03_request_preservation.py -q`:
  1033 pass, 0 skip, 5,84 s. `scratchpad/c03-qwen-profile-owner.log`.
- Ruff en fuente/prueba editadas: passed.
- `scripts/test_source_quality.ps1`: Fast verde, build0errores/avisos;
  proceso95570 terminal0, `scratchpad/c03-qwen-profile-fast.log`.
- Full NO ejecutado; corresponde sólo al candidato de cierre.
- Sellos dependientes actualizados por el mecanismo existente:
  llm e341940983cbf3ca898da89ad5bf43b1babbb0ba77dd393fe03dd498bec23ea2;
  STT programtree 49b82ee43d56796e4fb8bc6d362190cefb12c737e7f0917f902d5eba96e23bbe.
  __main__ y effect_intent sin cambio en este tramo.

## Continuar

No repetir búsqueda de sampler ni llamar modelo-solo a la antigua ablación con
wrapper. No repetir Full ni modificar prompts para esconder un texto particular.
Las tres causas del panel integrado de20 siguen abiertas: fecha (veto posterior
a primaria correcta), volumen absoluto (primaria relativa y contador multiple)
y negación (presentación knowledge no expresa correctamente la restricción).
El nuevo control standalone de aire añade un problema de exactitud a revisar;
la última tasa integrada conocida sigue siendo la anterior17/20, no se ha recontado.

Siguiente trabajo: conservar una representación coherente del propósito actual
entre interpretación y presentación/grounding. En particular, una restricción
no pide datos para ejecutar, y la ausencia de una frase en un diccionario de
dominio no demuestra incompatibilidad semántica. Reutilizar contratos y guardas
existentes; contrastar negativos válidos/consultas/efectos y referencias con y
sin antecedente antes de promover una modificación de autoridad. Ver causas
y rutas exactas en ASTRA-TRAMO-32. Todos los procesos propios están terminales.
