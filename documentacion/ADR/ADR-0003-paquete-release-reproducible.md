# ADR-0003 — Paquete Release reproducible

- Estado: **aceptado**.
- Fecha: 2026-07-15.
- Ámbito: build y paquete offline de BAXY para `win-x64`. No decide todavía el
  lifecycle del instalador ni autenticidad de editor.

## Contexto

BAXY necesitaba separar un artefacto de desarrollo autoconsistente de un
Release atribuible a bytes exactos de un commit. La distribución debía ser
reproducible, autocontenida, utilizable sin terminal de desarrollo y honesta
ante la ausencia de firma.

El mecanismo anterior publicaba un directorio local, pero no congelaba un
contrato exacto de payload, no producía un ZIP/sidecar canónicos y no ligaba los
bytes de un Release a un snapshot Git inmutable.

## Alternativas

1. Conservar el directorio de desarrollo. Rechazado: no es una unidad de
   distribución ni demuestra procedencia o reproducibilidad.
2. Usar `Compress-Archive` o `ZipArchive` con Deflate. Rechazado: Windows
   PowerShell 5.1 no ofrece un layout byte-estable suficientemente explícito y
   `NoCompression` seguía emitiendo método Deflate.
3. Introducir WiX, Inno Setup o NSIS en este corte. Diferido: resolvería otra
   capa, pero sumaría toolchain antes de congelar el payload que debe contener.
4. Build desde snapshot Git + ZIP Stored repo-native y validado. Aceptado.

## Decisión

- Un Release limpio se compila desde un worktree detached del commit fuente.
- La app se publica .NET 10 WPF self-contained single-file con cinco DLL
  nativas adyacentes; el core se publica .NET 10 NativeAOT self-contained.
- El linker NativeAOT recibe `/Brepro`; `PathMap`, SDK fijado, versión fuente y
  `SOURCE_DATE_EPOCH` completan la receta same-host.
- `baxy-product-build-v3` admite exactamente siete archivos de usuario y
  declara `authenticity=not_provided`.
- El paquete contiene esas siete entradas, el manifiesto congelado y
  `SHA256SUMS`, todas Stored y bajo layout ZIP canónico.
- ZIP y sidecar se promueven juntos y se revalidan en destino.
- Los builds dirty solo existen bajo override explícito, con nombre y
  procedencia de desarrollo.

## Evidencia

Dos builds limpios y dos paquetes del commit `aac3e05` fueron idénticos. El
payload mide 82.842.635 bytes; el ZIP, 82.845.957 bytes y SHA-256
`11971bc0501598009145506f815407ec42a7c8fde2e88996815c1d2eaf3e7ba9`.
El gate versionado es `artifacts/product/product_package_gate.json`.

La primera réplica detectó un P1: tres timestamps PE de `link.exe` hacían variar
el core. `/Brepro` corrigió la causa y la repetición limpia completa pasó. La
auditoría final no dejó P0/P1 en el corte.

## Consecuencias

- El instalador puede consumir un único contrato de paquete estable y rechazar
  builds sucios o esquemas distintos.
- Los hashes permiten verificar consistencia y corrupción, no autenticidad del
  editor.
- Stored prioriza canonicalidad y verificación; el ZIP es aproximadamente del
  tamaño del payload.
- La reproducción acreditada es same-host; MSVC/Windows SDK y caches se
  observan, no se certifican cross-host.
- Staging y worktrees con GUID reducen colisiones, pero no sustituyen un journal
  de recuperación tras corte eléctrico ni protegen contra un atacante
  concurrente con la misma identidad.

## Fallback

Ante una regresión del writer ZIP, conservar el árbol limpio y sus hashes como
evidencia mientras se corrige el empaquetador. No volver a distribuir un build
dirty ni degradar a un ZIP no atestado.

## Criterio de reapertura

Reabrir si dos réplicas del mismo commit difieren; cambia el set de payload; el
instalador necesita metadata incompatible; aparece un P0/P1; o se adopta firma
de código/autenticidad que obligue a versionar el contrato.
