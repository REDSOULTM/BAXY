# Transporte MUSIC1065, pendiente de revisión/ejecución raíz

Corredor heredado íntegramente de MUSIC1061 salvo nombres1065, sello/snapshot y la incorporación de este documento al mapa de archivos sellados. Una sola llamada execute --case-index N (0..22) lee dos líneas originales: session.new y turn ordinary. No hay bucle automático de panel, confirmaciones automáticas, fixture mutado ni argumentos esperados enviados al producto. caseId guía observaciones, no un ordinal global de terminal.

PANEL C:/Users/usuario/AppData/Local/BAXY/C03-music1065-proposal; PRIVATE PANEL/private; PREPARATION PRIVATE/PREPARATION.json; segmentos PRIVATE/run-NN; resultados PANEL/results/case-NN. PROFILE C:/Users/usuario/AppData/Local/BAXY/C03-music1065-profile, hijo directo LOCALAPPDATA/BAXY. El prepare exige perfil nuevo; luego los segmentos comparten su marca de ownership, sin sobrescribir índices ya ejecutados.

CLI prepare: runner.py prepare --seal-sha256 SHA --expected-head HEAD40 --candidate-manifest PATH --candidate-manifest-sha256 SHA. CLI por caso: runner.py execute con esos mismos argumentos más --preparation-sha256 SHA --case-index N --fixture-receipt PATH --fixture-receipt-sha256 SHA. No ejecutar aún: candidato final y build pendientes.

Manifiesto c03-music1065-root-manifest-v1: source_pins584, binary_pins18, runtime_pins5 efectivos, registro actual SHA, build state/fingerprint, logs y receipt build/shutdown0, ejecución autorizada explícita y política no-tests del dueño. Root liga runner_sha256 y panel_seal_sha256. El runner conserva HEAD40/linaje y pins exactos antes/durante/después; no atribuye un verde histórico al nuevo candidato.

Fixture music1065-root-fixture-v1: case_index, case_id, head, candidate_manifest_sha256, panel_seal_sha256, root_verified=true, kind=owned_media_session para0..17 o no_effect para18..22, evidence_pins absolutos con hashes reales. Para controles se exige evidencia no vacía de preparación fresca, incluida observación de sesión propia; una lectura antigua no basta por compartir título. Fuente y estado por caso deben responder a las precondiciones del panel. Los límites requieren igualmente recibo raíz de no efecto.

RAM4000/768, GPU3800,900s y120000ms sin cambios. Un producto/GPU a la vez; el runner controla sólo procesos propios, conserva journal y snapshots y no restaura audio automáticamente. Raíz audita y adjudica el efecto real/terminal de cada caso. Ningún dato aquí certifica que el perfil exista, que el build esté listo o que la sesión siga pausada.
