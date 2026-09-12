# Transporte MUSIC1069, pendiente de revisión/ejecución raíz

Corredor heredado íntegramente de MUSIC1065 salvo identidad1069 y pins de sello/snapshot. Una sola llamada execute --case-index N (0..22) lee dos líneas originales: session.new y turn ordinary. No hay bucle automático de panel, confirmaciones automáticas, fixture mutado ni argumentos esperados enviados al producto. caseId guía observaciones, no un ordinal global de terminal.

PANEL C:/Users/usuario/AppData/Local/BAXY/C03-music1069-proposal; PRIVATE PANEL/private; PREPARATION PRIVATE/PREPARATION.json; segmentos PRIVATE/run-NN; resultados PANEL/results/case-NN. PROFILE C:/Users/usuario/AppData/Local/BAXY/C03-music1069-profile, hijo directo LOCALAPPDATA/BAXY. El prepare exige perfil nuevo; luego los segmentos comparten su marca de ownership, sin sobrescribir índices ya ejecutados.

CLI prepare: runner.py prepare --seal-sha256 SHA --expected-head HEAD40 --candidate-manifest PATH --candidate-manifest-sha256 SHA. CLI por caso: runner.py execute con esos mismos argumentos más --preparation-sha256 SHA --case-index N --fixture-receipt PATH --fixture-receipt-sha256 SHA. No ejecutar aún: candidato final y build pendientes.

Manifiesto c03-music1069-root-manifest-v1: source_pins584, binary_pins18, runtime_pins5 efectivos, registro actual SHA, build state/fingerprint, logs y receipt build/shutdown0, ejecución autorizada explícita y política no-tests del dueño. Root liga runner_sha256 y panel_seal_sha256. El runner conserva HEAD40/linaje y pins exactos antes/durante/después; no atribuye un verde histórico al nuevo candidato.

Fixture music1069-root-fixture-v1: case_index, case_id, head, candidate_manifest_sha256, panel_seal_sha256, root_verified=true, kind=owned_media_session para0..17 o no_effect para18..22, evidence_pins absolutos con hashes reales. Para controles se exige evidencia no vacía de preparación fresca, incluida observación de sesión propia; una lectura antigua no basta por compartir título. Fuente y estado por caso deben responder a las precondiciones del panel. Los límites requieren igualmente recibo raíz de no efecto.

RAM4000/768, GPU3800,900s y120000ms sin cambios. Un producto/GPU a la vez; el runner controla sólo procesos propios, conserva journal y snapshots y no restaura audio automáticamente. Raíz audita y adjudica el efecto real/terminal de cada caso. Ningún dato aquí certifica que el perfil exista, que el build esté listo o que la sesión siga pausada.

Helpers: root_read_media.py se hereda byte a byte1065; sólo lee media.status mediante Core existente, sin modelo. Sigue guardando lecturas en C03-music1058-preparation/read-LABEL y perfiles directos únicos; raíz debe usar etiquetas nuevas, por ejemplo1069-before-00, nunca sobrescribir. Conserva el pin del Core de BUILD1064retry1: raíz verifica vigencia .NET antes de usarlo. No se ejecuta concurrentemente con el producto/GPU.

root_execute.py sólo cambia1065→1069. Recibe INDEX, REPORT_PATH y UI_PATH; exige lectura verificada fresca, identidad de sesión propia, título/artista de los WAV y PID/creation del reproductor previamente observado. Esos asserts no prueban vigencia por sí solos: raíz vuelve a observar el proceso y la cola; si cambiaron, se detiene antes del caso. Construye el recibo por caso y llama el runner ordinary. No prepara el estado, no aprueba automáticamente operaciones y no adjudica el postestado.

No se copia root_prepare.py1065: sus asserts de diez cambios y su fabricación de candidato eran específicos de esa tanda. Root escribe el nuevo manifiesto real y usa la CLI prepare anterior. El orden dirigido0,8,9,1,10,11 y el bloqueo del resto hasta éxito son decisiones explícitas de raíz; no cambian materiales ni añaden protocolo.
