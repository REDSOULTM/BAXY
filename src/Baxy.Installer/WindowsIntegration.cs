using System.Runtime.InteropServices;
using System.Security;
using Baxy.Providers.Windows.External;
using Microsoft.Win32;

namespace Baxy.Installer;

/// <summary>Where the installer leaves its marks on Windows; tests point them at a folder and a registry key of their own.</summary>
internal sealed record WindowsPlaces(string Link, string UninstallKey, string RunKey, string Data, string OtherBaxy)
{
    internal static WindowsPlaces ForThisUser { get; } = new(
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "BAXY.lnk"),
        @"Software\Microsoft\Windows\CurrentVersion\Uninstall\BAXY-App",
        @"Software\Microsoft\Windows\CurrentVersion\Run",
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY"),
        // The other BAXY (the one with its own setup) keeps its data in the same folder as this one.
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "BAXY"));

    /// <summary>The Task Scheduler BAXY's alarms and reminders are set in (INS-1); tests give one of their own.</summary>
    internal ITaskSchedulerHost Scheduler { get; init; } = new WindowsTaskSchedulerHost();
}

/// <summary>The Start menu entry, «Installed apps» and the copy of this installer that uninstalls.</summary>
internal static class WindowsIntegration
{
    internal const string InstallerName = "BAXY-Instalador.exe";

    /// <summary>The App's own Run value (src/Baxy.App/WindowsAutostartRegistration.cs).</summary>
    internal const string AutostartValue = "BAXY";

    /// <summary>
    /// The last step of installing, with BAXY's files already in place: the copy of this installer that uninstalls, the
    /// agreement, the entry of «Installed apps» and the Start-menu shortcut. The entry goes before the shortcut, so a
    /// BAXY whose shortcut Windows refused can still be removed from Windows. What Windows refuses comes out as
    /// <see cref="NotRegisteredException"/>: BAXY is installed, and this step can be run again alone (INS-5).
    /// </summary>
    internal static void Register(InstallPaths paths, string version, long installedBytes, WindowsPlaces? places = null)
    {
        places ??= WindowsPlaces.ForThisUser;
        try
        {
            string installer = Path.Combine(paths.Root, InstallerName);
            File.Copy(Environment.ProcessPath!, installer, overwrite: true);
            string licenses = Path.Combine(paths.Root, "licenses");
            Directory.CreateDirectory(licenses);
            File.WriteAllText(Path.Combine(licenses, "BAXY-licencia-es.txt"), LicenseText("es"));
            File.WriteAllText(Path.Combine(licenses, "BAXY-license-en.txt"), LicenseText("en"));
            File.WriteAllText(Path.Combine(licenses, "Installer-fonts-OFL.txt"), Resource("Baxy.Installer.fonts.OFL.txt"));
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(places.UninstallKey))
            {
                key.SetValue("DisplayName", "BAXY");
                key.SetValue("DisplayVersion", version);
                key.SetValue("Publisher", "REDSOULTM");
                key.SetValue("InstallLocation", paths.Root);
                key.SetValue("DisplayIcon", paths.App);
                key.SetValue("UninstallString", $"\"{installer}\" --uninstall");
                key.SetValue("QuietUninstallString", $"\"{installer}\" --uninstall --quiet");
                key.SetValue("URLInfoAbout", "https://github.com/REDSOULTM/BAXY");
                key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                key.SetValue("EstimatedSize", (int)(installedBytes / 1024), RegistryValueKind.DWord);
            }

            ShellLink.Write(places.Link, paths.App, "BAXY");
        }
        catch (Exception refused) when (refused is IOException or UnauthorizedAccessException or SecurityException or COMException)
        {
            throw new NotRegisteredException($"BAXY is in {paths.Root}, but Windows refused its registration: {refused.Message}", refused);
        }
    }

    /// <summary>The folder «Installed apps» names for this BAXY (it was installed with --dir or in the usual one).</summary>
    internal static string? RegisteredRoot(WindowsPlaces places)
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(places.UninstallKey);
        return key?.GetValue("InstallLocation") as string is { Length: > 0 } root && Path.IsPathFullyQualified(root) ? root : null;
    }

    internal static string LicenseText(string language) => Resource($"Baxy.Installer.license.{language}");

    private static string Resource(string name)
    {
        using Stream stream = typeof(WindowsIntegration).Assembly.GetManifestResourceStream(name)
            ?? throw new InvalidDataException($"{name} is not in this build");
        using StreamReader reader = new(stream);
        return reader.ReadToEnd();
    }

    /// <summary>What «keep your data» leaves on the disk (INS-9): every file under the data folder; links are not followed.</summary>
    internal static long DataBytes(WindowsPlaces? places = null)
    {
        DirectoryInfo data = new((places ?? WindowsPlaces.ForThisUser).Data);
        if (!data.Exists)
        {
            return 0;
        }

        EnumerationOptions whole = new()
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
        };
        return data.EnumerateFiles("*", whole).Sum(file => file.Length);
    }

    /// <summary>The data are BAXY's alone unless the other BAXY, which shares their folder, is installed.</summary>
    internal static bool ADifferentBaxyIsInstalled(WindowsPlaces? places = null) =>
        Directory.Exists((places ?? WindowsPlaces.ForThisUser).OtherBaxy);

    /// <summary>
    /// How many alarms and reminders uninstalling <paramref name="paths"/> takes out of Windows (INS-1): the ones BAXY
    /// recorded in its data (<see cref="ScheduledRingTasks.Recorded"/>, one ring script per task, in each data root of
    /// its data folder). None when another BAXY keeps using those data: the other BAXY that shares the folder, or the
    /// one «Installed apps» names when a copy in another folder is removed.
    /// </summary>
    internal static int RingsToRemove(InstallPaths paths, WindowsPlaces? places = null)
    {
        places ??= WindowsPlaces.ForThisUser;
        return OwnsTheEntries(paths, places) && !ADifferentBaxyIsInstalled(places)
            ? RingFolders(places).Sum(static folder => ScheduledRingTasks.Recorded(folder).Count)
            : 0;
    }

    private static bool OwnsTheEntries(InstallPaths paths, WindowsPlaces places) =>
        RegisteredRoot(places) is not { } registered
        || string.Equals(Path.TrimEndingDirectorySeparator(registered), paths.Root, StringComparison.OrdinalIgnoreCase);

    /// <summary>The notifications folder of every data root in BAXY's data (the product's is «1»).</summary>
    private static string[] RingFolders(WindowsPlaces places) =>
        Directory.Exists(places.Data)
            ? [.. Directory.GetDirectories(places.Data).Select(static root => Path.Combine(root, ScheduledRingTasks.FolderName))]
            : [];

    /// <summary>
    /// Everything the install and BAXY created, the window's uninstall and --uninstall --quiet alike: the folder, the Start
    /// menu entry, «Installed apps», BAXY's start with Windows, the alarms and reminders it set in the Task Scheduler
    /// (<see cref="RemoveRings"/>) and, when asked, its data. When the data cannot go (the other BAXY shares them)
    /// nothing is removed, so a script never ends with half of what it asked for.
    /// </summary>
    /// <param name="held">The exe of the original that waits on this copy (--uninstall --quiet from the installed copy).
    /// Windows refuses to move the folder while it runs (W1: «Access denied» with the published single-file exe), so the
    /// folder is emptied around it and <see cref="DeleteHeld"/> takes it once the original ended, as Inno Setup does.</param>
    internal static void Uninstall(InstallPaths paths, bool deleteData, WindowsPlaces? places = null, string? held = null)
    {
        places ??= WindowsPlaces.ForThisUser;
        if (deleteData && ADifferentBaxyIsInstalled(places))
        {
            throw new InvalidOperationException($"the other BAXY in {places.OtherBaxy} keeps its data in {places.Data} too: they stay");
        }

        bool ownsTheEntries = OwnsTheEntries(paths, places);
        if (held is null)
        {
            Remove(paths, places, ownsTheEntries);
        }
        else
        {
            // What cannot be deleted stops it before the entries go: «Installed apps» still offers to try again.
            EmptyAround(paths.Root, held);
            RemoveRings(paths, places);
            RemoveEntries(paths, places, ownsTheEntries);
            DeleteLeftovers(paths);
        }

        if (deleteData && Directory.Exists(places.Data))
        {
            Directory.Delete(places.Data, recursive: true);
        }
    }

    /// <summary>The exe <see cref="Uninstall"/> left for last, and its folder, once the original that ran it ended.</summary>
    internal static void DeleteHeld(InstallPaths paths, string held)
    {
        try
        {
            File.Delete(held);
            if (Directory.Exists(paths.Root) && !Directory.EnumerateFileSystemEntries(paths.Root).Any())
            {
                Directory.Delete(paths.Root);
            }
        }
        catch (Exception left) when (left is IOException or UnauthorizedAccessException)
        {
            Program.Log(left.ToString());
        }
    }

    /// <summary>A folder in use refuses the move and nothing has changed yet, so the person can close BAXY and try again.</summary>
    private static void Remove(InstallPaths paths, WindowsPlaces places, bool ownsTheEntries)
    {
        string leaving = MoveAway(paths);
        try
        {
            RemoveRings(paths, places);
            RemoveEntries(paths, places, ownsTheEntries);
        }
        catch (Exception failure) when (failure is IOException or UnauthorizedAccessException)
        {
            // Without this, «Installed apps» would point at an uninstaller that has just been moved away.
            Directory.Move(leaving, paths.Root);
            throw;
        }

        DeleteLeftovers(paths);
    }

    /// <summary>
    /// INS-1: the alarms and reminders BAXY set are tasks of Windows' Task Scheduler that ring by themselves, with a
    /// script kept in BAXY's data, so they went on ringing on a PC with no BAXY (kept data) or started a PowerShell
    /// against a script that was gone (deleted data), every day or every hour. They go with BAXY in both cases: nothing
    /// sets them again when BAXY is installed anew (the scheduler is where it reads them from), and the screen says so
    /// (<see cref="Texts.UninstallBodyFor"/>). Only the tasks BAXY recorded are removed, by their exact name
    /// (<see cref="ScheduledRingTasks"/>); the scheduler is not opened when there is none.
    /// A scheduler that refuses stops the uninstall before the entries go, as a folder in use does: «Installed apps»
    /// still offers it, and the person is not told BAXY is gone with its alarms left ringing.
    /// </summary>
    private static void RemoveRings(InstallPaths paths, WindowsPlaces places)
    {
        if (RingsToRemove(paths, places) == 0)
        {
            return;
        }

        try
        {
            int removed = RingFolders(places).Sum(folder => ScheduledRingTasks.RemoveAll(places.Scheduler, folder));
            Program.Log($"removed {removed} alarms and reminders from the Task Scheduler");
        }
        catch (TaskSchedulerHostException refused)
        {
            throw new IOException($"the Task Scheduler did not remove BAXY's alarms and reminders ({refused.Message})", refused);
        }
    }

    /// <param name="ownsTheEntries">False when «Installed apps» names another folder: its Start menu entry and its
    /// uninstall entry belong to that installation and stay.</param>
    private static void RemoveEntries(InstallPaths paths, WindowsPlaces places, bool ownsTheEntries)
    {
        if (ownsTheEntries)
        {
            if (File.Exists(places.Link))
            {
                File.Delete(places.Link);
            }

            Registry.CurrentUser.DeleteSubKeyTree(places.UninstallKey, throwOnMissingSubKey: false);
        }

        using RegistryKey? run = Registry.CurrentUser.OpenSubKey(places.RunKey, writable: true);
        if (run?.GetValue(AutostartValue) is string command
            && command.Contains(paths.Root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        {
            run.DeleteValue(AutostartValue);
        }
    }

    private static void EmptyAround(string root, string held)
    {
        if (!Directory.Exists(root))
        {
            return;
        }

        foreach (string entry in Directory.EnumerateFileSystemEntries(root))
        {
            if (string.Equals(Path.GetFullPath(entry), Path.GetFullPath(held), StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (Directory.Exists(entry))
            {
                Directory.Delete(entry, recursive: true);
            }
            else
            {
                File.Delete(entry);
            }
        }
    }

    internal static void RemoveFolders(InstallPaths paths)
    {
        MoveAway(paths);
        DeleteLeftovers(paths);
    }

    /// <summary>Under a name of its own: a folder an earlier removal could not finish deleting never blocks this one.</summary>
    private static string MoveAway(InstallPaths paths)
    {
        string leaving = $"{paths.Root}.removing-{Guid.NewGuid():N}";
        if (Directory.Exists(paths.Root))
        {
            Directory.Move(paths.Root, leaving);
        }

        return leaving;
    }

    private static string[] Removing(InstallPaths paths)
    {
        string parent = Path.GetDirectoryName(paths.Root)!;
        return Directory.Exists(parent) ? Directory.GetDirectories(parent, Path.GetFileName(paths.Root) + ".removing-*") : [];
    }

    private static void DeleteLeftovers(InstallPaths paths) =>
        DeleteAll([.. Removing(paths), paths.Staging, paths.Previous, paths.Downloads]);

    private static void DeleteAll(IEnumerable<string> folders)
    {
        foreach (string folder in folders)
        {
            try
            {
                if (Directory.Exists(folder))
                {
                    Directory.Delete(folder, recursive: true);
                }
            }
            catch (Exception left) when (left is IOException or UnauthorizedAccessException)
            {
                Program.Log(left.ToString());
            }
        }
    }
}
