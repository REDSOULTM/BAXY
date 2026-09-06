# Fase 12 — del árbol validado al producto entregable

Mapa, no prompt ejecutable. Después de 11.16. Hace explícitos los compromisos
de producto diferidos por `00_ALCANCE_DESARROLLO_VS_PRODUCTO.md`; no añade
funcionalidades nuevas ni sustituye C03–C09 o la aceptación del 10.

| Orden | Prompt | Qué demuestra |
|---|---|---|
| 12.1 | [Instalación y ciclo de vida](12.1_INSTALACION.md) | Paquete reproducible, inicio real, actualización/rollback y borrado de datos propios. |
| 12.2 | [Hardware objetivo](12.2_HARDWARE.md) | Producto completo en perfil GPU 4 GB y CPU 8 GB, incluida voz/presencia. |
| 12.3 | [Aceptación y entrega](12.3_ENTREGA.md) | Mismo candidato instalado, conducta diaria y todos los compromisos acreditados. |

11.16 entrega un candidato de desarrollo validado. Sólo 12.3 declara
**BAXY_DEFINITIVO_VALIDADO**, con versión, alcance y evidencia. Ningún sprint
garantiza ausencia universal de errores: se certifican las pruebas y condiciones
publicadas, sin defectos conocidos pendientes del alcance.

Si falta hardware/cuenta Windows/certificado, se prepara lo automatizable y se
deja BLOQUEADO_ENTORNO con acción exacta. La falta no es un pass ni obliga a
repetir C03. El certificado de firma es requisito de distribución según el
alcance existente; no se compra ni se publica a terceros desde un test.

Los fixtures de apagado, borrado o comunicación prueban sus fronteras, no el
efecto real. El cierre exige el efecto en entorno desechable/controlado cuando
sea una capacidad comprometida; jamás sobre datos o sesiones personales.

Protocolo único: [ejecución](00_PROTOCOLO_EJECUCION.md). Los mínimos originales
se conservan. Un cambio de producto durante 12 invalida y revalida dependencias
de 10/11; no basta volver a empaquetar.
