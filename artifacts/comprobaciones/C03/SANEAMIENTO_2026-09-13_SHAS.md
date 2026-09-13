# Saneamiento del historial 2026-09-13 — equivalencia de commits

El dueño retiró del historial publicado los corpus privados (`docs/PUBLICACION_Y_DATOS_PRIVADOS.md`, commit 77603a77) y reescribió la rama `codex/kiro-goal-c03`. Los artefactos de las tandas C03 citan los SHA anteriores al saneamiento (sellos, `SOURCE.json`, `APP_SOURCE.json`, `ROOT_ADJUDICATION.json`, HANDOFF). El contenido de cada commit es el mismo; sólo cambió el identificador. Equivalencia (SHA citado → SHA en la rama saneada):

| Citado | Saneado | Commit |
|---|---|---|
| 5f99956f | b47e3514 | C03: WEB1257 adjudicated, +3 covered (341/742) |
| 6c562d12 | bf6c3a30 | C03: named public sites open by navigation; andá as a request head (WEB1257 repair) |
| d610b62f | d0e41881 | C03: MEMORY1255 adjudicated, +2 covered (338/742) |
| 88f5afdf | 0f1062fb | C03: the remembered-value check keeps content words, not the whole sentence (MEMORY1255 repair) |
| b9224114 | e9f5524f | C03: MEMORY1253 adjudicated, +2 covered (336/742) |
| 772a1671 | 8905e0a5 | C03: memory completion composes against the request text; quoted remembered value; memory_disabled hint (MEMORY1253 repair) |
| 6fc6c331 | be8f3075 | C03: MEMORY1251 checkpoint and relay state |
| dd404b28 | 24304566 | C03: MEMORY1251 adjudicated on the reverted activation wording, 0 credits (334/742) |
| 53b1d90b | 5e51ea4a | C03: MEMORY1249 adjudicated, 0 credits (334/742); save composition fixed, activation wording regressed and reverted |
| e3580505 | 57699c92 | C03: keep the memory activation message's prior wording; the new cause fact made its composition fail (MEMORY1249) |
| cbc19a38 | 8317b26f | C03: a completed private-memory save says what it remembered, as local memory, in the request's language (MEMORY1249 repair) |
| 050ee686 | 076d89bd | C03: MEMORY1247 adjudicated, 0 credits (334/742); two-phase memory saves verified, final composition defective (cause measured) |
| d2a7a725 | 15f9c05d | C03: conductor command turn.memory-confirm answers the private memory channel's own confirmation (MEMORY1247) |
| 6eb57c2a | 5cc75651 | C03: MEMORY1245 adjudicated, +3 covered (334/742); personal statements credited, private-memory saves blocked by the App activation confirmation (cause measured), Memoria 3/10 |
| 385bfb56 | 4553f026 | C03: the private memory parser accepts «recordá/acordate que me llamo …», «quiero que me recuerdes como …» and «recordá … color favorito» (MEMORY1245 repair) |
| e2eb5847 | f7e2120b | C03: FILES1243 adjudicated, +4 covered (331/742); named-file deletions to the private trash and truthful absence credited, Archivos 19/32 |
| 4873c48b | 424caf12 | C03: the deletion reader owns the known-folder enum during argument grounding (FILES1243 repair) |
| cd6ec990 | 5f47b86a | C03: a literal request to delete a named file in a known folder is the recoverable known-file trash (FILES1241 repair) |
| c61490d2 | 6f7caaf9 | C03: AUDIO1239 adjudicated, +12 covered (327/742); relative volume requests ask the amount (owner rule), absolute level, pronoun mute and prohibitions credited, Audio 39/51 |
| c021ef45 | d5741240 | C03: volume requests accept «suví», «poné/ponelo», an absolute level after a direction verb, the pronoun mute and a lateness frame (AUDIO1239 repair) |
| 1d9fbfc9 | b5e3b086 | C03: APPS1237 adjudicated, +5 covered (315/742); File Explorer openings and truthful absent targets credited, Abrir apps 39/54 |
| 360ea216 | a647bc0e | C03: the shell's File Explorer entry is identified by its process, not by a title prefix (APPS1237 repair) |
| 7f51be21 | c75d3747 | C03: File Explorer launches verify by a new CabinetWClass window of the shell; openings of known software absent from the catalog become a presence read (APPS1233 repair) |
| cf5b890d | 8af573f8 | C03: APPS1231 adjudicated, +5 covered (310/742); Calculator openings credited (clitic, typo, courtesy, clock-time, «abre a»), Abrir apps 34/54 |
| 04645e82 | a3c9417d | C03: «abre a calculadora» is a Spanish opening, not Portuguese, when a known application follows the article (APPS1231 repair b) |
| ccf61b64 | 258c9aad | C03: application openings accept the voseo clitic, «avrí», trailing «dale/porfa/pls», a stated clock time and bilingual catalog aliases (APPS1231 repair) |
| 317d5d9e | 67f014eb | C03: ARRANGE1229 adjudicated, +3 covered (305/742); foreground-window maximize/minimize credited, Organizar ventanas 3/13 |
| a9cdb721 | 5b42b8a8 | C03: deictic window mutations bind the foreground window; English maximize/minimize/restore are direct requests (ARRANGE1229 repair) |
| 26ca262b | 4710bdac | C03: CLOSE1227 adjudicated, +4 covered (302/742); deictic closes and close prohibitions credited, Cerrar apps 11/20 |
| 657346eb | de9555b7 | C03: a close prohibition with a justification clause is acknowledged as a constraint (CLOSE1227 repair) |
| c2e8febb | d18b071d | C03: CLOSE1225 adjudicated, +3 covered (298/742); deictic closes of the foreground window credited |
| f4933c4a | f6972ec7 | C03: deictic closes of the foreground window («esta ventana», «cerrala», «close this window») (CLOSE1225 repair) |
| 7c64dfde | c1446d5d | C03: prohibitions with a justification clause and future-request announcements read as conversation (CLOSE1225 repair) |
| 074f8309 | f1daab4c | C03: require a complete window enumeration only for the candidate process (CLOSE1225 repair) |
| 2016a58c | 1b88687b | C03: CLOSE1223 adjudicated, +4 covered (295/742); first credited app closes (Notepad, Calculator, Chrome) through the reviewed turn |
| 50ad70f0 | b0ea9287 | C03: action and plan replies carry the request language (CLOSE1223 repair) |
| 85863175 | afa098c3 | C03: only candidate processes need a strong identity in the window inventory (CLOSE1223 repair) |
| 9a9b440f | d760ee6f | C03: CLOSE1221 adjudicated, +0 covered (291/742); hosted Calculator resolved, strong inventory aborted by a foreign elevated process |
| 53a55c58 | 306b172e | C03: strong identities for classic and frame-hosted apps, confirmation in the request language (CLOSE1221 repair) |
| ea5d092d | 0ac72857 | C03: CLOSE1219 adjudicated, +0 covered (291/742); first reviewed app closes complete (Notepad, Paint), Chrome/Calculator identities and confirmation language pending |
| c7dc80d5 | 8f2956e2 | C03: keep the page-scope and foreground fields the reviewed close shape reads (CLOSE1219 repair) |
| bc422bfc | 4829480a | C03: CLOSE1217 adjudicated (partial), +0 covered (291/742); capture refusal traced to the observation projection |
| 2aa9a177 | 5c59497e | C03: record the capture refusal through the shell trace sink (CLOSE1217 diagnostics, build fix) |
| bb92bb4b | 2846f50a | C03: name the guard that refuses a conductor confirmation capture (CLOSE1217 diagnostics) |
| c1f481c6 | 289c9f9d | C03: CLOSE1215 adjudicated (partial), +0 covered (291/742); named close reaches the app.close challenge, reviewed capture refuses |
| 73595548 | 604ed2f4 | C03: close requests authenticate catalog identities and colloquial heads (CLOSE1215 repair) |
| ad2dbbf8 | fbbd863f | C03: WINDOWS1213 adjudicated, +6 covered (291/742); window inventories answered on the real desktop |
| 117110ff | 2c0da209 | C03: name titled windows only, line-bound quantities, language veto on masked copy (WINDOWS1213 repair) |
| 447857c6 | 2ab7bb79 | C03: WINDOWS1211 adjudicated, +0 covered (285/742); five inventory literals compose, pairs blocked by two validation defects |
| 2f1ba9aa | 47034149 | C03: remaining-window scope and observed-name stutter (WINDOWS1211 repair) |
| 9f41bc0a | a0321b28 | C03: WINDOWS1209 adjudicated (partial), +0 covered (285/742); bounded projection composes, two prose checks still reject |
| 622ec0cb | 53ac9264 | C03: bounded window inventory projection (WINDOWS1209 repair) |
| 72f261cb | c9273f24 | C03: WINDOWS1207 adjudicated (partial), +5 covered (285/742); app presence answered, window inventory blocked by scale |
| 9c147e18 | 98c8626e | C03: window inventory and app-presence questions in their colloquial forms (WINDOWS1207 repair) |
| a9ab14ab | c8f24b7d | C03: FILES1205 adjudicated, +12 covered (280/742); files and folders created in known folders and verified on disk |
| d95b9f96 | cf14c023 | C03: files and folders can be created in known folders (FILES1205 repair, BUILD1205) |
| f5cb8f69 | 25fd87f8 | C03: NETWORK1203 adjudicated, +2 covered (268/742); every observed IP is named and the English answer is published |
| 6478ff47 | 70d08a60 | C03: provenance is not a fact and every observed IP is named (NETWORK1201 repairs) |
| 5bae30ed | 74654b4c | C03: NETWORK1201 adjudicated, +1 covered (266/742); the machine's own IP is read without confirmation |

Los commits WEB1257 (6c562d12, 5f99956f) se trasladaron por cherry-pick sobre la rama saneada (bf6c3a30, b47e3514); el instrumento C03-web1257-instrument-v1 quedó sellado sobre 6c562d12, cuyo árbol de `src` es idéntico a bf6c3a30. La copia local de los corpus privados sigue en `tests/data/` (ignorada por `.gitignore`) y en el respaldo privado fuera del remoto. Regla para el escritor raíz: `git fetch` antes de cada push; ante una rama reescrita, cherry-pick sólo los commits de trabajo, nunca merge ni rebase del historial anterior.
