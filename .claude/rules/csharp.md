---
paths:
  - "src/Baxy.*/**/*.cs"
  - "tests/Baxy.*/**/*.cs"
  - "**/*.csproj"
  - "Directory.Build.props"
  - "Directory.Packages.props"
---

# C# en BAXY

- .NET 10, `Nullable` y `TreatWarningsAsErrors` activos, analizadores `latest-recommended` con estilo en el
  build (`Directory.Build.props`). Un aviso se arregla; no se calla con `#pragma`, `NoWarn` ni `!`.
- `record` para modelos de valor inmutables, `sealed` para clases que no se heredan, modificadores de acceso
  explícitos. Sin `dynamic`.
- `async`/`await` hasta arriba; nada de `.Result`, `.Wait()` ni `async void` fuera de manejadores de eventos;
  `CancellationToken` en las APIs asíncronas públicas.
- Interfaces sólo en las costuras que de verdad se comparan (`documentacion/03_COSTURAS.md`); nunca una
  interfaz con un solo implementador «por si algún día».
- `Process.Start`, rutas y argumentos que vienen de la mente son entrada no confiable.
- Versiones de paquetes centralizadas en `Directory.Packages.props`. Pruebas NUnit (`Assert.That`) en el
  proyecto dueño, `dotnet test tests/Baxy.<Proyecto>.Tests -c Release --nologo -v:minimal`.
