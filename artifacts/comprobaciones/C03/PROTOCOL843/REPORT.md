# C03 — respuesta densa y recuperación — 843

Una lectura OCR real se guardó como completada y verificada, pero Core se cerró antes de entregarla: Message tenía 6532 unidades UTF-16 y el contrato admitía4096. Kernel y App ya admitían48000. Se unifica ese límite en Contracts exclusivamente para OperationResponse.Message; los otros límites4096 y el frame1MiB permanecen. No se modifica texto, geometría, modelo o presupuesto.

El parche de ocho archivos se adopta dentro de ese alcance. Rojo conductual:8 fallos; dueñas raíz118 pass/0 fail/0 skip. `scripts/test_source_quality.ps1 -Mode Full -QualityPython C:/Users/usuario/AppData/Local/BAXYQuality/source-quality-v1/Scripts/python.exe` terminó0, sesión33623 recogida c329d6. Release7,89s, cero advertencias/errores;60 fuentes selladas intactas.

| Suite | Pass | Fail | Omisiones agregadas |
|---|---:|---:|---:|
| Contracts | 70 | 0 | 0 |
| Integration | 3443 | 0 | 1 |
| Kernel | 162 | 0 | 0 |
| Providers.Windows | 602 | 0 | 0 |
| Setup | 477 | 0 | 0 |
| Python | 12907 | 0 | 3 |

Las16 líneas optativas .NET son una vista diagnóstica no disjunta, no16 pases u omisiones adicionales. Python informa además466 subpruebas aprobadas, separadas de los12907 tests;658,25s. Las causas de sus tres skips no aparecen en este log. Full no acredita las rutas omitidas ni cierra C03.

La prueba real reabrió el mismo diario autenticado y recuperó la invocación completada con requestId nuevo: Coreexit0, respuesta completed/verified/replayed,6532UTF16/6535UTF8, frame18716bytes. Message y Result coinciden con lo persistido; diario y69 pins de fuente/binarios permanecen intactos. No se ejecutó otro OCR. La proyección real de App sobre ese replay conservó exactamente texto, layout y hash de imagen; MessageCore=MessageApp, SHA5eba86f6fb4960c9886364c222847e94dff6a1e332e55184bf6dc6f63cf79cb7.

La utilidad externa844 tuvo un error de compilación por un import faltante y luego una advertencia de nulabilidad; se corrigieron sin tocar producto. Compilación final0/0warnings/0errors, ejecución0. Se preservaron los tres logs. Llamar a la proyección App aisladamente no acredita App→Mind, interfaz, una captura nueva o la respuesta de H0675.

C03 sigue EN_CURSO:36/742 cubiertos,706 abiertos,0NA;matriz3/11;procesos49/50. Quedan dos observaciones nuevas y el oráculo raíz antes de834-O, además del pedido original834-E. La solicitud de ampliar el Administrador de tareas continúa pendiente. Apps75 está preparado sin ejecución; no se cambian sus textos. Los datos de pantalla y payloads se conservan sólo en privado. Ver FULL_RESULT, REPLAY_RESULT, PROJECTION844_RESULT y ADOPTION.
