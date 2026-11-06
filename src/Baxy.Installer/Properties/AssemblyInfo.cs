using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

[assembly: InternalsVisibleTo("Baxy.Installer.Tests")]

// It runs from Downloads or a temporary folder: no DLL of that folder takes the place of Windows' own.
[assembly: DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
