# BAXY FieldUi

FieldUi es la presentación React/TypeScript que `Baxy.App` muestra dentro de
WebView2. No es una SPA desplegada, un servidor ni el backend de BAXY.

La arquitectura completa está en
[`documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/README.md`](../../documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/README.md).

## Estado de procedencia

ADR-0008 restauró literalmente la interfaz histórica solicitada por el usuario.
La procedencia exacta está en [ORIGIN.md](ORIGIN.md):

- `src/` permite inspeccionar y validar la presentación histórica intacta;
- `dist/` contiene los tres blobs que carga el producto;
- ambos tienen tests y hashes de procedencia y del sello vigente;
- el `dist/` versionado es una excepción deliberada a la regla de outputs
  generados.

No ejecutes `pnpm build` como parte de una prueba rutinaria: reemplazaría el
payload histórico. Modificar la presentación o regenerar `dist/` requiere
reabrir ADR-0008, actualizar source, bridge, procedencia y pruebas como una
unidad.

## Runtime

```text
Baxy.App (WPF)
  → MainWindowSurfacePresenter
  → WebView2 local
  → Baxy.FieldUi/dist
  → field-native-bridge.js
  → mensajes baxy.field.v1
  → FieldUiBridge.cs
  → MainWindowViewModel
```

No se abre un puerto HTTP. La App configura un virtual host local, inyecta
`src/Baxy.App/Assets/field-native-bridge.js` antes del documento y bloquea:

- navegación externa;
- ventanas nuevas;
- requests de red arbitrarios;
- ejecución directa de JSON/tools;
- adjuntos sin contrato tipado.

FieldUi no recibe autoridad del sistema operativo y nunca habla directamente
con Core, Mind o Providers.

## Estructura

| Ruta | Rol |
|---|---|
| `src/App.tsx` | composición de la interfaz y estado de paneles |
| `src/components/` | superficies visuales |
| `src/hooks/useEventStream.ts` | consumo del stream adaptado |
| `src/hooks/useToast.ts` | mensajes de presentación |
| `src/types.ts` | tipos del contrato visible |
| `src/styles/prototype.css` | estilo histórico |
| `src/main.tsx` | entrypoint React |
| `dist/` | payload exacto servido por App |
| `vite.config.ts` | build histórico verificable |
| `pnpm-lock.yaml` | grafo JS fijado |
| `ORIGIN.md` | commits/hashes de procedencia |

El perfil y la superficie seleccionada usan `localStorage` del origen local
solo como estado de presentación. El estado autoritativo de misión, plan,
memoria y providers reside en App/Core.

## Contrato del bridge

El canal es `baxy.field.v1`. El bridge adapta los `fetch` y WebSocket que
esperaba la interfaz histórica a mensajes WebView2 tipados.

Familias expuestas:

- estado de agente, modelo, métricas y hardware;
- superficies;
- voz;
- envío de turnos y actividad;
- sesiones;
- proyecciones acotadas de memoria, triggers y tools;
- perfil, accesibilidad y settings administrados;
- inventario y lifecycle controlado.

`src/Baxy.App/FieldUiBridge.cs` es el consumidor autoritativo. Una route nueva
o un cambio de shape exige:

1. versión/compatibilidad explícita;
2. cambio coordinado en JS y C#;
3. validación de origen, método, payload y límites;
4. test en `Baxy.Integration.Tests`;
5. actualización de la guía de contratos;
6. revisión del sello visual si cambia `dist/`.

No agregues un proxy genérico para invocar operaciones.

## Preparar dependencias

Desde esta carpeta:

```powershell
pnpm install --frozen-lockfile
```

El repositorio fija el grafo en `pnpm-lock.yaml`, pero todavía no fija la
versión de Node ni de pnpm. Si una diferencia de toolchain modifica el lock o
los bytes producidos, detente y no la normalices silenciosamente.

## Validar sin regenerar

```powershell
.\node_modules\.bin\eslint.cmd . --max-warnings 0
.\node_modules\.bin\tsc.cmd --noEmit --incremental false `
  --pretty false -p .\tsconfig.app.json
.\node_modules\.bin\tsc.cmd --noEmit --incremental false `
  --pretty false -p .\tsconfig.node.json
```

Desde la raíz del repositorio, `scripts/test_source_quality.ps1` ejecuta los
tres checks. No emite archivos y no toca `dist/`.

## Build deliberado

Solo después de autorizar la reapertura del sello:

```powershell
pnpm build
```

Después hay que:

- revisar cada cambio visual y de bundle;
- actualizar `ORIGIN.md`;
- actualizar hashes y tests de blobs;
- validar el bridge;
- ejecutar la compuerta completa;
- abrir BAXY físicamente y revisar WebView2, foco, navegación, accesibilidad y
  DPI;
- confirmar que no hubo red externa.

El servidor `pnpm dev` sirve únicamente para iteración visual aislada. No
reproduce el bridge nativo ni demuestra la conducta integrada.

## Extensión preferida

Para una nueva vista nativa que no exige alterar la interfaz histórica, usa la
costura bajo `src/Baxy.App/Presentation`:

- `AppSurfaceCatalog`;
- `AppSurfaceNavigator`;
- `MainWindowSurfacePresenter`;
- una factory lazy que devuelve `AppSurfaceSession`.

Esa ruta permite agregar una superficie WPF con ownership y lifecycle propios
sin mutar el Field sellado. Añadir una entrada desde React sigue siendo un
cambio del bridge.

## Pruebas relacionadas

- `tests/Baxy.Integration.Tests/MainWindowShellContractTests.cs`;
- `tests/Baxy.Integration.Tests/AppSurfaceNavigatorTests.cs`;
- tests de `FieldUiBridge` y contrato del shell dentro de Integration;
- tests que fijan hashes/procedencia de ADR-0008;
- ESLint y ambos proyectos TypeScript en la compuerta de calidad.

Una captura visual es evidencia útil, pero no sustituye tests de contrato,
teclado, foco, accesibilidad o bloqueo de navegación.
