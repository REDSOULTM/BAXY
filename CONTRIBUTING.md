# Contribuir a BAXY

Gracias por el interés. BAXY es un proyecto pequeño con reglas claras; leerlas antes ahorra trabajo a todos.

## Antes de empezar

- Lee [docs/arquitectura.md](docs/arquitectura.md) y [docs/identidad.md](docs/identidad.md). Las decisiones de
  diseño no son preferencias: un cambio que las contradiga se discute primero en un issue.
- Para algo más grande que un arreglo pequeño, abre un issue y cuenta qué quieres cambiar y cómo lo vas a medir.
- Instala el entorno siguiendo [docs/instalacion.md](docs/instalacion.md).

## Las reglas del código

1. **El catálogo tipado es la única fuente de operaciones.** Una operación nueva se declara en
   `src/Baxy.Kernel/Operations/ProductCatalog.cs`, con su manejador, su proveedor y sus pruebas.
2. **Nada se afirma sin verificar.** Un proveedor comprueba el efecto y lo devuelve en el recibo. «Se envió el
   comando» no es éxito.
3. **Confirmación ligada a la invocación exacta** para lo destructivo, lo que envía algo o lo que cierra trabajo sin
   guardar.
4. **Sin frases fijas visibles.** Lo que lee o escucha la persona lo formula el modelo.
5. **Sin código que nombre una aplicación.** La cobertura sale de mecanismos generales (UI Automation, OCR, visión) y
   de datos en `src/baxy_mind/data/`.
6. **Privado y en local.** Nada que envíe contenido de la persona fuera del PC.
7. **Lo más ligero que cumpla**, y sin código muerto: si una pieza sustituye a otra, la otra se va.

## Flujo de trabajo

```powershell
git switch -c mi-cambio
# ... cambios ...
dotnet build Baxy.slnx -c Release -warnaserror       # sin avisos
dotnet test tests\Baxy.Kernel.Tests -c Release       # la suite .NET de lo que tocaste
py -3.12 -m pytest -q tests                           # pruebas de la mente
py -3.12 -m pip install --requirement requirements-quality.txt   # una vez: ruff
py -3.12 -m ruff check .                              # análisis estático de Python (ruff.toml)
```

- **Un arreglo empieza por una prueba que falla** y termina con la prueba en verde.
- Las pruebas de `tests/Baxy.Providers.Windows.Tests` marcadas como en vivo manejan el escritorio real: córrelas en
  una sesión sin trabajo abierto.
- Si cambias la interfaz (`src/Baxy.FieldUi`), compila con `pnpm install --frozen-lockfile` y `pnpm build`, y
  versiona `dist/`.
- Si tu cambio afecta a lo que BAXY decide o dice, mide con los bancos (`scripts/renew/`) y pon el antes y el después
  en el pull request. Ver [docs/evaluacion.md](docs/evaluacion.md).

## Pull requests

- Uno por tema, pequeño, con una descripción de qué cambia y cómo se comprobó (comando y resultado).
- Commits en español o inglés, en presente y con el área al principio (por ejemplo, `Mente: …`, `App: …`,
  `Proveedores: …`).
- **Nada de datos personales**: ni rutas de tu usuario, ni peticiones reales, ni capturas de tu escritorio, ni claves.

## Agentes de programación

Si trabajas con un agente (Claude Code, Codex u otro), [AGENTS.md](AGENTS.md) resume lo que necesita saber.

## Licencia

Al contribuir aceptas que tu aportación se publique bajo la [licencia MIT](LICENSE) del proyecto.
