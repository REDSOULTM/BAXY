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

    internal static bool IsRequested(string[] arguments) => arguments.Length == 1 && arguments[0] == Argument;

    internal static int Run() => Run(
        MemoryOperationProtector.DataRootPath(),
        Path.GetDirectoryName(Environment.ProcessPath) ?? AppContext.BaseDirectory,
        OtherInstallations(),
        ScheduledRingsRemoval.RemoveAll);

    internal static int Run(string dataRoot, string ownFolder, IEnumerable<string> installations, Func<string, int> remove)
    {
        if (installations.Any(folder => HoldsABaxy(folder) && !IsInside(ownFolder, folder)))
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

    /// <summary>
    /// UPD1 (REV10 m4): a BAXY is in the folder, not only its name: its app (an installation the installer registered) or
    /// what its own setup puts there (src/Baxy.Setup/CanonicalWindowsPaths.cs). An empty Programs\BAXY, or an old entry's
    /// folder with nothing of BAXY left, kept the alarms ringing with no BAXY. The installer's check since UNI1
    /// (WindowsIntegration.ADifferentBaxyIsInstalled and DataSharedWith).
    /// </summary>
    private static bool HoldsABaxy(string folder) =>
        File.Exists(Path.Combine(folder, "app", "Baxy.exe"))
        || File.Exists(Path.Combine(folder, "Baxy.Setup.exe"))
        || Directory.Exists(Path.Combine(folder, "versions"))
        || File.Exists(Path.Combine(folder, "current"));

    private static bool IsInside(string path, string folder) =>
        (Path.TrimEndingDirectorySeparator(Path.GetFullPath(path)) + Path.DirectorySeparatorChar).StartsWith(
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(folder)) + Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase);

    // UNI2: every installation the installer registered, each in its own entry (InstalledBaxyEntries).
    private static List<string> OtherInstallations() =>
    [
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "BAXY"),
        .. InstalledBaxyEntries.All().Select(static entry => entry.Root),
    ];
}
