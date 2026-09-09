# 326 — comprobación del filtro de propuesta operativa

Baseline nueva: 6 fail, 5 pass, 0 skips, 206 ms. Cinco ofertas reales eran
rechazadas correctamente; cinco seguimientos conversacionales y la respuesta
literal contextual se rechazaban erróneamente.

Primer owners: 127 pass, 1 fail, 0 skips, 4 m 3 s. El control histórico de
«¿Qué quieres que cierra?» detectó que también debe reconocerse un verbo operativo
sin objeto. Se reutilizó la lista de verbos existente; no se modificó esa prueba.
La clase MindShellEndToEndTests pasó en este conjunto.

Final: `dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter 'FullyQualifiedName~C03FactPreservationTests|FullyQualifiedName~Goal06VisibleVoiceTests'`
→ **93 pass, 0 fail, 0 skips, 11 s** (owners-final.log).

`.\scripts\test_source_quality.ps1 -Mode Fast` → verde, build Release16,12 s,
0 advertencias, 0 errores (fast326.log).

Se reemplaza LooksLikeCatalogProposal por extracción de la cláusula propuesta;
el resto de la explicación no aporta familias a ese filtro. Se requieren
familias o verbos operativos reconocibles. Sin cambios de modelo, prompts,
permisos ni ejecución. Producto327 en curso, todavía sin adjudicación.
