namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// The folders whose files run by themselves when the person starts something: Windows runs the person's Startup and
/// the one for all users at sign-in, and PowerShell (Windows PowerShell 5.1 and PowerShell 7) runs the profiles in
/// Documents\WindowsPowerShell and Documents\PowerShell (Microsoft.PowerShell_profile.ps1, profile.ps1,
/// Microsoft.VSCode_profile.ps1, and the modules it loads from there) every time it opens without -NoProfile. They are
/// taken where Windows says they are (Documents redirected or in OneDrive too, and a folder not made yet), never from a
/// user name; the profiles for all users under $PSHOME are not writable without elevation. No file tool writes, edits,
/// creates, moves or copies there, whichever folder, subfolder or full path names it (an 8.3 alias such as STARTM~1 is
/// the same folder once Path.GetFullPath reads it); reading is unaffected. Revisión de fase 3: through folder home a
/// LowReversible file.write in AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup would run at the next
/// sign-in, and through folder documents one in WindowsPowerShell\profile.ps1 at the next PowerShell.
/// </summary>
internal static class AutostartArea
{
    internal static string[] DefaultRoots() =>
        RootsFrom(folder => Environment.GetFolderPath(folder, Environment.SpecialFolderOption.DoNotVerify));

    /// <summary>The roots where <paramref name="folderPath"/> says the special folders are; tests answer with temporary ones.</summary>
    internal static string[] RootsFrom(Func<Environment.SpecialFolder, string?> folderPath)
    {
        List<string> roots = [];
        foreach (Environment.SpecialFolder startup in new[] { Environment.SpecialFolder.Startup, Environment.SpecialFolder.CommonStartup })
        {
            if (FullyQualified(folderPath(startup)) is { } folder)
                roots.Add(folder);
        }
        if (FullyQualified(folderPath(Environment.SpecialFolder.MyDocuments)) is { } documents)
        {
            roots.Add(Path.Combine(documents, "WindowsPowerShell"));
            roots.Add(Path.Combine(documents, "PowerShell"));
        }
        return [.. roots];
    }

    private static string? FullyQualified(string? path) =>
        !string.IsNullOrWhiteSpace(path) && Path.IsPathFullyQualified(path) ? Path.GetFullPath(path) : null;

    /// <summary>The path is one of the roots or lies inside one.</summary>
    internal static bool Holds(IReadOnlyList<string> roots, string path) => BaxyPrivateArea.Holds(roots, path);
}
