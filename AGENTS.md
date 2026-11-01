# AGENTS.md

Guía corta para agentes de programación (y personas) que trabajan en este repositorio. Para qué es BAXY y cómo
funciona: el [README](README.md) y [docs/arquitectura.md](docs/arquitectura.md).

## Mapa

Producto híbrido **.NET 10 + Python 3.12 + React/TypeScript**, sólo Windows. La shell es PowerShell.

| Pieza | Dónde | Qué hace |
|---|---|---|
| Arranque de desarrollo | `main.py` | `py -3.12 main.py`: compila lo que cambió y lanza la App |
| App | `src/Baxy.App/` | Ventana WPF + WebView2, canal con la mente, voz |
| Interfaz | `src/Baxy.FieldUi/` | React + TypeScript; `dist/` se versiona |
| Core | `src/Baxy.Core/` | `baxy-core.exe` (NativeAOT), manejadores de operaciones |
| Kernel | `src/Baxy.Kernel/` | Catálogo (`Operations/ProductCatalog.cs`), riesgo, confirmación, diario |
| Contratos | `src/Baxy.Contracts/` | Protocolo `baxy.local.v1` |
| Proveedores | `src/Baxy.Providers.Windows/` | Efectos y lecturas reales sobre Windows |
| Mente | `src/baxy_mind/` | `mind.py` (el turno), `llm_server.py`, `answer_check.py`, voz |
| Pruebas | `tests/Baxy.*.Tests/`, `tests/test_*.py` | NUnit por proyecto; pytest para la mente |
| Scripts | `scripts/` | Arranque, compilación, empaquetado, voz y bancos (`scripts/renew/`) |

## Invariantes

No se re-derivan:

1. El catálogo tipado es la única fuente de operaciones. La mente propone, el kernel autoriza, el proveedor ejecuta.
2. Nada se afirma sin verificar.
3. Estados terminales honestos: un efecto ambiguo no reintentable es `failed` con `effectMayHaveOccurred`.
4. La confirmación se liga a la invocación exacta.
5. Cero respuestas visibles fijas: el modelo formula cada mensaje.
6. Local y privado: BAXY puede leer la web, pero no envía contenido de la persona.

Y dos reglas de diseño: **nada de código que nombre una aplicación** (mecanismos generales y datos en
`src/baxy_mind/data/`) y **cero código muerto** (si una pieza sustituye a otra, la otra se va).

## Validar

Sube sólo hasta el peldaño que el cambio justifica:

| Nivel | Cuándo | Comando |
|---|---|---|
| 1 | Tras editar | La prueba de lo que tocaste: `py -3.12 -m pytest tests/test_X.py -q` o `dotnet test tests/Baxy.Kernel.Tests -c Release --nologo` |
| 2 | Cambio de código integrado | `dotnet build Baxy.slnx -c Release -warnaserror` y `py -3.12 -m pytest -q tests` |
| 3 | Antes de fusionar | Las suites .NET de los proyectos tocados, pytest entero y `ruff check .` |
| 4 | Conducta del modelo o de la App | Los bancos de `scripts/renew/` (ver `docs/evaluacion.md`) |

Un arreglo empieza por una prueba que falla. Un skip no cuenta como pass. Di el comando y el resultado exactos.
Las pruebas en vivo y los bancos e2e manejan el escritorio real: no los lances en una sesión con trabajo abierto, y
cierra por PID lo que una prueba abra (nunca por nombre de proceso).

## Buscar y leer

- Ámbito por defecto: `src tests scripts main.py`. Busca con ripgrep acotado y lee sólo el rango que necesitas.
- No abras enteros `tests/data/*.jsonl` ni `src/Baxy.FieldUi/dist/`: mide antes con `git ls-tree -r -l HEAD -- ruta`.
- Salida corta primero: `pytest -q`, `dotnet ... -v:minimal`, `git status --short`, `git diff --stat`.
- La historia del proyecto (decisiones, mediciones, rechazos) está en `docs/construccion/`. Antes de abrir una línea
  de investigación, busca ahí: muchas cosas ya se midieron.

## Privacidad

Nunca escribas en el repositorio datos personales: rutas de usuario, peticiones reales, nombres, correos, claves,
capturas. Los bancos con peticiones reales viven fuera del repositorio; aquí sólo van cifras agregadas y huellas.

## Commits

Pequeños y por tema, con el área al principio (`Mente: …`, `App: …`, `Proveedores: …`, `Documentación: …`).
