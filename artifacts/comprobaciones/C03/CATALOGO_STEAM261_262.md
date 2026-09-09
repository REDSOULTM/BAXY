# C03 — Steam desaparecía del catálogo: tramos261–262

## Causa demostrada

Los tres textos literales de UI260 se reprodujeron sólo en retrieval, con el
Core actual y el E5 fijado, sin ejecutar operaciones ni LLM. `app.open` ocupó
puestos semánticos116,15,26 para «Tengo en mente que abras steam», «abre steam»
y «Si, abre steam». La primera shortlist coincide exactamente con UI260:
la operación no llegó al selector. Es un problema de recuperación independiente.

Además, el hello de Core exponía292 aplicaciones y ninguna llamada Steam.
Get-StartApps devolvió dos Steam con AppID distintos. Shell AppsFolder expuso:

| Identidad | Destino observado | Estado local |
|---|---|---|
| Valve.Steam.Client | D:\Steam\steam.exe | Existe,5.775.512bytes. |
| {7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}\Steam\Steam.exe | C:\Program Files (x86)\Steam\Steam.exe | No existe. |

CreateCatalogSnapshot eliminaba cualquier nombre con más de un AppID, y el
resolver también rechazaba esa ambigüedad. El duplicado antiguo ocultaba la
instalación utilizable. No se borró ni modificó ningún acceso directo.

## Contraste y reparación mínima

Se conservó Get-StartApps y la validación de identidades heredada. La alternativa
de elegir la primera coincidencia permitiría ejecutar una instalación incorrecta:
se descartó. Microsoft documenta AUMID como identidad de lanzamiento y
System.Link.TargetParsingPath como destino Shell; no se dedujo una ruta del AppID.
Consulta2026-09-07:

- https://learn.microsoft.com/en-us/windows/configuration/store/find-aumid
- https://learn.microsoft.com/en-us/windows/win32/properties/props-system-link-targetparsingpath
- https://devblogs.microsoft.com/oldnewthing/20251219-00/?p=111885

Sólo para nombres duplicados, WindowsInstalledApplicationPlatform añade el
destino informado por Shell. Conserva una identidad únicamente si tiene un
ejecutable local existente y todas las identidades alternativas tienen destinos
locales comprobados como ausentes. Dos destinos existentes, metadatos desconocidos,
red, instaladores MSI, directorios y acceso denegado no resuelven la ambigüedad.
No equivale File.Exists=false a ausencia: sólo FileNotFound/DirectoryNotFound
con raíz local disponible aportan esa evidencia. El filtro vive en la lectura
del provider, compartida por publicación, resolución y ejecución.

## Validación

`dotnet test tests/Baxy.Providers.Windows.Tests -c Release --nologo -v:minimal
--filter FullyQualifiedName~WindowsInstalledApplicationOpenProviderTests`:
primera tanda38pass/0skips; final39pass/0skips,108ms. Se añadió protección de
ruta inválida antes de la tanda final. Controles con nombres ajenos a Steam:
destino presente/ausente,ambos presentes,desconocido,ambos ausentes,misma identidad,
URL/ruta remota/directorio y archivos temporales reales. La publicación del
catálogo y el resolver se comprueban conjuntamente.

`scripts/test_source_quality.ps1`: Fast completo verde; Release22,27s,
0advertencias/errores. No Full durante reparación.

Nuevo hello del Core Release reconstruido: **293 nombres, único añadido Steam,
ningún nombre retirado y169 operaciones idénticas**. «abre steam» resuelve a
Steam. `CORE_RESULT.json` conserva huellas de Core y provider. Esta es lectura
de catálogo, todavía no una prueba de abrir/enfocar Steam desde la UI nueva.

## Pendiente causal, no ocultarlo

La corrección de identidad no cambia retrieval. «Tengo en mente que abras steam»
sigue sin identidad extraída por resolve_application_catalog_app_id, y `app.open`
continúa fuera del top28 calculado261. «Si, abre steam» también devuelve null en
ese helper aislado; eso no prueba toda la ruta contextual. Se deben comparar los
recorridos integrados, sin añadir prefijos por frase ni promover esta reparación
como C03 completo. También queda la generalización falsa de capacidades tras un
fallo previo, observada en UI260. Reserva100/100 aún sin congelar.

Sesiones63898(261),98309(38tests),26242(39tests/Fast) terminales exit0 recogidas.
Core262 lectura síncrona exit0, cerrada por helper; ningún lanzamiento de apps.
Fuente262: sólo provider y test dueño editados. Registro LLM intacto; Qwen3.5
sigue candidato por override. C03 íntegro EN_CURSO.
