# Alcance y Definition of Done

> **Alcance retirado, 2026-08-15.** La instalación limpia, el primer
> arranque y el purge en cuenta o perfil desechable quedan **fuera de la
> definición de terminado**: el responsable del producto no dispone de una
> cuenta ni de un equipo desechable. No se miden, no se cuentan como
> pendientes y no bloquean la entrega.

## Alcance finito

El corpus probatorio de BAXY 1.0 conserva todos los mensajes históricos
dirigidos a Carter o BAXY desde el inicio de las fuentes disponibles hasta el
cutoff fijado el `2026-07-14T10:51:49Z`. Las aclaraciones del usuario que
corrijan el contrato se incorporan; capacidades nuevas posteriores solo entran
si el usuario las marca explícitamente como 1.0.

El compromiso funcional de 1.0 es español, inglés y spanglish. Incluye
code-switch natural y errores de STT cuya intención pertenezca a esos idiomas.
Los mensajes inequívocamente escritos en otras lenguas permanecen preservados
con ID, hash, fuente y mapping como trazabilidad histórica, pero son
`trace-only`: no suman cobertura de aceptación ni obligan a crear nuevas reglas
o capacidades para 1.0.

El campo derivado `language` es un detector heurístico. Puede clasificar como
`other` órdenes cortas que sí son español, inglés o spanglish; por eso el alcance
se decide mediante revisión semántica auditada, nunca filtrando mecánicamente
por ese valor.

## Must para 1.0

1. Genealogía Carter → BAXY documentada con heredar/rediseñar/descartar.
2. 100 % de mensajes del cutoff preservados, clasificados y enlazados a un
   único resultado permitido.
3. 100 % de misiones canónicas con estado esperado, plan, operaciones,
   provider, verificación, respuesta natural y prueba.
4. Ninguna solicitud histórica dentro del alcance funcional de español,
   inglés o spanglish técnicamente solucionable en unsupported o backlog.
5. Fallos históricos importantes convertidos en regresiones o gates.
6. Torneo de base cero con cortes Python, .NET y Rust/alternativa, protocolo y
   pesos publicados antes de medir, frontera de Pareto y ADR.
7. Entrada por voz y texto al mismo cerebro de misión; español, inglés y
   spanglish como alcance lingüístico funcional obligatorio de 1.0.
8. Operaciones tipadas compactas y componibles, shortlist acotado, riesgo y
   confirmación proporcionales, idempotencia y recuperación.
9. Verificación independiente antes de declarar éxito; conversación natural
   sin JSON ni trazas en modo normal.
10. Memoria local inspeccionable, corregible y borrable; privacidad y secretos
    protegidos.
11. GUI centrada en conversación y fiel a la identidad visual archivada.
12. Perfil cómodo para 4 GB de VRAM con objetivo aproximado de 3 GB cuando sea
    viable, CPU fallback y mediciones honestas de RAM/VRAM/latencia/estabilidad.
13. Unitarias, contratos, integración, replay, E2E y gates físicos
    representativos; cero P0/P1 conocidos y cleanup correcto.
14. Instalador o paquete reproducible que no dependa de terminal de desarrollo,
    checksum. La instalación limpia queda retirada del alcance (2026-08-15).
15. Documentación de configuración, privacidad, operación, doctor,
    actualización, desinstalación y rollback; comparación con versiones
    anteriores y commit final.

## Cálculo de progreso

El porcentaje es `gates Must aprobados / 15`. Un gate solo aprueba con evidencia
enlazada; avance parcial interno no redondea el gate.

## Should si cabe

- Mejoras de calidad que superen la expectativa histórica sin ser necesarias
  para resolverla.
- Perfiles opt-in de mayor calidad que no comprometan el perfil base.
- Ergonomía adicional que no retrase la entrega.

## Después de 1.0

Solo capacidades nunca pedidas, experimentos y optimizaciones que no reparen un
Must, P0/P1 o regresión histórica. El archivo canónico es
`../07_riesgos_y_pendientes/BACKLOG_POST_ENTREGA.md`.

## Regla de parada

Al aprobar los gates vigentes: empaquetar, checksum, smoke,
congelar versiones, documentar, commit final, marcar el objetivo completo y
detener expansión u optimización.
