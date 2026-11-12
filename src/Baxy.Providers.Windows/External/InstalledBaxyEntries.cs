using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// UNI2: the «Installed apps» entries of the BAXY the GitHub installer (src/Baxy.Installer) put on this PC, one per
/// installation folder. The first one is <see cref="MainKey"/>; one installed with --dir in another folder while that
/// one is there gets a key of its own beside it, named after its folder, as Windows asks of each instance installed
/// side by side (Microsoft Learn, «Authoring Multiple Instances with Instance Transforms»: each instance has its own
/// product code, and «registry keys should include the instance name in their path to prevent collisions»).
/// The installer, the App (the Run value it replaced) and the store's ring removal read them here. The installer compiles
/// this file as it is (Baxy.Installer.csproj), so it uses nothing else of the providers.
/// </summary>
public static class InstalledBaxyEntries
{
    /// <summary>The first installation's entry, under HKCU.</summary>
    public const string MainKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\BAXY-App";

    /// <summary>One entry: its key's path under HKCU and the folder it names (InstallLocation).</summary>
    public sealed record Entry(string Key, string Root);

    /// <summary>The main entry and the ones beside it named after it (<c>BAXY-App-…</c>) that name a full path.</summary>
    public static IReadOnlyList<Entry> All(string mainKey = MainKey)
    {
        string parent = Path.GetDirectoryName(mainKey)!;
        string name = Path.GetFileName(mainKey);
        using RegistryKey? uninstall = Registry.CurrentUser.OpenSubKey(parent);
        if (uninstall is null)
        {
            return [];
        }

        List<Entry> entries = [];
        foreach (string sub in uninstall.GetSubKeyNames()
            .Where(sub => string.Equals(sub, name, StringComparison.OrdinalIgnoreCase)
                || sub.StartsWith(name + "-", StringComparison.OrdinalIgnoreCase))
            .Order(StringComparer.OrdinalIgnoreCase))
        {
            using RegistryKey? key = uninstall.OpenSubKey(sub);
            // Any program of the person's writes here: a value that is not a path is no installation's.
            if (key?.GetValue("InstallLocation") is string { Length: > 0 } root && Path.IsPathFullyQualified(root)
                && !root.Contains('\0', StringComparison.Ordinal))
            {
                entries.Add(new Entry(parent + @"\" + sub, Path.TrimEndingDirectorySeparator(Path.GetFullPath(root))));
            }
        }

        return entries;
    }

    /// <summary>The entry of the installation <paramref name="file"/> is in (the innermost, should one folder be inside
    /// another), or null when none names its folder.</summary>
    public static Entry? Holding(string file, string mainKey = MainKey)
    {
        string full = Path.GetFullPath(file);
        return All(mainKey)
            .Where(entry => full.StartsWith(entry.Root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            .MaxBy(static entry => entry.Root.Length);
    }
}
