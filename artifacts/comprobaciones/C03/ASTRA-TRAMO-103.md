# Tramo103 — hacer visible el progreso, 2026-09-07

Hipótesis: la primera pérdida restante está en FieldCenter. UI102 conserva ocho
finales pero oculta el aviso detrás de draft durante la espera del POST /turn.
La evidencia está en PRUEBAS_UI102.md, incluidos cinco cuadros intermedios.

Herencia: ADR-0008 y ORIGIN.md conservan la UI histórica y dos reaperturas
deliberadas. Se consideró la superposición del bridge nativo, ya usada para
identidad, pero añadir allí otro lector/estado del progreso duplicaría el lector
React que ya recibe boot_stage. Se adapta su dueño FieldCenter y se regenera
deliberadamente el payload, igual que la reapertura de recursos de agosto.

Contraste actual consultado 2026-09-07:
[HTML placeholder](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/placeholder)
confirma que sólo se muestra sin valor; [ARIA live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions)
recomienda una región de estado existente antes del cambio de contenido.

Única diferencia funcional: la etiqueta recibida ocupa una región role=status
encima del input. Sustituye su uso como placeholder; conserva el borrador y el
lector existente, incluido el borrado al completar o cambiar fase. No agrega
prosa fija, otro generador, estado paralelo ni transformación de hechos.

Criterio antes de ejecutar: observar un aviso generado antes del final en los
mismos casos de lectura de UI102, en español e inglés; comprobar que desaparece
al finalizar y que el borrador no lo oculta. Conservar los ocho finales útiles.
Validación pendiente: build UI sellado, pruebas dueñas de shell/progreso, Fast y
producto real con py main.py. No Full durante reparación.

Build deliberado `pnpm build`: exit0, TypeScript y Vite8.0.12,37 módulos,
476ms Vite. Sello conjunto de38archivos
5396C5B4C33FAA3603CED416017EED5D44E0B03949A8C82D920C43F25BAF3687.
`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~MainWindowShellContractTests|FullyQualifiedName~FieldProgressContractTests|FullyQualifiedName~MissionInputPipelineTests'`:
97pass,0skips,12s;handle13098exit0; TEMP/c03-ui103-dotnet.log.

Fast inicial no arrancó: se indicó Python312 de pruebas, sin Ruff; usar el
resolvedor predeterminado de calidad. Primer Fast real55553exit1 detectó CRLF
introducido por write_text en MainWindowShellContractTests; se restauró LF y
se corrigió el script de sellado. El diff C# vuelve a ser una línea de hash.
Evidencia conservada TEMP/c03-ui103-fast.log y c03-ui103-fast-default.log.
Fast corregido73364 sigue ejecutándose al escribir; no se declara verde aún.

Resultado posterior: Fast73364exit0, Release18,95s, cero avisos/errores,
TEMP/c03-ui103-fast-final.log. UI104 prerregistrado con hashes verificados y
launcher72826 activo desde py main.py. No otros builds/modelos mientras dure UI104.
