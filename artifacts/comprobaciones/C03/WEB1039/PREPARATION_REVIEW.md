# WEB1039 — material sellado y runner, sin ejecución
Se leyó PLAN público raíz antes del sello y se copió byte por byte a PLAN.md. Registro156 SHA11fc78167e4e935b5f2e63913214e88e4d966923496a4b808dfc54bf83c00229; snapshot completo preservado.
17 casos/34wire: H0326/H0605 exactos,10variantes,5límites. Comparación de datos:17textos/criterios/kinds idénticos al draft;17entradasmapa y34líneas; cinco hashes de materiales coinciden con SEAL. Es revisión de datos y diff, no ejecución de Python/AST/import/test.
Se conservó kind boundary original; runner exige esa misma clasificación. Positivos sin antecedente textual requerido; session.new no borra historialCDP. Argumentos esperados sólo comparan, no se inyectan al producto.
Runner clonado de REPAIR1036: únicamente identidad/rutas/schemas/conteos, registry/seal, más guarda de preparación solicitada. Diff +46/−22 en RUNNER_DIFF.patch. Guardas4000/768/3800/900/120000,584fuentes/18binarios/5runtime, no-tests, parentela, PIDcleanup y guardado de evidencia intactos. Sin atribuir verdes previos.
Manifiesto requerido c03-web1039-root-manifest-v1 conserva contrato1036 y añade browser_preparation={endpoint,receipt_path,receipt_sha256}. Recibo privado SHA exacto: endpoint igual, target_id no vacío, entry_count entero>=13,page_target_count=1. RootPLAN requiere25entradas observadas: el piso13 del runner sólo asegura espacio nominal para12retrocesos y no sustituye la revisión raíz de posición final/identidad/historial.
BAXY_CDP_ENDPOINT debe existir y coincidir exactamente con manifiesto en prepare/run; URLloopbackHTTP explícita sin credenciales. Filtroenvheredado no elimina ese nombre; se comprueba otra vez antesdePopen y queda en runtime.json. Recibo preparación entra en pins monitorizados. Ningún HTTP/CDP/reseed de runner, ni otroCorepara preparación.
Edgepreparado fuera del árbolBAXY requiere medición/identidad e historial inicial/final por raíz; RAMglobal mantiene guardas. Runner no lo cierra ni manipula; cleanup raíz sólo despuésdeobservación final. Una sola page target evita resolver página arbitraria; no perfilusuario.
Candidato pendiente y autorización de materialfalse; raíz ligaHEAD/binarios/entorno/reciboantesprepare/run. No ejecución de stages, GPU, pruebas, compilación, fuente, registro ni URLs por este agente.

SHA256 finales:
- panel.json: bb8c5ba88b456faf21deaf17d8fd5ed07c672f637d88175d7b189c4e306b5cbc
- turns.jsonl: b2937a09b632ed11942fd9a1d55f5986af1723c942e72f28c69c0ae98f0917ae
- case-map.json: f9ad60b628ee54c838950b3a01bd22a66330a985ed9de84c714cc5439d81410a
- PLAN.md: 9e7fa665bff8316708dabda75f919182308ad9d78dc98849136599c828b1583b
- requirements-snapshot.jsonl: 11fc78167e4e935b5f2e63913214e88e4d966923496a4b808dfc54bf83c00229
- SEAL.json: 5a153d1202eb0e6b978418bbb4ce15a3bd2423c687e2596a3db8c8596b7b7d81
- runner.py: 6d73b166441c4bbfd9b202c9af00248a91636d4bd7edfe129a05e36f8b2b21ab