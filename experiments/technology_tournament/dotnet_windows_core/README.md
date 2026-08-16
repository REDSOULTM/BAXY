# .NET/Windows core contender

Build and run with .NET 10:

```powershell
dotnet build -c Release
dotnet run -c Release --no-build -- --server
```

It uses only the .NET shared framework for the vertical cut. Framework-
dependent, self-contained single-file and Native AOT publications are measured
separately so packaging does not get hidden inside the core result.
