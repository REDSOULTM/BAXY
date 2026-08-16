# Auditoría nocturna BAXY — 2026-07-27

## Alcance

- Repositorio canónico: `D:\BAXY\source`
- Rama: `codex/baxy-rebuild-v3`
- Commit auditado: `f23b23f064211154e954d82883ba6bee5c2c466c`
- Versión esperada: BAXY 1.0.8
- Inicio: 2026-07-27 00:52 America/Santiago
- Fin planificado: 2026-07-27 12:52 America/Santiago
- Modalidad: auditoría funcional; no se corrigen defectos.

## Reglas

1. Probar primero compuertas automatizadas y después efectos físicos.
2. Verificar el estado observable; un comando enviado no cuenta como éxito.
3. Restaurar estado reversible cuando sea posible.
4. No enviar mensajes o correos, borrar datos, comprar, imprimir, instalar,
   emparejar dispositivos ni cambiar cuentas o redes.
5. Registrar cada defecto reproducible en `BACKLOG.md`; no editar el producto.

## Capas de cobertura

- Baseline: suites Python y .NET.
- Arranque: instalación activa, desarrollo, readiness y cierre limpio.
- Conversación: español, inglés, spanglish, preguntas, negaciones y OOD.
- Acciones simples: aplicaciones, ventanas, teclado, mouse, volumen y estado.
- Multimedia: Spotify, reproducción exacta, pausa/reanudación y restauración.
- Navegación: abrir navegador, URL, búsqueda, lectura y acciones encadenadas.
- Planes: dependencias, fallo intermedio, confirmación y recuperación.
- Voz: STT, TTS, micrófono, loopback, cancelación, ducking y wake.
- Resiliencia: repetición, reinicio, timeout, procesos huérfanos y soak.
- UX: mensajes naturales, progreso y ausencia de detalles internos.
- Catálogo: smoke test de las 168 operaciones; los efectos sensibles se
  ejercitan por contrato, confirmación o simulación segura.
- Diagnóstico: causa raíz documentada de cada defecto sin aplicar correcciones.

## Resultado final

La auditoría cubrió la ventana completa de 12 horas, desde las 00:52 hasta las
12:52 (America/Santiago), sobre BAXY 1.0.8 y el commit
`f23b23f064211154e954d82883ba6bee5c2c466c`. No se modificó código del
producto.

- Suite Python: 611 pruebas + 350 subtests, 0 fallos; la repetición bajo carga
  volvió a aprobar el mismo conteo.
- Suite .NET: 2.080 casos, 2.063 aprobados, 17 omitidos y 0 fallos; la
  repetición bajo carga coincidió exactamente.
- Catálogo: 168 operaciones; 149 ejercitadas funcionalmente y 135 con éxito
  verificado. Las 19 no ejecutadas quedaron excluidas por comunicación
  externa, instalación, compra, privacidad o riesgo de pérdida de trabajo.
- Soak del core: 10,019 horas, 6.826 llamadas, seis reinicios/segmentos, cero
  anomalías y sin error final.
- Soak del modelo: 8,713 horas, 522 decisiones, cinco segmentos, cero anomalías
  de proceso/protocolo y sin error final. Solo 205/522 decisiones conservaron
  la intención (39,27 %), confirmando el defecto sistémico de enrutamiento.
- Stress adicional: 5.000/5.000 respuestas en ráfaga; 500/500 entradas
  adversarias rechazadas con recuperación posterior; 36/36 arranques
  simultáneos del core; 20/20 recuperaciones tras cierre abrupto; 200/200
  ciclos diagnósticos de UI.
- Backlog: 27 defectos confirmados y no corregidos (16 P1, 11 P2), todos con
  causa, reproducción y evidencia.
- Limpieza: no quedaron procesos, perfiles aislados ni aplicaciones creadas
  por la auditoría. El estado reversible del equipo fue restaurado y los
  procesos preexistentes del usuario se conservaron.

## Entregables

- `RESULTS.md`: cronología y resultados detallados.
- `BACKLOG.md`: defectos reproducibles y causas.
- `operation_coverage.json`: cobertura por operación y exclusiones por riesgo.
- `soak_summary_final.json`: métricas consolidadas de core y modelo.
- `overnight_soak_installed.json`: evidencia completa del soak del core.
- `mind_overnight_soak_installed.json`: evidencia completa del soak LLM.
