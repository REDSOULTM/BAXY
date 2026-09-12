# MUSIC1084 — dirección relativa y dominio ambiguo

Caso5 de1082, music1037-dev-05: «Pasá al tema que viene.». Fuente2741e7d502a65011bbefe87cd3e2881093a5eb19; sólo lectura. No parche: convertir tema en pista por defecto sobreautorizaría peticiones conversacionales. Este material exige avanzar al vecino de la cola observada, no sólo formular una aclaración.

## Primera pérdida observada

turn-audit.jsonl request8: retrieval lexical,28 candidatos sin media.control. raw_attempt ya propone conversation/knowledge, effect_count zero y ninguna operación. validated_raw, explicit_contract, information_question, domain_grounding, compound_conservation, action_relevance y action_grounding mantienen ese estado; no se ve una operación multimedia correcta que un veto posterior retirara.

raw-replies.jsonl registra pre_veto attempt1 con history_users0: «¡Claro! ¿Qué tal si hablamos de algo más interesante, como tu día o lo que estás haciendo ahora? 😎». case-observations publica exactamente ese final; shell-trace t1 seq29 enlaza turn.decide.id.8, seq33 decision.ready conversation y seq36/37 response.final. No es error de extracción ni composición bloqueada. La única Corecall trazada es memory.status de arranque; no se lee su resultado cifrado. Raíz observó Aurora playing antes/después, pero eso no demuestra que la mente recibiera contexto multimedia ni autoriza interpretar todo tema como música.

## Discrepancia estática concreta

- effect_intent.py:7980–8030 _is_direct_request contiene pasa en la autoridad general: el problema no es simplemente faltar el imperativo voseante.
- _media_navigation_request:6068–6080, reutilizado en autoridad y _review_media_and_email_effects:11811, sólo acepta forma nominal siguiente/anterior/next/previous + podcast/episodio/canción/song/pista/track, con prefacio opcional pon/pone/play/reproduce. Faltan construcción de tránsito pasa al, dirección relativa que viene y sustantivo polisémico tema.
- _review_media_and_email_effects:11925–11960 tampoco rescata la frase: su rama de control exige las cabezas/dominio existentes y no interpreta esa dirección relativa. La ausencia de recuperación explícita concuerda con audit; no afirmamos que esos predicados expliquen matemáticamente todo el ranking lexical.
- __main__.py:4310–4350 _explicit_media_control_arguments tampoco liga next desde que viene. Añadir sólo tema a una lista dejaría dos fronteras sin reparar y ampliaría autoridad sin desambiguar.
- resolve_explicit_effects:13451–13460 recibe texto, catálogo y previous_user_text opcional; no recibe estadoSMTC como argumento. turns.jsonl tiene session.new antes de la petición y rawreply acredita0 usuarios anteriores. No hay antecedente conversacional musical observado que pueda reutilizarse en este caso. No asumir que una pista sonando hace musical cualquier conversación.

## Corrección común defendible y su límite

La costura reutilizable es el lector de dirección existente: si se amplía, debe producir una dirección única para tránsito y posición relativa con objeto musical inequívoco, compartida con el binder; se retira el reconocimiento sustituido, sin otra capa o lista del panel. Negación, cita, relato futuro, coordinación y direcciones contradictorias conservan sus guardas. Ese cambio cubre gramática de transporte, pero no resuelve por sí solo tema ambiguo.

Para tema sin calificativo se necesita contexto musical acreditado de la misma petición/antecedente real o una aclaración del dominio antes del efecto. Un estadoSMTC existente prueba que hay música disponible, no que ése es el tema al que se refiere el usuario. No se inventa antecedente, no se inyecta el criterio del panel en la mente y no se sustituye el literal por canción. El mecanismo de aclaración existente puede ser el siguiente paso de producto, pero con el contrato actual de esta variante no sería un pase de avance ni acreditaría los literales next.

No hay parche pequeño demostrado que garantice el efecto exigido en este turno aislado preservando esa ambigüedad; por ello se entrega diagnóstico, no una whitelist de «tema que viene». La ejecución inglesa que raíz realiza debe evaluarse separadamente: si contiene track explícito y falla, puede aislar gramática sin resolver primero la polisemia española. No se reejecutó ningún caso.

## Evidencia y propietarios SHA256
- C:\Users\usuario\AppData\Local\BAXY\C03-music1082-proposal\panel.json — cfaf35b143e3438568417fe412b8465d19cca82ceb59a4494f456a2f236d53f0
- C:\Users\usuario\AppData\Local\BAXY\C03-music1082-proposal\private\run-05\turns.jsonl — f8f1fbf38d6c07cdf7d04529d0138e0c056d0de5aee775f7120cff56394b3331
- C:\Users\usuario\AppData\Local\BAXY\C03-music1082-proposal\private\run-05\turn-audit.jsonl — e335e0e69f9dccf34839d5f90d9cd497131a38c2064a259c9b9c293ccfbfea7d
- C:\Users\usuario\AppData\Local\BAXY\C03-music1082-proposal\private\run-05\raw-replies.jsonl — a3ad65d231e96aed4c9b578d045ae08d1e486c4030cb9b2e8d12c424fadf13ec
- C:\Users\usuario\AppData\Local\BAXY\C03-music1082-proposal\private\run-05\compose-audit.jsonl — 135dbc78d30846ae35b3325b9e3eff17227080d90f46e100f1657d8956c5a420
- C:\Users\usuario\AppData\Local\BAXY\C03-music1082-proposal\private\run-05\shell-trace.jsonl — b14e7d545476ca485cb4ad1bc6d90cd6e1c81a1e4e11cdb8c0461cf5495b32dc
- C:\Users\usuario\AppData\Local\BAXY\C03-music1082-proposal\private\run-05\case-observations.json — ac1524bfe2eae28c5359ea963ca64e4f9e44a5558154fd4eb99af9bc40aeb0c1
- D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO\src\baxy_mind\effect_intent.py — db79ad14666531dc11ab471eb4a9292a6d3378ceb5e224832d5b6ca39f957001
- D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO\src\baxy_mind\__main__.py — 7be3cd8e8bce8a45eec8e2031e3189b422c53b9c46df0b62754a289b7760888f
