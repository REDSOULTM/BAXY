# MUSIC1086 — runner segmentado heredado1082

Derivación directa del runner1082: identidad/rutas/esquemas1086,12casos/24wire,3literales/4variantes/5límites y procedencia4reejecuciones+6heredados no ejecutados+2nuevos. HEAD sigue40hex; fuentes584/binarios18/runtime5 conservados, sin verdes históricos atribuidos. Perfiles C03-music1086-caseNN-profile directos y nuevos para cada segmento; salida private/run-NN y results/case-NN dentro propuesta.

Preparación exige manifiesto raíz c03-music1086-root-manifest-v1 con candidato reparado1084, hashes reales y build/fingerprint vigente elegido por raíz. Sello mantiene candidate=null,fixture=null,execution_authorized=false; autorización va en manifiesto externo revisado, no en datos. No se ejecutó prepare/run.

Guardas iguales:4000MiB preflight,768MiB runtime,3800MiB GPU,900s global,120000ms por turno. Muestreo, invocaciones, métricas, stop, comprobación de pins y cleanup sólo del child heredados. Se selecciona un --case-index0..11, nunca un lote automático. Rootfixture debe ligar índice/caseID/head/SEAL y estado/cola observados antes de cada caso; root aprueba pertinencia del vecino y ausencia de autoavance.

Se ejecuta session.new+turn exactos. media.control LowReversible no lleva review ni confirmación; cualquier señal no prevista se conserva y raíz decide. No se cambia fuente, volumen,cola,app ni perfil del usuario mediante este runner. Referencias de lectura reales se proveerán por raíz antes de cada segmento; no se genera una fixture afirmando observación.

RUNNER_DIFF.patch contiene adaptación completa para revisión; no está dentro del sello de material para evitar dependencia circular. El hash final de runner se liga por manifiesto raíz y DELIVERY.json, no como supuesto candidato. PLAN_RUNNER sí está sellado.
