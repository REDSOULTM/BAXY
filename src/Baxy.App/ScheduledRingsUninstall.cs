using System.IO;
using Baxy.Providers.Windows.External;
using Microsoft.Win32;

namespace Baxy.App;

/// <summary>
/// INS-1, for the BAXY a store installed. Steam and the itch app delete the folder themselves; no uninstaller of
/// BAXY's runs, so the alarms and reminders it set stayed in Windows' Task Scheduler and went on ringing with no BAXY.
/// Started with <see cref="Argument"/> alone, this executable removes them (the tasks its data root recorded,
/// <see cref="ScheduledRingsRemoval"/>) and ends: no instance of its own, no window, nothing else touched.
/// Steam runs it when the app is uninstalled (scripts/steam/installscript.vdf, «Run Process On Uninstall»,
/// https://partner.steamgames.com/doc/sdk/installscripts); the itch app has nothing to run then, so there it is a
/// command for the person (documentacion/itchio/EMPAQUETADO.md).
/// The rings stay when another BAXY on this PC keeps the same data (the one the installer registered, or the one with
/// its own setup): they are its alarms too.
/// </summary>
internal static class ScheduledRingsUninstall
{
    internal const string Argument = "--remove-scheduled-rings";

    /// <summary>The Task Scheduler refused: the store ignores it, a person running the command can read it.</summary>
    internal const int Refused = 1;

    // The entry Baxy.Installer writes for «Installed apps» (WindowsIntegration.Register).
    private const string InstallerKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\BAXY-App";

    internal static bool IsRequested(string[] arguments) => arguments.Length == 1 && arguments[0] == Argument;

    internal static int Run() => Run(
        MemoryOperationProtector.DataRootPath(),
        Path.GetDirectoryName(Environment.ProcessPath) ?? AppContext.BaseDirectory,
        OtherInstallations(),
        ScheduledRingsRemoval.RemoveAll);

    internal static int Run(string dataRoot, string ownFolder, IEnumerable<string> installations, Func<string, int> remove)
    {
        if (installations.Any(folder => Directory.Exists(folder) && !IsInside(ownFolder, folder)))
        {
            return 0;
        }

        try
        {
            remove(dataRoot);
            return 0;
        }
        catch (Exception refused) when (refused is IOException or UnauthorizedAccessException)
        {
            return Refused;
        }
    }

    private static bool IsInside(string path, string folder) =>
        (Path.TrimEndingDirectorySeparator(Path.GetFullPath(path)) + Path.DirectorySeparatorChar).StartsWith(
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(folder)) + Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase);

    private static List<string> OtherInstallations()
    {
        List<string> folders =
        [
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "BAXY"),
        ];
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(InstallerKey);
        if (key?.GetValue("InstallLocation") is string { Length: > 0 } registered && Path.IsPathFullyQualified(registered))
        {
            folders.Add(registered);
        }

        return folders;
    }
}
