# C03 — cobertura vigente

**66/742 cubiertos, 676 abiertos, 0 no aplican; 38 acreditaciones confirmadas en las últimas 24 h; 0/35 categorías cerradas.** Hay dos actualizaciones adicionales de casos cubiertos cuya fecha de primera acreditación no se distingue. Matriz C03: 3/11 cumplidas; C03 continúa EN_CURSO. Registro SHA256: 96d6ca83640517f8f972b4749bb2398d3588bc648e4a2b3dcd98d2fe4eb53626. Cifras consultables en SURVEY_COVERAGE_CURRENT.json.

El dueño reanudó el goal y aclaró el método: omitir suites automáticas, Fast y Full; mantener ejecuciones reales selladas, respuestas fieles y variantes para acreditar encuesta. El bloqueo anterior de alcance está resuelto. También autorizó cerrar aplicaciones para liberar RAM. No se cuentan pruebas omitidas como aprobadas.

Fuente vigente: c99a60f58281e74fe22792740b54ca9506e792e4 (904), publicada. Última ejecución906: una variante fallida, trece casos no ejecutados, cero confirmaciones y cero créditos. Reparación local910 y continuación909 en preparación. Los tramos siguientes son históricos y sus novedades más recientes están al final.

Últimos tres tramos:

- 881: 8/8 ejecutados, 6 válidos y 2 fallidos, sin crédito. Ambos literales fueron útiles pero faltaba una variante de cada conducta. Sus causas se escribieron al adjudicar. [Adjudicación](APP_LOOKUP881/ROOT_ADJUDICATION.json).
- 885: el primer arranque falló antes de cargar comandos por un perfil anidado no admitido. Se corrigieron sólo rutas externas y se preservó todo. La continuación ejecutó 9/9: 1 válido y 8 fallidos, sin crédito. Paint y hora fueron verificados, pero la respuesta correcta fue rechazada después; Calculadora dejó efecto incierto en H0183. [Adjudicación](APP_UNEXECUTED885_RETRY1/ROOT_ADJUDICATION.json).
- 892: 9/9 ejecutados, 7 válidos y 2 fallidos, **+2 créditos H0353/H0406**. Literales actuales y variantes pertinentes actuales/anteriores ligados explícitamente a sus candidatos. H0353 se escribió al adjudicar su literal; H0406 al resolver su par. Persisten dos límites fallidos: prohibición respondida como error y comparación conceptual sin respuesta. [Adjudicación](APP_LOOKUP892/ROOT_ADJUDICATION.json).

| Tanda | Pico VRAM MiB | Pico RAM MiB | Tiempo | Guarda |
|---|---:|---:|---:|---|
| 881 | 3497,56 | 2429,65 | 41,875 s | Sin violaciones |
| 885 continuación | 3497,56 | 2398,76 | 66,922 s | Sin violaciones |
| 892 | 3497,56 | 2410,98 | 82,047 s | Sin violaciones |

VRAM y RAM se informan por separado; techo de referencia 4096 MiB, parada GPU a3800 MiB y RAM libre mínima768 MiB. Las tres sesiones están recogidas y cerradas; no quedan corridas que esperar.

Siguiente categoría por masa: **web46 abiertos**, seguida de apps44. Agente893 prepara diagnóstico de dos búsquedas genéricas con mecanismo existente, H0098/H0380. 887 deja sólo un plan para tres Google: falta vincular la confirmación ordinaria con operación y argumentos exactos; no se construyó infraestructura ni se infló su alcance. 891 propone reparación C# del rechazo posterior de una respuesta correcta con hora y apertura; parche externo sin adoptar, sin build ni pruebas, para revisar cuando corresponda a la prioridad. 880 sigue sellado sin ejecutar.

No repetir: paneles completos854/TAIL,861,864,881,885,892; campañas de modelo/backend ya cerradas; Full843 histórico. Full/Fast/suites nuevos se omiten por orden posterior. H0675/OCR/nuevos providers y los9 Steam854 siguen aparcados con sus reanudaciones heredadas. No reintentar efectos inciertos H0183/Calculadora, H0151/Explorer ni Steam/Discord sin resolver su causa. Paint propio de885 se cerró normalmente y está fuera; Spotify preexistente se conservó. Audio861 ya restaurado31/sin silencio: no repetir su restauración. Los3 negativos y18 sin marca conservan sus marcas y límites.

Tabla de la taxonomía846, ordenada por requisitos abiertos:
| Categoría | Total | Cubiertos | Abiertos | No aplican |
|---|---:|---:|---:|---:|
| Navegación y búsqueda web | 46 | 0 | 46 | 0 |
| Abrir aplicaciones | 54 | 10 | 44 | 0 |
| Música | 39 | 0 | 39 | 0 |
| Estado de hardware y sistema | 40 | 2 | 38 | 0 |
| Alarmas, recordatorios, tareas y agenda | 38 | 0 | 38 | 0 |
| Conocimiento, razonamiento y creatividad verbal | 37 | 3 | 34 | 0 |
| Entrada incompleta, ruido y control de diálogo | 34 | 0 | 34 | 0 |
| Archivos y carpetas | 32 | 0 | 32 | 0 |
| Mensajería | 31 | 0 | 31 | 0 |
| Instalar y desinstalar software | 31 | 0 | 31 | 0 |
| Audio y volumen | 51 | 21 | 30 | 0 |
| Vídeo y series | 26 | 0 | 26 | 0 |
| Conversación social y ayuda general | 31 | 9 | 22 | 0 |
| Interacción dentro de aplicaciones | 22 | 0 | 22 | 0 |
| Hora y fecha | 23 | 3 | 20 | 0 |
| Red y Bluetooth | 21 | 1 | 20 | 0 |
| Cerrar aplicaciones y ventanas | 20 | 0 | 20 | 0 |
| Pantalla, captura e interpretación visual | 19 | 0 | 19 | 0 |
| Brillo y pantalla | 17 | 0 | 17 | 0 |
| Información web actual | 17 | 0 | 17 | 0 |
| Estado de ventanas y aplicaciones | 14 | 1 | 13 | 0 |
| Organizar ventanas y pestañas | 13 | 0 | 13 | 0 |
| Identidad y capacidades del asistente | 19 | 7 | 12 | 0 |
| Notas | 12 | 0 | 12 | 0 |
| Memoria personal | 10 | 0 | 10 | 0 |
| Correo | 6 | 0 | 6 | 0 |
| Bibliotecas y fichas de juegos | 6 | 0 | 6 | 0 |
| Contactos | 5 | 0 | 5 | 0 |
| Desarrollo y ejecución de comandos | 5 | 0 | 5 | 0 |
| Restricciones negativas de apertura | 4 | 1 | 3 | 0 |
| Portapapeles | 3 | 0 | 3 | 0 |
| Energía del sistema | 3 | 0 | 3 | 0 |
| Crear documentos y editar imágenes | 2 | 0 | 2 | 0 |
| Leer y resumir páginas web | 2 | 0 | 2 | 0 |
| Procesos | 9 | 8 | 1 | 0 |

[Historia preservada hasta Audio861](CHECKPOINT_HISTORICO_2026-09-11_HASTA_AUDIO861.md). Los tramos posteriores conservan recibos propios y versiones anteriores de este checkpoint en Git.


893 terminado y leído37d8c6: raw web.search correcto en H0098/H0380 se retira por domain_grounding; exige una mención pública adicional aunque la orden ya es una búsqueda directa. Son lecturas existentes, sin confirmación de navegador. InformeSHA898422b45b39c1ecf9389c344dd27bb5570d271d0e098d1d3ea38c832d181746. Agente apps_intent852 prepara894 fuera de canónico, en worktree codex/c03-web-search894, sólo effect_intent.py y __main__.py si imprescindible. No pruebas/build/GPU/HTTP; raíz revisaráparche y sellarácontinuación de2literales convariantes, sin repetir864. Fuente canónica todavía d6cf9d2a.66/742,676open,0NA;38altas24h,0/35categorías.

894 integrado tras revisión manual: la búsqueda pública directa conserva web.search sin exigir la palabra internet; extracción reutiliza verbos existentes y conserva buscá. Fuente pendiente de ejecución895, sin suites, sin verdes atribuidos. Panel895 sellado antes de ejecutar:4 variantes originales, H0098/H0380 intactos y5 límites;11casos/22wire, SHA0af2e16c9384fcf07001f2d155c312a552cbb132fc9b5b5d666163b4de8152d9. 66/742 cubiertos,676 abiertos,0NA;38altas confirmadas24h,0/35categorías. Siguiente inmediato: runner895, manifiesto nuevo del HEAD real y producto; no repetir864. Agente896 clasifica siguiente grupo web por fallos ya observados.

## 895 — búsqueda ejecutada; relevancia todavía abierta

Fuente894 publicada fb04a7014a368dc37afb05a904a671ba7e0e7499. Panel895 sellado11casos/22wire antes de ejecutar; revisión raíz751456, manifiesto6e4fb0a75e7c45ff2e23b6c5dbf4a15541fce66b73e20cc246211f9df449a492 y preparacióna1812b1e557a81cad609b759d63cfd9fa05a65e5ce3fb4f7ae4cebd9fe21c3ee. RunnerSHAfbdaf29bb227c144f3dc6530704814a43f6c411b8ea1d9fa643f3905d84e3d63, perfil hijodirecto. Session60692 terminal9a09fa exit0:11/11,3pass8fail,0créditos;94,422s,VRAM3497,56MiB/RAM2454,39MiB, sinviolaciones y pinsintactos. No suites/Fast/Full.

H0380 ahora busca Transformers y da respuesta útil fiel al resultado; sigueopen porque0/4variantes pasaron. H0098 conserva recetas de pizza pero los resultados sólo hablan de recetas generales; falla relevancia aunque Core marcóverified. Dune novels devuelvepelículas; tampoco cuenta. Una variante pide aclaración innecesaria y otra acaba sinrespuesta tras fallo de búsqueda. Límites: cita y condiciónsinseñalválidas; negación, falta deconsulta yscopeprivado sinrespuestaútil. Causas individuales y registro escritas748cc5; [adjudicación](WEB_SEARCH895/ROOT_ADJUDICATION.json). No repetirpanelentero.66/742cubiertos,676abiertos,0NA;38altasconfirmadas24h y2fechasindistinguibles,0/35categorías;matriz3/11.

Siguiente inmediato: recoger898 del proveedor existente sobre consulta/relevancia (sinHTTPnuevo, sinrelajarcriterio) y PLAN897 de11web aúnnoejecutados864.896 ya terminó:5búsquedasOpera/GX retiradasendominio; conservarconsulta, identidadexacta yconfirmación antesdetanda, no prometercrédito porañadirunapalabra. Evidencia896SHA c2d98af2bd305ea702343aab0acff20a62f59e3ae042e5b26ea4c8caa8b284d0. H0675/OCR/proveedoresnuevos permanecenaparcados. No corridasGPU vivas ni permisos pendientes.

900: filtro existente de relevancia sustituye cinco líneas de umbral parcial por queryTokens.All(observed.Contains). Revisión raíz898+2ca8ce; no nombres de casos/temas ni provider nuevo. Compilación de producto y publish terminaron0, shutdown0, sesión28145 recogida44f6cb; sin suites/Fast/Full. Corepublicado sincronizado con App antesdesello. Próxima tanda899 de3literales/3variantesrepetidas/5límites; éxito aún no demostrado.66/742,676open,0NA;38confirmadas24h,0/35categorías.

## 900 terminado — rechaza resultados parciales, aún sin crédito

Candidato2a69be0d3e0c5b0264a4ada01b33225d6e94400b, proveedorSHA448887961f8af18ce0ce7689336ab1088552d69eeaca98fe6524bb80eb942822. Compilación/publish real0 yshutdown0;584fuentes/18binarios(9cambiados)/5runtime. Manifiesto1e586240246ad2933f95c655b69e7217c56d8024e5408519e41f8b3e7a31c53f; preparación950796c71b2ed4a3d240cb5365a89def2e0af91ec0892231fe5cb823475e9526; runner59ddc66013fcfce53e766126e46de1d6d7f2c600af82bbdb35bf2b9a748bae45. Session66897 terminald2a602:11/11,3pass8fail,0créditos,89,094s,VRAM3497,56MiB/RAM2470,53MiB,sinviolaciones,pinsintactos. Suites/Fast/Full omitidos; no atribuir verde de pruebas al build.

895→900: ya no admite recetas genéricas para pizza ni películas para novelas. Los tres pares siguen fallando; H0380 sigue útil sin pares y H0708/H0098 sinresultadosrelevantes. Cinco límites sinoperaciones: negación y orientaciónlocalválidas; repeticióncitada noresuelta, explicacióngramaticalcontradictoria ycondición declaradafueradecapacidad fallan. Raíz c33d5c escribiólas3causasopen aladjudicar. RegistroSHA96d6ca83640517f8f972b4749bb2398d3588bc648e4a2b3dcd98d2fe4eb53626.66/742cubiertos,676abiertos,0NA;38altasconfirmadas24h+2fechasindistinguibles,0/35categorías;matriz3/11.

903REPORT leído76c3d7 SHAfb253b008870e4ddf6c8f079eeabc329df45f542a39df67db8f4c16a70198831: H0708 envía exactamente el clima en internet; extracciónretira en la web pero noen internet. El filtroexigeclima+internet; noRSScrudoquedemuestre que quitarámbitos baste. Reparaciónpendiente debeconservarcitas ytemas sobreInternet, no eliminarpalabraglobalmente.

901PLAN leído76c3d7 SHAd45ee2c6f99fd36559ced639963d699d6c4c8081da7663e7bdf70029fb23a63b:5destinos H0267/H0389/H0397/H0490/H0622 sintransporteobservaciónconfirmaciónactual. Decisiónraíz: una guardia acotada dentrodelconductor existente noañadeprovider/framework/harnesspersistente; preparar904con3archivosdueños aislados yconfirmaciónnormal, alcance5sin inflarloa10. No ejecutarconfirmacionesciegas mientrasfaltacambio. No es bloqueo delgoal. Enparalelo902prepara material880intacto+runner:correcciónpositivaH0691 y2variantes/5límites, sinrepetir854. Fuente raíz estable900; ningúnproductoGPU vivo.

## 902 terminado — rectificación positiva

Panel880 y criterios intactos; nuevo sello902: 8fe01e99d2486a74336828ae531c89f69ef961f0b5fca5782f5c0bcbbb69a87e. Runner44266782430502bfdf3de44b43f7b68cbae076fb2d7b1bc40c2e03a3966a527e. HEAD866672927615379f57c5259daeccf974df40d156, fuente900 sin cambios. Manifiesto4c05f90b2b034b26112fa8bc40375754626aec8ceb256c7c377e2e6e70b0e3ba; preparación55c978f113a22549550aeff6af17f4734c0dcde0b7fdd529d308d4fb39f59360.

8/8 ejecutados, 2 válidos, 6 fallidos, 0 créditos. Session20854 terminó con exit0, recogidae52586. Duración60,125s; pico VRAM3497,56MiB y RAM2454,90MiB; sin violaciones, pins intactos. Sin suites ni nuevo build. Paint se abrió y verificó en la variante ES (c4a197e5-ceb3-436a-8b7b-f18bfa89d017); la variante EN quedó sin respuesta y H0691 pidió reconfirmar Firefox sin abrirlo. La cita se explicó bien; los otros cuatro límites no produjeron operaciones pero sus respuestas fueron inútiles o atribuyeron intentos no observados. Raíz6ee075 adjudicó y escribió H0691 open.

Paint propio39048/HWND28313962/creación2026-09-11T17:26:29.8237390Z cerrado normalmente, gone:true. No repetir limpieza. No hay producto/GPU vivo.

Estado:66/742 cubiertos,676 abiertos,0NA;38 altas confirmadas24h y2 primeras fechas indistinguibles;0/35 categorías,matriz3/11. Registro96d6ca83640517f8f972b4749bb2398d3588bc648e4a2b3dcd98d2fe4eb53626. Este turno tuvo progreso:19 casos reales900+902,5 válidos14 fallidos,0 altas; fuente900 reduce falsos positivos y4 causas abiertas quedaron escritas.

Siguiente: recoger parche904 del conductor existente (process_counts812) y contenido905 (apps_intent852). Raíz revisa, integra y compila si procede, sella formato y ejecuta5 destinos con confirmación exacta. Alcance5 declarado: sin provider/framework/harness persistente nuevo y sin permiso pendiente.903 conserva el diagnóstico del ámbito del clima; su reparación debe preservar citas y temas sobre Internet. No repetir900/902 completos ni reabrir campaña de modelo/Full. Fuente actual2a69be0d; main preservado.

## 904 integrado y compilado — pendiente ejecución906

Tres archivos del conductor existente, +129/−23. Raíz revisó afd475/a101db/8c0647/769d2e/cd7945; integración93b3bd con hashes coincidentes. Parche6561f87dbcca3057201d5cd13f27035c8c68e0d6d19fa502ee314bd7492c9476. La nueva orden turn.confirm-if-matches sólo compara el pendiente tipado; revalida el mismo desafío/Prepared y lo envía por confirmación ordinaria. Los argumentos esperados nunca completan la propuesta. Un desajuste detiene el lote, exit3; sólo phase=final puede acreditar el caso. Se preservan las dos fases y ninguna confirmación cuenta como variante.

Compilación/publish de producto0, shutdown0: sesión64748 recogida211c15. Core publicado sincronizado con App. Sin suites/Fast/Full; build no demuestra comportamiento del panel. Alcance5 requisitos explícitos, sin provider/framework/harness persistente nuevo. Fuente publicada en el commit de este tramo; detalle y pins WEB_CONFIRMATION904/SOURCE.json. Worktree904 aún preservado junto al parche; limpiar sólo después de confirmar fuentes adoptadas.

Próximo inmediato: apps_intent852 termina panel906 desde borrador905 revision2,14casos/28wire (4variantes,5literales,5límites); process_counts812 adapta runner906 para fases separadas, máximo23 admisiones/terminales y14 finales de caso. Leer ambos entregables, revisar/sellar candidato actual con584fuentes/18binarios/5runtime y build904 real, preparar y ejecutar. Un rechazo temprano deja la cola no ejecutada, no fallida; no reintentar ni confirmar destinos sustitutos.

El límite original905 pedía exportar notas locales: raíz rechazó ese borrador ANTES del sello/ejecución y pidió una pregunta conceptual sin leer/exportar. Original preservado; sólo revision2/906 puede usarse. Resto de literales/criterios padre864 intactos. Nada de906 se ha ejecutado. Registro96d6ca83640517f8f972b4749bb2398d3588bc648e4a2b3dcd98d2fe4eb53626;66/742,676open,0NA;38altas confirmadas24h,0/35categorías,C03matriz3/11. Goal activo, sin permiso pendiente ni GPU viva.

## 906 — parada exacta conservada, trece casos no ejecutados

Fuente904 bajo HEAD1c7973ed25d2bcde732762f4e0fbd96031c9f5fd; panel d4ec688293e559ac55d8b2045f1848705c3a07d4f19167acc234a616edde2981. Manifiesto ef4f02cda4561975f93d5b1e6957014b417613d84c301dc4cfa2614fac2a2824; preparación03293f3fed6755eb3762d91dfb271ccab1cb8bcf8d890b70baae38c6d8b9d6e4. Runner6249bcf72fd10a902c9256394e9af92e79c243c4154992bed6dcaa06af3db96d, revisión e28350/2c7dc6, preparación a0b19b y corrida c1ce62/session58941 recogida c23966.

1/14 ejecutado, 0 válidos, 1 fallido, 13 no ejecutados, 0 créditos. Primera variante «Llevame a https://www.rfc-editor.org/.» devolvió «No puedo llevarlo a esa página. Eso está fuera de mis funciones.». Retrieval lexical no incluyó browser.navigate; request8 terminó conversación sin operación. La guarda904 rechazó el pendiente ausente; no envió confirmar. Hostexit3, una admisión real, dos fases reportables; cola no ejecutada demostrada. 23,094s, VRAM3497,56MiB y RAM1598,58MiB, sin violaciones y pins intactos. No se ejecutaron literales: registro96d6ca83640517f8f972b4749bb2398d3588bc648e4a2b3dcd98d2fe4eb53626 intacto. Raíz adjudicó ROOT_ADJUDICATION.json.

66/742 cubiertos,676 abiertos,0NA;38 altas confirmadas24h (dos fechas iniciales adicionales indistinguibles);0/35 categorías,matriz3/11. No suites/Fast/Full. No repetir la variante fallida sin reparación justificada; continuar sólo los13 no ejecutados.908 diagnostica primera pérdida;907 prepara siguientes aperturas. Goal activo, sin bloqueo ni permiso pendiente.

## 910 — lector de navegación corregido; continuación909 sellada

Revisión de908 (SHA0ed025796d5c7d287b566d343b68417d4a5a1b7b9ac1086b23958134d59a5ea8) y fuente afc197/d1ce7f: llevame ya era petición directa pero faltaba en los patrones locales de navegación. Una expresión local sustituye siete repeticiones y añade ese verbo; no cambia _OPEN global ni retrieval. Parchebc4899590046031f6f2094027eff12ae98d6fcc299c91150119861c2993b2279, fuente3c472d768dd3eee64112ba0697d6287fef72f8843524339ceb546a33404a6ff4, integrado1e2057. Sin suites; comportamiento pendiente del producto.

909 conserva bytes de panel/wire906 y los14 objetos: sólo se reejecuta la variante fallida con reparación justificada; otros13 nunca se ejecutaron. Sello3617e9a7ceddcbf8f0606fced8a24a5f1c07cc45781b3806540dcd6ffc39b48b, runnerd2089a513c34c5352e770160cd2b0f9b53e2e0ab82a29ddd51d54d5bbbe4bcb8; revisióncd73e2: sólo10 líneas de identidad/rutas/schema, guardas intactas. Reutilizar build904 real de C# sin atribuir build nuevo ni pruebas verdes; sólo cambia Python. Raíz ligará584fuentes/18binarios/5runtime y ejecutará909.

907 inventaría44apps abiertos:40positivos+4límites; cero literales positivos nuevos elegibles bajo exclusiones. Esto no cierra ni aparca la categoría: requiere reparar fallos observados antes de repetir los afectados. Los10 Calculadora requieren resolver verificación/efecto incierto primero; no pedir permiso nuevo para una reparación dentro del goal. 66/742 cubiertos,676abiertos,0NA;38altas confirmadas24h,0/35categorías,C03matriz3/11.
