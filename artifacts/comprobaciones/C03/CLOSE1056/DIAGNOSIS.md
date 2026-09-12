# CLOSE1056 — cierre por nombre autenticado, propuesta externa

Base52a49b005718822a1caaa7019daa4df223e11cea. Primer fallo común está en el reconocimiento de intención de cierre por nombre; los vetos posteriores impiden ejecutar operaciones equivocadas y no deben retirarse. Propuesta única owner effect_intent.py, no proveedor nuevo ni catálogo de frases/aplicaciones. No se integra ni ejecuta durante WEB1054.

## Herencia aplicada

REGISTRO_DE_MANTENIBILIDAD.md4814–4850 y4894–4908: D3 demostró que listas negras de objetos físicos no terminan; D5 exige evidencia positiva del dominio digital, tras «Cuelga el cuadro en la pared del pasillo»→app.close. Mantener esa frontera. R272/R274 líneas9164–9244: tres app.close eran falsos positivos deun corte que pedía aclaración; no considerar match determinista suficiente para ejecutar. No reabrir corpus rechazados ni inventar nuevas reglas porliteral.

Instrumentación1052 ya amplió revisión exacta del prefijo window.resolve/window.active→app.close; aquí ninguna deesas rutas llegó a efecto ni challenge útil porque falló antes la intención. No se arregla cambiando fixture/foco ni confirmation.

## Evidencia observada

Índice0/H0095 «cierra el bloc de notas», run-00,request8: retrieval lexical,28candidatas; app.close presente enposición14 base0, pero rawdecisión note.list/action/one. explicit_contract e information_question lo conservan; domain_grounding lo veta aunsupported, ceroefectos finales. Rawvisible «No puedo cerrar el bloc de notas tal como fue pedido.»; composeerror payloadoutside what I do inventa «porque no tengo permiso para hacer eso». Journal segmentsnapshot sólo memory.status. No cierre ni denegación real de permisos.

Índice10/close1052-dev-01 «Cerrá Paint, por favor.», run-10,request8: retrieval lexical28candidatas sinapp.close; rawwindow.active/action/one, dominio lo veta aunsupported, ceroefectos. Rawvisible «No puedo cerrar Paint tal como fue pedido.»; composeerror inventa «no tengo permiso ... en este equipo». Journal contiene sólo memory.status. No se afirma regresión delproducto sinbaseline comparable. EVIDENCE conserva las dos trazas exactas, no elcatálogo global deapps.

## Primera transformación errónea

_review_application_and_window_effects108xx reconoce cierre mediante has_named_window_target (título deventana explícito), lista _KNOWN_APPLICATION, sustantivoapp/program o ventanaactiva/contextual. La alternativa de nombres tiene artículo opcional sólo la/the yterminación simple. H0095 usael; Paint no pertenece a la lista fija ysu cortesía concoma tampoco cabe. Ambos quedan fuera deefectoexplícito ycaen a recuperación/modelo.

Además el gate app.close/window.close1113 reutiliza _authenticated_application_target. Su dueño _indexed_authenticated_application_target3480 reconoce _OPEN oinstalled_query, no una cláusula de cierre. Por eso no basta reconocer cierre nuevo si luego pierde el dominio. El requisito previo window.resolve también exige ventana/proceso/aplicación literal, que falta en «Cerrá Paint».

No sonfallos de autorización real. No retirar domain_grounding de note.list/window.active: correctamente evita efectos ajenos a lo pedido. La explicación falsa de permisos es otro defecto de presentación desde out_of_catalog, no un permiso observado; esta propuesta no declara reparada toda producción deesa prosa.

## Reparación mínima propuesta

Nuevo helper _authenticated_application_close_target: única cláusula anclada de cierra/cerra/cerrar/close, autoridad vigente, negación/cita/pasado/hipotético/deferred/dispositivoajeno conservados. Extraeel operando completo yreutiliza _application_target_forms para artículos/cortesía/puntuación. Sólo acepta claveEXACTA de catálogo OS autenticado yuna identidad única. Impide reutilizar hints de número deintentos de apertura: cualquier sufijo retirado debe ser cortesía existente, no número ni cláusula adicional.

Se conecta en3sitios existentes: reconocimiento decierre, gate dedominio app.close/window.close, gate deprerequisito window.resolve. Se conserva el resto de rutas históricas (título/ventanaactiva/contexto/nombresyaexistentes), para no eliminar conductas sin medición. No agrega nombres a _KNOWN_APPLICATION, no abre una ruta a cualquierobjeto desconocido. No añadevenas semánticas porcaso ni mezcla app.open conapp.close.

_expand_effect_plan ya agrega window.resolve a app.close y conserva evidencia literal. Este parche sólo reconoce la intención ysu dominio; NO transforma nombredecatálogo enprocessName,appId,HWND/windowId. __main__ no tiene un argumento explícito por nombrepara window.resolve, salvotítulo/inventario: la resoluciónplanificada debeobtener selector real yprovideridentidad, yrootdebe cotejar Prepared confixturepropia. No aceptar nombredeapp como prueba dequeventanaexiste oestávacía. Confirmaciónexacta1052 permanece obligatoria.

## Limitaciones ypróxima medición

No se capturó aquí el catálogo completo recibido por mente1052; verificar antes de medir si el snapshot contiene clavesexactas «bloc de notas» y«Paint». Si sólo contieneNotepad eninglés, helper no promete resolverlaexpresiónespañola: se mantiene abierto hasta evidencia deidentidad/alias existente, sin sumar aliasporliteral. Nombreautenticado no demuestra ventanaactiva yno concede cerrarunproceso. Root debe inspeccionar elprimer plan/window.resolve/Prepared en nueva tanda, abortar anteidentidad incorrecta odesconocida.

Masa demostrada:1literalH0095fallido y1variantePaintfallida; otros3literalesdenombre H0186/H0228/H0346 son candidatos pertinentes, NO fallos reparados probados. No≥10 ni4créditosgarantizados. Próximo subset debe conservar H0095 yclose1052-dev-01 como reejecuciones, más pares pertinentes ylímites de negación/cita/condición/objeto físico/referenteausente. No repetir25.

Revisión estática solamente, sin import/AST/tests/GPU/build/efectos/source/registry/commit. Identidad ySHA enIDENTITY.json. DIFF15569c2d983bf8f130c2531705b22457a4b8691c96debb7eb4dd237c39bdcfb7. Root decide integración sólo trasWEB1054.

## Revisión acotada adicional: procedencia de applicationCatalog

Cadena exacta actual, sin ejecutar producto:
1. Python __main__.py7707–7718 recibe catalog.configure; configure_application_catalog962–1005 exige objeto exacto version/verified/complete/names,version1,verified=true,complete=true ylímites de nombres/bytes; no usa sky.list_apps.
2. App MindSidecarClient.cs410–430 crea ese objeto copiando literalmente ApplicationCatalogSnapshot.Names,flagsyversion. MainWindowViewModel.cs1838–1843 pasa _coreClient.ApplicationCatalog. CoreProcessClient.cs123–129 copia hello.ApplicationCatalog ysu arrayNames; no localiza/traduce ni añadealiases.
3. Core Program.cs320–345 construye snapshot de WindowsInstalledApplicationOpenProvider.GetCatalogSnapshotAsync. Si lector/filtro falla emite verified=false,complete=false,namesvacíos; no fabrica catálogo válido.
4. Provider Applications/WindowsInstalledApplicationOpenProvider.cs266–368 llamaReadCatalogAsync yCreateCatalogSnapshot. Filtra IsUsable,normalizaNFC,descarta claves ambiguas asociadas amásdeunAppUserModelId,ordena/deduplica yacota bytes/cantidad. Names contiene nombresobservados deWindows, no una lista de aliases delmodelo.
5. Caché ReadCatalogAsync477ss reutiliza _platform.ReadCatalogAsync (vida5min). WindowsInstalledApplicationPlatform dentro delmismoarchivo820–910 ejecuta WindowsPowerShell sinperfil/noninteractive,Shell.Application COM,NameSpace('shell:AppsFolder'),Items().Name y.Path,TargetParsingPath sólo para duplicados. Decodificación StrictUTF8. Este ES el OSreader; Get-StartApps o sky.list_apps por separado no certifican el mismo conjunto filtrado ni los flags.

Evidencia privada inspeccionada:
- CLOSE1052/run-00 yREPAIR1036/run: capture/events, shell-trace, launchstdout/stderr,runtime. No hallé applicationCatalog/hello serializado en esosarchivos; shell-trace sólo acredita inicio de catalog.configure.id.1 (1052seq9,1036seq11), sinpayload ni Names. No inferir nombres por ese evento.
- CLOSE1052results/case-00/PREREG enlaza private/fixture-00.json cuyaúnicaevidencepin es fixture-00-sky-observation.json. Es observación deventana/fixture, no captura delcontrato applicationCatalog; no se usó como prueba denombres.
- Directorio exacto C03-app-intent852-proposal contiene evidence852.json yREPORT.md. evidence852 sólo proyecta2turnos deAPP_OPEN847 (Paint, candidateapp.open,0corecalls); no Names nihello. REPORT documenta reproducciones/pruebas con catálogo de fixtures. El directorio C03-app-repairs851852-private contienefuentes/worktrees ylogsowners/fast, no un snapshothello identificado. Nada deello demuestra losnombres Notepad/BlocdeNotas/Paint que recibió mente1052. No se recorrieron otrosárboles ni se declara inexistencia global.

Conclusión: la procedencia está demostrada, pero enlas capturas examinadas aúnNO hay evidencia dequé nombres exactos recibióelcontrato de1052/1036. La incertidumbre delhelperexacto1056permanece. Paint mencionadoenunturno/testoinventariosky no basta; tampoco sepuede asumir que Notepad se convierte a Bloc de notas automáticamente.

Siguiente lectura necesaria de raíz, después de WEB1054 ysinGGUF: primero reutilizar un hello.json previamente conservado delCore real actual si existe conpin/binarios/fecha; por ejemplo eladaptador1051conserva pre/hello.json (fuera delconjuntoinspeccionado aquí, no seafirman susnombres). Si no hay unorepresentativo, arrancar únicamenteCoreactualconperfilnuevo hijoDIRECTO LOCALAPPDATA/BAXY,retenerprimera líneahello completa ySHA/PID/binarios,filtrar applicationCatalog sólo para reportarversion/verified/complete,totalNames ycoincidencias exactas Notepad/Bloc de notas/Paint;cerrarstdin/esperarexit0. No llamar operaciones ni ejecutarShellCatalog porotrocamino,nocrear/abrirapps,nuevafuentedeloggingninnecesaria. Es una lectura delmismocontrato que App transmite sinmutación; no prueba retroactiva de1052, sí condiciónactual para evaluar1056.

Esta ampliación modifica sólo DIAGNOSIS.md;parche/IDENTITY/EVIDENCE intactos, sinimports/tests/GPU/Core/efectos/canónico.

Fuente adicional `src/Baxy.Core/Program.cs` SHA256 `7671087321487f4a274fb6128652e9f18ed60b212b816eef69f2deb5adb5c751`.

Fuente adicional `src/Baxy.App/CoreProcessClient.cs` SHA256 `d9cae328aa467f9a9bd793b40f306b44ad963f0340b3b296f1c390ccaafcb21e`.

Fuente adicional `src/Baxy.App/MainWindowViewModel.cs` SHA256 `7cca118cc4d4d2f271d1b498f1251eaf9b2019aea8881c707d41bb02bfc463fe`.

Fuente adicional `src/Baxy.App/MindSidecarClient.cs` SHA256 `38016ca41971b4a30eff62e7f0e47677c08b2fe9fdf6cac875b76946aea095ba`.

Fuente adicional `src/Baxy.Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs` SHA256 `8df84d96bc914b8cb2dbaad6c223e796a6aef3fe3d81eae40a3f685d71aee8ff`.

## Hecho nuevo: hello real conservado de AUDIO1051

Se leyeron exclusivamente pre/hello.json ypost/hello.json conservados por eladaptadorCoredeAUDIO1051, más REPORT yPREPARATION/candidatoenlazado para procedencia. Ambosson typehello/protocolbaxy.local.v1; applicationCatalogversion1,verified=true,complete=true,total293nombres. Enlosdos aparecen EXACTAMENTE «Bloc de notas»,«Paint»,«Calculadora»,«Google Chrome». No aparecenexactos «Notepad»,«Calculator» ni«Chrome». No es sky.list_apps ni uncatálogo defixture.

Esto resuelve lafalta deevidencia de nombres para elhelper1056: elcatálogo real anterior sí contiene clavesnormalizadasexactas bloc de notas ypaint. No hace falta añadir aliases porliteral para esosdosoperandos. No demuestra retroactivamente elpayload de1052 ni garantizaexistencia/vacío deventanas, pero sí aporta una lectura real delmismocontrato conambosnombres yflags válidos.

Pre: PID26356,2026-09-12T14:44:42.146550+00:00→14:44:44.943529,Coreexit0,statusobserved,pins_unchangedtrue. Post: PID26820,14:48:36.955642→14:48:39.332987,Coreexit0,statusobserved,pins_unchangedtrue. Preypostconservan idénticospinsbinarios.

Procedencia de candidato: private/PREPARATION.jsonSHAc905c634644f54417cbf6b2fd7c871b01f69fdf519ea1d3edf9206798322360d declaraHEAD990946e035b64426d3c0c7e5b5a4a0e3a1e9b1c1 yCANDIDATE_AUTHORIZED_v2.jsonSHAf8681ac9dc89f8ce9f08a0471f18aa76b7343e18197f26dc8592ac237daa1527 (SHAactualcomprobado). PREPARATION fija pre/REPORT SHA51f6fd00a4f64cc7cc807d7cc7183dc3ae448c918b7b1df23a477e6aa4c81be0. PinsCoreexe/dll/Providersdepreypostcoincidenconbinary_pinsdelcandidato. Loshello no tienenHEADinterno; seatribuyenporarchivosybinariosdela lectura, no comoheaderfirmado.

SHAactuales delmaterial conservado:

- `C:\Users\usuario\AppData\Local\BAXY\C03-audio1051-proposal\pre\hello.json`: `69071144590078f6b92b5d3bda1e4064e2960b9a6c9a8503717509bb1aab5fe2`.

- `C:\Users\usuario\AppData\Local\BAXY\C03-audio1051-proposal\pre\REPORT.json`: `51f6fd00a4f64cc7cc807d7cc7183dc3ae448c918b7b1df23a477e6aa4c81be0`.

- `C:\Users\usuario\AppData\Local\BAXY\C03-audio1051-proposal\post\hello.json`: `d1431323f0ed78cac5a2ff96e8aa04042dff6dc22263990938fd23135cd277fa`.

- `C:\Users\usuario\AppData\Local\BAXY\C03-audio1051-proposal\post\REPORT.json`: `e27612e0142c853a81753e7755ca4f36989f048103a6f824647b68f31a8e8fe5`.

No se necesita arrancarotroCorepara resolverestaduda léxica ahora. Rootpuede medir1056 traslatandaactiva,concatálogocandidatovigente yfixture/Preparedpropios; tampoco esta lectura acredita cierre. Sólo DIAGNOSIS1056ampliado;parche yrestoarchivosintactos,sinoperaciones/nuevoCore/GPU.
