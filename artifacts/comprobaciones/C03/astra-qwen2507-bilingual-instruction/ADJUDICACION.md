# Desarrollo: instrucción bilingüe

174.53 s; GPU 3497.56 MiB; RAM 5079.30 MiB; registro intacto.
8/12 publicados; máximo 6/12 útiles. DESCARTADA; sin cambio de prompt productivo.

| Turno | Adjudicación |
|---|---|
| 1, 3, 4 | Hora y consulta compuesta fieles. Inglés del audio telegráfico. |
| 2 | Datos fieles, pero «muted» incumple español explícito del compositor; calidad de idioma débil. |
| 5 | Hora fiel, «please» pegado a la respuesta sin función: no natural. |
| 6–9 | composition_failed: falla visible. |
| 10 | Traducción repetida, «a invisible», duplicación final y analogía defectuosa: falla calidad. |
| 11–12 | No abre Paint; capital Lima correcta. |

La reparación del wrapper sí aparece en turn-audit: t9 toma conversación de
conocimiento con response_language=mixed, sin candidatas de copia. El rechazo
posterior es de presentación: el guard léxico descarta prosa como «Una copia de
seguridad es como un backup…», fuerza retries y éstos agotan JSON. Ésta es la
última variante de wording; no continuar cambiando la misma instrucción.

La plantilla oficial sí conserva mensajes system sucesivos; la hipótesis de que
sólo se enviara el primero no está sustentada:
https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/raw/main/tokenizer_config.json
