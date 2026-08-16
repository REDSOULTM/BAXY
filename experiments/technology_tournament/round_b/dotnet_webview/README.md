# .NET + WebView2 integrated finalist

This WPF shell hosts the shared offline BAXY interface and owns the Native AOT
.NET core through a private UTF-8 stdin/stdout channel. The UI never chooses a
workspace: the trusted shell injects a LocalAppData root and the core enforces
it again.

Build the core, set `BAXY_ROUND_B_CORE` to its executable, then run:

```powershell
dotnet run -c Release
```

WebView2 navigation, downloads, permissions, popups, devtools and background
network features are denied for the slice. The round-B harness verifies actual
process connections rather than trusting those flags.
