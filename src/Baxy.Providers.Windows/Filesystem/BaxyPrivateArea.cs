namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// BAXY's own state is not one of the person's files: its data root (the confirmation mode, the journal, the memory
/// store, the sessions), the rest of its folder under the local application data (traces, the System One switch, other
/// profiles) and its runtime. A file operation never reads, writes, edits, lists or trashes there, whichever folder or
/// full path names it; the working folder (the sandbox, inside the data root) is the provider's own and stays usable.
/// Renew al máximo (B-SYS-1): through the home folder a LowReversible file.write turned Bypass on.
/// </summary>
internal static class BaxyPrivateArea
{
    internal static string[] DefaultRoots()
    {
        List<string> roots = [];
        string localData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (!string.IsNullOrWhiteSpace(localData))
        {
            roots.Add(Path.Combine(localData, "BAXY"));
            roots.Add(Path.Combine(localData, "BAXYRuntime"));
        }
        string? dataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        if (!string.IsNullOrWhiteSpace(dataRoot) && Path.IsPathFullyQualified(dataRoot)) roots.Add(dataRoot);
        return [.. roots.Select(Path.GetFullPath)];
    }

    /// <summary>The path is one of the roots or lies inside one.</summary>
    internal static bool Holds(IEnumerable<string> roots, string path)
    {
        string full = Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        return roots.Any(root =>
        {
            string folder = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            return string.Equals(full, folder, StringComparison.OrdinalIgnoreCase)
                || full.StartsWith(folder + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
        });
    }
}
