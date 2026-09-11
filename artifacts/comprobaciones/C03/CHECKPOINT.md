# C03 — cobertura vigente

**66/742 cubiertos, 676 abiertos, 0 no aplican; 38 acreditaciones confirmadas en las últimas 24 h; 0/35 categorías cerradas.** Hay dos actualizaciones adicionales de casos cubiertos cuya fecha de primera acreditación no se distingue. Matriz C03: 3/11 cumplidas; C03 continúa EN_CURSO. Registro SHA256: 45c523628df911994fbe8be17e367c429ce1f544ddb2341db8965ab57e3d7c4e. Cifras consultables en SURVEY_COVERAGE_CURRENT.json.

El dueño reanudó el goal y aclaró el método: omitir suites automáticas, Fast y Full; mantener ejecuciones reales selladas, respuestas fieles y variantes para acreditar encuesta. El bloqueo anterior de alcance está resuelto. También autorizó cerrar aplicaciones para liberar RAM. No se cuentan pruebas omitidas como aprobadas.

Fuente vigente publicada: d6cf9d2a52f4f1e49836365d6ced125e68f662fe. 888 amplía la consulta local de apps reutilizando lector y selector; 889 conserva premisas explícitas sobre objetos ficticios en el verificador existente. Revisión manual y ejecución892 posterior, sin suites. No cambia modelo, runtime, catálogo ni provider.

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
