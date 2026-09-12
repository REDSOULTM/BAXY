# MUSIC1063 — dos cortes distintos en el control SMTC

Fuente base cd1b08ab8c1be8d40c80498b02a5e7aabf9f6990. Evidencia privada exacta MUSIC1061 run-01 H0110 y run-00 H0046; pins en IDENTITY.json. No se altera CLOSE1060 ni el material sellado MUSIC1061. La raíz cerró 1061 parcial: dos fallos, veintiún casos sin ejecutar, cero créditos.

## H0110: la operación correcta no alcanza argumentos

Literal: «reanudá la música». La raíz verificó previamente su sesión propia Aurora de cobre pausada, source Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic. Esa observación es de preparación de raíz, no una prueba ejecutada por este diagnóstico.

Turn audit request8: decision_path=model; media.control ausente entre 28 candidatos; raw propone media.seek.relative. El primer veto visible es domain_grounding, que lo convierte a unsupported. Ese veto es correcto: la persona no pidió desplazamiento temporal. Shell confirma sólo memory.status de arranque, ninguna operación multimedia. raw_reply unsupported y composición final «No puedo reanudar la música.» derivan del out_of_catalog; no prueban ausencia ni fallo SMTC.

Primera pérdida en fuente: _review_media_and_email_effects exige la palabra paused/pausado/stopped para resume_existing_media incluso con reanuda/reanudar/resume. Al no estar ese adjetivo, excluye media.control. La propuesta cambia únicamente esa condición: el verbo de reanudación ya expresa continuidad; play/reproduce mantiene el requisito de un estado textual pausado/detenido para no convertirse automáticamente en transporte de la sesión actual. Se conservan el dominio multimedia, cabeza de petición y todos los controles de autoridad. _explicit_media_control_arguments ya transforma reanuda/resume a action=play; no se modifica ni se fija sourceApp porque el literal no nombra una aplicación.

Herencia consultada: PLAN/REPORT MUSIC1061, material original1037 y registro de mantenibilidad sobre propagación sourceApp=spotify desde media.play.exact; esa propagación permanece. git log -S resume_existing_media localizó base7662b80c y408f9a5c; los hunks408f9a5c afectan separación de reproducción YouTube, no este requisito de reanudación. Se conserva esa separación. No se reabre ni se presenta como positiva la campaña rechazada por aquel commit.

Los pares originales1037 son «Seguí con la reproducción que quedó en pausa.» y «Resume the track from where it stopped.». No se reescriben. Sus formas léxicas/objeto no están cubiertas automáticamente por esta modificación y aún no se midieron aquí; no afirmar que los pares pasarán ni añadir aliases a partir del material para fabricar el crédito.

## H0046: efecto real, recibo con proveedor falso y veto de composición aparte

La raíz observó pausa SMTC/UI sobre Aurora de cobre; journal run-00 contiene invocación315877fd-cc4c-431d-b031-d6b6ac0160c0, media.control, completed/verified=true, playbackStatus=paused. Su resultado y su message atribuyen provider=spotify, aunque la fuente observada es Microsoft.ZuneMusic. El error se origina en MediaResult de WindowsMediaSessionAdapter, llamado tanto por control genérico como por PlayExactCurrentAsync, que escribía spotify incondicionalmente.

El parche exige sourceAppUserModelId observado del objeto session para ambos callers. El control genérico deja de publicar provider; mantiene title, artist, playbackStatus y authority=windows_smtc, coherente con la forma de media.status y sin inventar un nombre comercial. PlayExactCurrentAsync conserva provider=spotify explícitamente: esa rama ya selecciona una sesión Spotify. Su postread/dispatch y la vía Web API no cambian.

Composición es un problema separado: run-00 contiene los tres intentos rechazados por missing_name, incluido «La música está pausada en Spotify.». Esta propuesta elimina el hecho falso del recibo, pero no pretende solucionar missing_name. La raíz conserva ownership de llm.py/App policy. No se cambia un recibo para satisfacer el compositor ni se acredita el literal por haber ejecutado sólo el efecto.
