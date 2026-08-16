# Checklist de release

> **Alcance retirado, 2026-08-15.** La instalación limpia, el primer
> arranque y el purge en cuenta o perfil desechable quedan **fuera de la
> definición de terminado**: el responsable del producto no dispone de una
> cuenta ni de un equipo desechable. No se miden, no se cuentan como
> pendientes y no bloquean la entrega.

- [ ] 15/15 gates Must aprobados —estado honesto: 8/15; cinco son frontera
  Fable y dos esperan entorno limpio.
- [x] Cero P0/P1 conocidos.
- [x] Versiones, dependencias y configuración del cuerpo congeladas.
- [x] Paquete offline reproducible generado desde snapshot Git limpio.
- [x] SHA-256 y evidencia reproducible del paquete versionados.
- [x] Setup NativeAOT embebido reproducible y checksum/evidencia versionados.
- [x] Motor transaccional de instalación y recovery cubierto por fault matrix.
- [x] GUI fiel: misión WPF física, respuesta UIA, captura nativa e identidad
  archivada verificadas en `artifacts/product/gui_capture_gate.json`.
- [x] Instalador por usuario generado con install/update/rollback/uninstall.
- ~~Instalación limpia ejecutada.~~ (retirado del alcance 2026-08-15)
- [x] Lifecycle same-host install/update/rollback/keep-data ejecutado sin residuos.
- ~~Primer inicio instalado y purge-data en perfil desechable.~~ (retirado del alcance 2026-08-15)
- [x] Smoke final del core NativeAOT: 21 tools públicas, schemas cerrados,
  `app.status` interno, stderr vacío y limpieza exacta.
- [ ] Misión compuesta general ejecutada —requiere planner Fable.
- [x] Privacidad determinista aprobada en Gate 10; update/rollback/keep-data
  tienen evidencia física en `artifacts/setup/gate14_lifecycle_gate.json`.
- [x] Comparación con Carter/FunctionGemma/BAXY anterior documentada.
- [x] Contexto final actualizado.
- [x] Commit final de la frontera determinista preparado; los Must de Fable y
  de entorno limpio no se marcan completos por inferencia.
