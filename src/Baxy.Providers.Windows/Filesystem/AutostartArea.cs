namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// The folders whose files Windows runs at sign-in: the person's Startup and the one for all users, where Windows says
/// they are (a redirected one too, and one not made yet). No file tool writes, edits, creates, moves or copies there,
/// whichever folder, subfolder or full path names it (an 8.3 alias such as STARTM~1 is the same folder once
/// Path.GetFullPath reads it); reading is unaffected. Revisión de fase 3: through folder home a LowReversible file.write
/// in AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup would run at the next sign-in.
/// </summary>
internal static class AutostartArea
{
    internal static string[] DefaultRoots() =>
    [
        .. new[] { Environment.SpecialFolder.Startup, Environment.SpecialFolder.CommonStartup }
            .Select(folder => Environment.GetFolderPath(folder, Environment.SpecialFolderOption.DoNotVerify))
            .Where(path => !string.IsNullOrWhiteSpace(path) && Path.IsPathFullyQualified(path))
            .Select(Path.GetFullPath),
    ];

    /// <summary>The path is one of the roots or lies inside one.</summary>
    internal static bool Holds(IReadOnlyList<string> roots, string path) => BaxyPrivateArea.Holds(roots, path);
}
