# FILES1046 — espejo App, propuesta externa
Base HEAD leído: 15d3a5385db5db8545a0060cfd9bcf0ef4a2957f.
Único owner: src/Baxy.App/UserMessagePolicy.cs; ninguna fuente canónica modificada.
Base SHA256: aadc01838e4a6b521ee0d36a569cc3c14c284ab5777680f3de1a295b2700b3bc.
Propuesta SHA256: b897eadbd328e18a0f5f7653b6506928b2db064352ca84569fe3c073eb503fab.
DIFF.patch SHA256: 37a7fec3685a1be4ca4eda9f210826f6a6b83cac3de9dce87412e9fe7d59ab59.
Herencia FILES1046/DIFF.patch SHA256: 6683e1fae3f4bba2619d1a7ee4fd7ace5ec4c9d6c20b1d310faafe0bd3c4830d.

ReversesSuccessfulResult ya no devuelve éxito por reconocer una oración completa. El helper sustituido devuelve el texto restante tras neutralizar exclusivamente el predicado negativo ligado al query observado; LooksLikeFailure sigue inspeccionándolo. Los otros validadores reciben la respuesta original.
Se conservan kind=operation, filesystem.known.search, success, verified, succeeded, autoridad exacta, count entero cero, files vacío y query no blanco. Otra operación, recibo inválido, cinco resultados o nombre diferente no reciben esta neutralización.
La gramática coincide con el patch Python1046 y no incluye carpetas ni oraciones completas permitidas. Regex.Escape y límites de palabra conservan la ligadura al query; este reemplazo local usa CultureInvariant sin NonBacktracking porque los límites reutilizados requieren lookaround, como otros regex existentes del mismo owner.
Las cláusulas independientes de incapacidad, permisos o ejecución fallida permanecen en la comprobación de fallo. La neutralización no valida por sí misma el alcance de una afirmación ni demuestra ausencia en todo el PC.
El nuevo searchScope del provider1046 aporta raíces intentadas y límites de enumeración; exhaustive=false, ignoreInaccessible y skipReparsePoints impiden interpretarlo como inventario exhaustivo. No se añade un permiso basado en este campo ni se inventa ámbito cuando falta.

Revisión manual del diff realizada; pruebas, imports, AST, builds y ejecución omitidos por instrucción explícita. Resultado funcional pendiente de raíz, cero créditos. No se afirma corregir t4/count=5 ni su posterior veto invented.
Archivos base/ y proposal/ retienen identidad para integración; aplicar sólo DIFF.patch, sin reemplazar otros cambios de raíz.

WEB1045: el producto crea su perfil browser-profile y arranca Edge mediante CdpBrowserSession.EnsureEndpointAsync; no necesita setup externo. BAXY_CDP_ENDPOINT residual debe estar ausente para no seleccionar un navegador externo.
Approval exacto (ProductConductorHost 424–444): schema=conductor-review-approval-v1, nonce, caseId, operation, missionId, invocationId, arguments y decision=approve; exactamente ocho propiedades. Identificadores y argumentos deben coincidir con proposal.json observado; máximo una confirmación, sin reconstruir ni completar argumentos.
