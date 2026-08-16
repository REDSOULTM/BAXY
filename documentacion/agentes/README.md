# Recuperación de subagentes Codex

Esta carpeta permite reutilizar el trabajo de los subagentes ejecutados en el
hilo:

019f5027-c684-75a1-a47b-5af2edd2339b

La exportación actual reconstruyó 322 sesiones: 302 directas y 20 anidadas.
De ellas, 303 tienen finalización e informe y 19 quedaron interrumpidas según
los eventos persistidos.

## Qué se recupera

- metadatos de cada sesión;
- relación padre/hijo y profundidad;
- nombre canónico y alias;
- mensajes de progreso;
- resúmenes de razonamiento publicados;
- informes finales;
- nombres de tools utilizadas;
- llamadas y outputs exactos dentro del export privado;
- eventos de patches y finalización;
- hashes del segmento recuperado;
- ruta a la sesión original.

## Capas

### Versionada y sanitizada

- INDICE.md
- manifest.json

No contienen argumentos, outputs ni texto completo de mensajes.

### Local y privada

Ruta:

documentacion\agentes\privado

Contiene:

- hilo_raiz.jsonl.gz;
- una sesión task-specific comprimida por subagente;
- manifest_private.json;
- informes_finales.jsonl.

Está ignorada por Git porque puede contener rutas, comandos, outputs, contexto
personal o datos sensibles.

## Limitaciones

- El prompt exacto enviado al subagente puede estar cifrado en el JSONL. Se
  conserva el ciphertext original, pero este exportador no intenta romper el
  cifrado.
- No se recupera razonamiento interno oculto. Sí se recuperan los resúmenes de
  razonamiento que Codex decidió registrar.
- Algunas llamadas de spawn fueron reintentos o no produjeron una sesión. Por
  eso el número de llamadas, tarjetas de la GUI y sesiones descendientes puede
  diferir.
- Las sesiones interrumpidas se conservan aunque no tengan informe final.

## Regenerar

Desde la raíz:

python scripts\export_codex_subagents.py --force

No es una rutina de onboarding. `--force` reemplaza el export privado anterior
y vuelve a escribir metadatos dependientes del host, como timestamps y rutas
absolutas. Ejecútalo solo si la tarea exige una nueva captura, después de
preservar cualquier export que todavía sea necesario.

El manifiesto debe tratarse como evidencia histórica. Una conclusión de agente
no se vuelve decisión vigente hasta contrastarla con fuentes, código y pruebas.

## Cómo reutilizar sin inundar el contexto

1. Buscar por agent_path, alias, tools o estado en INDICE.md/manifest.json.
2. Abrir en manifest_private.json el registro de las sesiones pertinentes.
3. Leer primero final_answers y reasoning_summaries publicados.
4. Consultar el segmento .jsonl.gz solo si hace falta reconstruir comandos,
   outputs, patches o secuencia exacta.
5. Registrar session_id y segment_sha256 al trasladar un hallazgo al ledger.
6. Corroborar contra fuente primaria, código o prueba antes de decidir.

No se debe subir la carpeta privada ni asumir que varios agentes repitiendo el
mismo contexto constituyen evidencia independiente.
