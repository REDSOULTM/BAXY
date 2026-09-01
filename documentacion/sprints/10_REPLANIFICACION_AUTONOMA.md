# Replanificación del Goal 10 — certificación antes del uso cotidiano

Decisión del dueño del producto del **2026-09-01**. Esta decisión sustituye el
orden que exigía cuatro tandas humanas en `10.3`–`10.6` antes de validar las
familias funcionales.

## Problema corregido

El orden anterior convertía al dueño en detector de defectos básicos: pedía 200
turnos de uso personal cuando conversación, hechos locales, web, aplicaciones,
audio, productividad y misiones compuestas todavía no habían pasado sus campañas
dueñas. Un fallo temprano bloqueaba la campaña por disponibilidad humana, no por
una propiedad del producto.

## Decisión vinculante

- `10.3_USO_REAL_A.md`–`10.6_USO_REAL_D.md` quedan **retirados y no se lanzan**.
  El preflight publicado de 10.3 se conserva como evidencia histórica, pero su
  contador `0/50` no es deuda ni criterio pendiente.
- Después del cierre ya publicado de `10.2.5`, la secuencia continúa en
  `10.7_CONVERSACION.md` y recorre `10.8`–`10.17`.
- `10.18_INTEGRACION.md` absorbe la aceptación transversal: cuatro bloques
  autónomos de 50 turnos frescos, 200 en total, ejecutados por agentes a través de
  la **misma entrada pública de usuario** del producto.
- El dueño no tiene que proporcionar prompts, voz, observación ni disponibilidad
  para cerrar Goal 10. Los agentes generan las entradas desde contratos congelados
  y holdouts, conducen BAXY y verifican el resultado con un oráculo independiente.
- No se llama “uso real” a una invocación directa de `baxy_mind`, Core, Kernel o
  providers. Un turno cuenta sólo si cruza la superficie pública de texto o la
  ruta pública de voz. Las operaciones peligrosas mantienen fixture fiel; los
  efectos seguros y reversibles se verifican físicamente.

## Qué significa certificado

El cierre no promete que ningún software pueda fallar jamás. Promete algo
verificable: sobre el commit y ambiente certificados quedan **cero fallos
reproducibles conocidos dentro del alcance** después de `N10/M10/C10`, sus
holdouts frescos, 200 turnos transversales, reinicios, continuidad de sesión,
restauración de estado, Identidad y Full. Un fallo observado durante la campaña
se corrige en su owner y se repite el bloque afectado antes de avanzar.

## Orden vigente

`10.2.5` cerrado → `10.7` conversación → `10.8` hechos locales → `10.9` web →
`10.10` apps/ventanas/visión → `10.11` audio → `10.12` media → `10.13` sistema →
`10.14` productividad/memoria → `10.15` comunicación/navegación → `10.16`
misiones compuestas → `10.17` Identidad → `10.18` certificación integral →
`11.1`.

