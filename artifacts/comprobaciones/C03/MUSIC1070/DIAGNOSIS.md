# MUSIC1070 — primera pérdida de composición

Base31e7d33a62292ba496a2839acf7b5bd09ab96031; sólo propuesta externa llm.py. Evidencia exacta: C:/Users/usuario/AppData/Local/BAXY/C03-music1069-proposal/private/run-01. IDENTITY.json conserva hashes de compose-audit, shell-trace, turn-audit y REVIEW1064 heredado.

Shell-trace t1 seq35–36 muestra media.control antes de compose seq37. El primer borrador recibe operation=media.control, polarity=success, verified=true, succeeded=true; observed contiene authority=windows_smtc, playbackStatus=playing y título/artista reales. No se pierde el resultado en proyección.

compose-audit t1 first (draft SHA944fa78712e1cbb3c6e3c2570b10563fa50cf70fc7c078d6426646b6f18a9345) dice «Reanudé la música. Está reproduciéndose \"Sendero azul\" de Original BAXY preparation composition.» Conserva identidad y describe el estado verificado, pero recibe missing_state/published=false. Es el primer rechazo demostrado, no una respuesta vacía del modelo.

compose_visible_defect, llm.py:5146–5167, reconoce el gerundio reproduciendo pero no su forma reflexiva reproduciéndose; el límite de palabra impide reconocerla parcialmente. Por ello names_observed_state queda falso. Los borradores retry/third posteriores omiten el artista y reciben missing_name correctamente. La recuperación repite esos resultados hasta no_response;recovery:no_response;retry_exhausted. No existe raw-replies.jsonl en este segmento: las salidas nativas están capturadas dentro de compose-audit.

DIFF.patch cambia una sola alternativa morfológica del detector: reproduci[eé]ndo(?:se)?. Mantiene reproduciendo y admite la flexión reflexiva acentuada o sin tilde. No añade nombres de pistas, frases visibles ni un nuevo lector. Las afirmaciones siguen contrastándose con el estado observado; una afirmación de reproducción con paused/stopped continúa siendo contradictoria según la guarda existente.

Título/artista obligatorios, separación de metadatos antes de analizar predicados, negación y exigencia de media.control verificado/succeeded/authority/sourceApp siguen intactos. No cambian las alternativas paused/stopped ni la intención/proveedor. La función también sirve a media.status; sólo se amplía esta morfología, conservando sus controles.

REVIEW1064.md:11–13 documentó el hint de apertura inapropiado para recuperación missing_state de media.control. Se conserva como evidencia secundaria: no se modifica porque la reparación causal mínima se sitúa en el primer falso rechazo, tal como decidió raíz.

Revisión manual del único hunk, sin pruebas, importaciones, AST, build, Core, GPU, efectos o cambios canónicos. La respuesta observada satisface el predicado corregido por lectura estática; no se afirma un pass funcional posterior ni nuevos créditos. Raíz valida producto y conserva los recibos de pausa ya pasados.
