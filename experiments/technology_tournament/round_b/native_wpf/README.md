# BAXY Round B — WPF nativo

Tercera alternativa seria para el subsistema de interfaz. Conserva la
composición visual y el contrato de core, pero elimina HTML, JavaScript y
WebView2. El objetivo del corte es medir si una GUI Windows nativa evita red de
fondo, reduce RAM y mejora accesibilidad/lifecycle lo suficiente para compensar
el costo de mantener la vista en XAML.

```powershell
dotnet build BaxyNativeWpf.csproj -c Release
```
