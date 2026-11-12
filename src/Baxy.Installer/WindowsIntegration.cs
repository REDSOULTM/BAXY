using System.Runtime.InteropServices;
using System.Security;
using System.Security.Cryptography;
using System.Text;
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
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "BAXY"))
    {
        UsualRoot = InstallPaths.ForThisUser.Root,
    };

    /// <summary>The Task Scheduler BAXY's alarms and reminders are set in (INS-1); tests give one of their own.</summary>
    internal ITaskSchedulerHost Scheduler { get; init; } = new WindowsTaskSchedulerHost();

    /// <summary>The usual installation folder, whose BAXY uses the same data wherever «Installed apps» points; tests
    /// leave it out, or give one of their own.</summary>
    internal string? UsualRoot { get; init; }
}

/// <summary>The Start menu entry, «Installed apps» and the copy of this installer that uninstalls.</summary>
internal static class WindowsIntegration
{
    internal const string InstallerName = "BAXY-Instalador.exe";

    /// <summary>The App's own Run value (src/Baxy.App/WindowsAutostartRegistration.cs).</summary>
    internal const string AutostartValue = "BAXY";

    /// <summary>
    /// COX-1: what this installation replaced of another BAXY's, kept in its own «Installed apps» entry (programs may keep
    /// values of their own there, as Inno Setup does with «Inno Setup: App Path») so the uninstall gives it back. The
    /// Run command is kept by the App, which is what writes the Run value (src/Baxy.App/WindowsAutostartRegistration.cs);
    /// the Start-menu shortcut by <see cref="Register"/>, byte for byte, with the file it starts.
    /// </summary>
    internal const string ReplacedAutostartValue = "ReplacedAutostart";

    private const string Publisher = "REDSOULTM";

    private const string ReplacedLinkValue = "ReplacedStartLink";
    private const string ReplacedLinkTargetValue = "ReplacedStartLinkTarget";

    /// <summary>
    /// The last step of installing, with BAXY's files already in place: the copy of this installer that uninstalls, the
    /// agreement, the entry of «Installed apps» and the Start-menu shortcut. The entry goes before the shortcut, so a
    /// BAXY whose shortcut Windows refused can still be removed from Windows. What Windows refuses comes out as
    /// <see cref="NotRegisteredException"/>: BAXY is installed, and this step can be run again alone (INS-5).
    /// UNI2 (VIVO11): each installation owns only what points at its own folder. The first one takes «BAXY» (the main
    /// entry and shortcut); one installed with --dir in another folder while that one is there gets an entry and a
    /// shortcut of its own, told apart by its folder (<see cref="EntryFor"/>), instead of taking the other's.
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
            string entry = EntryFor(paths, places);
            bool main = string.Equals(entry, places.UninstallKey, StringComparison.OrdinalIgnoreCase);
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(entry))
            {
                key.SetValue("DisplayName", main ? "BAXY" : $"BAXY ({paths.Root})");
                key.SetValue("DisplayVersion", version);
                key.SetValue("Publisher", Publisher);
                key.SetValue("InstallLocation", paths.Root);
                key.SetValue("DisplayIcon", paths.App);
                key.SetValue("UninstallString", $"\"{installer}\" --uninstall");
                key.SetValue("QuietUninstallString", $"\"{installer}\" --uninstall --quiet");
                key.SetValue("URLInfoAbout", "https://github.com/REDSOULTM/BAXY");
                key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                key.SetValue("EstimatedSize", (int)(installedBytes / 1024), RegistryValueKind.DWord);
                if (main)
                {
                    KeepReplacedLink(key, paths, places);
                }
            }

            ShellLink.Write(main ? places.Link : SideLink(paths, places), paths.App, "BAXY");
        }
        catch (Exception refused) when (refused is IOException or UnauthorizedAccessException or SecurityException or COMException)
        {
            throw new NotRegisteredException($"BAXY is in {paths.Root}, but Windows refused its registration: {refused.Message}", refused);
        }
    }

    /// <summary>
    /// COX-1: a «BAXY» shortcut that starts another installation (the other BAXY's setup made it) is kept before this one
    /// takes its name: the person looks for «BAXY» and gets the BAXY just installed, and the uninstall puts the other's
    /// back. On an update run of this installer the shortcut is this BAXY's own and what was kept stays as it was.
    /// </summary>
    private static void KeepReplacedLink(RegistryKey key, InstallPaths paths, WindowsPlaces places)
    {
        // One whose target cannot be read is not known to be this BAXY's: it is kept too, with no target to check. UNI2:
        // one whose target is gone would never come back (RemoveEntries), so it does not take the place of what was kept.
        if (File.Exists(places.Link) && ShellLink.Target(places.Link) is var target
            && (target is null || (!IsInside(target, paths.Root) && File.Exists(target))))
        {
            key.SetValue(ReplacedLinkValue, File.ReadAllBytes(places.Link), RegistryValueKind.Binary);
            key.SetValue(ReplacedLinkTargetValue, target ?? string.Empty);
        }
    }

    private static bool IsInside(string path, string root) =>
        path.StartsWith(Path.TrimEndingDirectorySeparator(root) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);

    private static bool SameFolder(string one, string other) =>
        string.Equals(Path.TrimEndingDirectorySeparator(one), Path.TrimEndingDirectorySeparator(other), StringComparison.OrdinalIgnoreCase);

    /// <summary>
    /// UNI2: the «Installed apps» entry of <paramref name="paths"/>. The one that names its folder already (an update);
    /// else the main one when it is free (none, or its folder holds no BAXY any more: what it kept of another BAXY stays
    /// in it); else one of its own beside the main one, named after its folder, as Windows asks of instances installed
    /// side by side (<see cref="InstalledBaxyEntries"/>). Blind review of UNI2: a folder on a drive that is not there now
    /// (a USB or network drive, a locked volume) is not gone, and its entry is not taken. A main entry an installer
    /// before this fix let a copy take from
    /// this installation (it kept this one's shortcut as replaced) is given back, and the copy gets its own
    /// (<see cref="MoveAside"/>).
    /// </summary>
    private static string EntryFor(InstallPaths paths, WindowsPlaces places)
    {
        if (InstalledBaxyEntries.All(places.UninstallKey).FirstOrDefault(entry => SameFolder(entry.Root, paths.Root)) is { } own)
        {
            return own.Key;
        }

        if (RegisteredRoot(places) is not { } other || IsGone(other))
        {
            return places.UninstallKey;
        }

        bool takenFromThisOne;
        using (RegistryKey? main = Registry.CurrentUser.OpenSubKey(places.UninstallKey))
        {
            takenFromThisOne = main?.GetValue(ReplacedLinkTargetValue) is string taken && IsInside(taken, paths.Root);
        }

        if (takenFromThisOne)
        {
            MoveAside(places, new InstallPaths(Path.TrimEndingDirectorySeparator(Path.GetFullPath(other))));
            return places.UninstallKey;
        }

        return SideEntry(places, paths.Root);
    }

    private static bool IsGone(string root) =>
        Path.GetPathRoot(root) is { Length: > 0 } drive && Directory.Exists(drive) && !Directory.Exists(root);

    private static string SideEntry(WindowsPlaces places, string root) => places.UninstallKey + "-" + FolderId(root);

    /// <summary>Eight hex digits of the folder's path: the same folder always gets the same name.</summary>
    private static string FolderId(string root) =>
        Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)).ToUpperInvariant())))[..8];

    /// <summary>
    /// UNI2: the repair of a main entry a copy (<paramref name="other"/>) took before this fix. The copy's values go to
    /// an entry of its own, with its own shortcut; what the main entry kept as «replaced» stays with the installation
    /// it belongs to: the shortcut it kept was the one this installation had (so it goes), and the Run value it kept
    /// stays with whichever of the two Windows starts at sign-in.
    /// UNI3 (VIVOU2): the copy's own uninstaller is the installer before UNI2, which knows neither the entry nor the
    /// shortcut this repair gives it (removing the copy left both behind). This installer takes its place, as
    /// <see cref="Register"/> does with its own, so «Installed apps» removes them with the copy. Should Windows refuse
    /// the copy, what the old one leaves is forgotten the next time an installer starts (<see cref="ForgetGone"/>).
    /// Blind review of UNI3: it is copied beside it and then put in its place, so a copy cut short (a full disk) never
    /// leaves a broken uninstaller where the old one was.
    /// </summary>
    private static void MoveAside(WindowsPlaces places, InstallPaths other)
    {
        string uninstaller = Path.Combine(other.Root, InstallerName);
        string coming = uninstaller + ".new";
        try
        {
            if (!string.Equals(Path.GetFullPath(Environment.ProcessPath!), uninstaller, StringComparison.OrdinalIgnoreCase))
            {
                File.Copy(Environment.ProcessPath!, coming, overwrite: true);
                File.Move(coming, uninstaller, overwrite: true);
            }
        }
        catch (Exception refused) when (refused is IOException or UnauthorizedAccessException)
        {
            Program.Log($"the uninstaller of {other.Root} stays the one it had: {refused.Message}");
            try
            {
                File.Delete(coming);
            }
            catch (Exception left) when (left is IOException or UnauthorizedAccessException)
            {
                Program.Log(left.ToString());
            }
        }

        bool runStartsOther;
        using (RegistryKey? run = Registry.CurrentUser.OpenSubKey(places.RunKey))
        {
            runStartsOther = run?.GetValue(AutostartValue) is string command
                && command.Contains(other.Root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
        }

        // Blind review of UNI2: what tells this repair apart (the kept shortcut) goes last, so one that Windows stopped
        // halfway is done again, the same way, when this step is tried again.
        using RegistryKey main = Registry.CurrentUser.CreateSubKey(places.UninstallKey);
        using (RegistryKey aside = Registry.CurrentUser.CreateSubKey(SideEntry(places, other.Root)))
        {
            foreach (string name in main.GetValueNames()
                .Where(name => name is not (ReplacedLinkValue or ReplacedLinkTargetValue) && (runStartsOther || name != ReplacedAutostartValue)))
            {
                if (main.GetValue(name) is { } value)
                {
                    aside.SetValue(name, value, main.GetValueKind(name));
                }
            }

            aside.SetValue("DisplayName", $"BAXY ({other.Root})");
            aside.SetValue("UninstallString", $"\"{uninstaller}\" --uninstall");
            aside.SetValue("QuietUninstallString", $"\"{uninstaller}\" --uninstall --quiet");
        }

        if (File.Exists(places.Link) && ShellLink.Target(places.Link) is { } linked && IsInside(linked, other.Root))
        {
            ShellLink.Write(SideLink(other, places), other.App, "BAXY");
            File.Delete(places.Link);
        }

        if (runStartsOther)
        {
            main.DeleteValue(ReplacedAutostartValue, throwOnMissingValue: false);
        }

        main.DeleteValue(ReplacedLinkTargetValue, throwOnMissingValue: false);
        main.DeleteValue(ReplacedLinkValue, throwOnMissingValue: false);
    }

    /// <summary>
    /// UNI2: the Start-menu shortcut of an installation that is not the main one: «BAXY (folder)», the one it already has
    /// on an update, and with the folder's id too when another's has that name.
    /// </summary>
    private static string SideLink(InstallPaths paths, WindowsPlaces places)
    {
        if (SideLinks(places).FirstOrDefault(link => ShellLink.Target(link) is { } target && IsInside(target, paths.Root)) is { } own)
        {
            return own;
        }

        string start = Path.GetDirectoryName(places.Link)!;
        string plain = Path.Combine(start, $"BAXY ({Path.GetFileName(paths.Root)}).lnk");
        return File.Exists(plain) ? Path.Combine(start, $"BAXY ({Path.GetFileName(paths.Root)} {FolderId(paths.Root)}).lnk") : plain;
    }

    private static string[] SideLinks(WindowsPlaces places) =>
        Path.GetDirectoryName(places.Link) is { } start && Directory.Exists(start) ? Directory.GetFiles(start, "BAXY (*).lnk") : [];

    /// <summary>
    /// UNI3 (VIVOU2): what «Installed apps» and Start keep of an installation beside the main one that is gone, as an
    /// uninstaller before UNI2 left it (it deleted the folder and knew neither the entry nor the shortcut the repair gave
    /// it). Every installer forgets it as it starts to install, update or uninstall, the way the uninstall would have
    /// (<see cref="RemoveEntries"/>). Only what is BAXY's by its values (<see cref="WrittenByThisInstaller"/>) and surely
    /// gone (<see cref="IsSurelyGone"/>); the main entry stays, for what it kept is the other BAXY's and
    /// <see cref="EntryFor"/> takes it again. Nothing here stops the installer: what Windows refuses stays, and is logged;
    /// blind review of UNI3: one entry or shortcut refused never keeps the others.
    /// </summary>
    internal static void ForgetGone(WindowsPlaces places) => Logged(() =>
    {
        string? main = RegisteredRoot(places);
        foreach (InstalledBaxyEntries.Entry entry in InstalledBaxyEntries.All(places.UninstallKey))
        {
            Logged(() =>
            {
                if (!string.Equals(entry.Key, places.UninstallKey, StringComparison.OrdinalIgnoreCase)
                    && (main is null || !SameFolder(main, entry.Root))
                    && WrittenByThisInstaller(entry)
                    && IsSurelyGone(new InstallPaths(entry.Root)))
                {
                    RemoveEntries(new InstallPaths(entry.Root), places);
                    Program.Log($"forgot {entry.Root}: «Installed apps» named it, and it is gone");
                }
            });
        }

        // A BAXY shortcut beside «BAXY» that starts an app in a folder surely gone, with no entry left to remove it.
        foreach (string link in SideLinks(places))
        {
            Logged(() =>
            {
                if (ShellLink.Target(link) is { } target && Path.IsPathFullyQualified(target)
                    && Path.GetDirectoryName(Path.GetDirectoryName(target)) is { Length: > 0 } root
                    && new InstallPaths(root) is var paths
                    && string.Equals(paths.App, Path.GetFullPath(target), StringComparison.OrdinalIgnoreCase)
                    && IsSurelyGone(paths))
                {
                    File.Delete(link);
                    Program.Log($"forgot {link}: it started {target}, which is gone");
                }
            });
        }
    });

    /// <summary>A step Windows may refuse, or a value of the registry that is no path (any program writes there).</summary>
    private static void Logged(Action step)
    {
        try
        {
            step();
        }
        catch (Exception refused) when (refused is IOException or UnauthorizedAccessException or SecurityException
            or ArgumentException or NotSupportedException)
        {
            Program.Log(refused.ToString());
        }
    }

    /// <summary>
    /// An entry this installer wrote (<see cref="Register"/>): its publisher, and an uninstaller in the folder it names.
    /// Any program of the person's writes in «Installed apps», so the key's name alone does not make it BAXY's.
    /// </summary>
    private static bool WrittenByThisInstaller(InstalledBaxyEntries.Entry entry)
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(entry.Key);
        return key?.GetValue("Publisher") is Publisher
            && ExecutableOf(key.GetValue("UninstallString") as string) is { } uninstaller
            && string.Equals(Path.GetFullPath(uninstaller), Path.Combine(entry.Root, InstallerName), StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// Neither BAXY's app nor its uninstaller is in the folder, and Windows said so: File.Exists says false too when it
    /// refuses to look (Microsoft Learn, File.Exists: «If the caller does not have sufficient permissions to read the
    /// specified file… the method returns false regardless of the existence of path»). Blind review of UNI3: only on a
    /// fixed drive that is ready; on a removable or network one (or a UNC path) the folder may be on another disk that
    /// had that letter, or on a server that is down, and comes back. Nor while BAXY may be beside it, halfway through a
    /// swap or an uninstall (its .old, .new or .removing-* folders): the next installer there brings it back or ends it.
    /// </summary>
    private static bool IsSurelyGone(InstallPaths paths) =>
        Path.GetPathRoot(paths.Root) is { Length: 3 } drive && drive[1] == Path.VolumeSeparatorChar
        && new DriveInfo(drive) is { DriveType: DriveType.Fixed, IsReady: true }
        && IsSurelyMissing(paths.App) && IsSurelyMissing(Path.Combine(paths.Root, InstallerName))
        && !Directory.Exists(paths.Previous) && !Directory.Exists(paths.Staging) && Removing(paths).Length == 0;

    private static bool IsSurelyMissing(string file)
    {
        try
        {
            File.GetAttributes(file);
            return false;
        }
        catch (Exception missing) when (missing is FileNotFoundException or DirectoryNotFoundException)
        {
            return true;
        }
        catch (Exception unknown) when (unknown is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    /// <summary>Whether an entry of «Installed apps» names <paramref name="root"/>.</summary>
    internal static bool IsRegistered(string root, WindowsPlaces places) =>
        InstalledBaxyEntries.All(places.UninstallKey).Any(entry => SameFolder(entry.Root, root));

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

    /// <summary>
    /// The other BAXY, which shares the data folder, is installed: its folder holds what its setup puts there (its
    /// stable setup, its versions or its «current» pointer, src/Baxy.Setup/CanonicalWindowsPaths.cs). UNI1 (REV8 U6):
    /// an empty folder with its name is not that BAXY, and no longer hides «delete your data» for ever.
    /// </summary>
    internal static bool ADifferentBaxyIsInstalled(WindowsPlaces? places = null)
    {
        string other = (places ?? WindowsPlaces.ForThisUser).OtherBaxy;
        return File.Exists(Path.Combine(other, "Baxy.Setup.exe"))
            || Directory.Exists(Path.Combine(other, "versions"))
            || File.Exists(Path.Combine(other, "current"));
    }

    /// <summary>
    /// The folder of another installed BAXY that uses the same data folder as <paramref name="paths"/>, or null when
    /// they are this installation's alone: the other BAXY (its own setup), the one «Installed apps» names when the one
    /// removed is a copy in another folder, or one in the usual folder. UNI1 (REV8 U1): the alarms that stay, «delete
    /// your data» and what the screen says all follow this one check, so a copy never deletes the data a BAXY still
    /// installed uses.
    /// </summary>
    /// <remarks>A copy installed with --dir elsewhere and never registered is not known to Windows, so it is not seen.
    /// UNI2: every installation «Installed apps» names counts, each with its own entry.</remarks>
    internal static string? DataSharedWith(InstallPaths paths, WindowsPlaces? places = null)
    {
        places ??= WindowsPlaces.ForThisUser;
        if (ADifferentBaxyIsInstalled(places))
        {
            return places.OtherBaxy;
        }

        string?[] others = [.. InstalledBaxyEntries.All(places.UninstallKey).Select(static entry => entry.Root), places.UsualRoot];
        return others.FirstOrDefault(other => other is not null && !SameFolder(other, paths.Root) && new InstallPaths(other).HoldsBaxy);
    }

    /// <summary>
    /// How many alarms and reminders uninstalling <paramref name="paths"/> takes out of Windows (INS-1): the ones BAXY
    /// recorded in its data (<see cref="ScheduledRingTasks.Recorded"/>, one ring script per task, in each data root of
    /// its data folder). None when another BAXY keeps using those data (<see cref="DataSharedWith"/>).
    /// </summary>
    internal static int RingsToRemove(InstallPaths paths, WindowsPlaces? places = null)
    {
        places ??= WindowsPlaces.ForThisUser;
        return DataSharedWith(paths, places) is null
            ? RingFolders(places).Sum(static folder => ScheduledRingTasks.Recorded(folder).Count)
            : 0;
    }

    /// <summary>
    /// COX-1: how many alarms and reminders stay in Windows because another BAXY shares the data folder, for the screen
    /// to name them (<see cref="Texts.UninstallBodyFor"/>). They are the data's, not one installation's: each ring is a
    /// task whose action runs powershell.exe on a script kept in the data folder (NativeScheduledNotificationBackend,
    /// Exec action), so none starts the exe this uninstall removes, and the other BAXY, reading the same folder, lists
    /// and cancels them as its own (NativeScheduledNotificationBackend.IsOwn).
    /// </summary>
    /// <remarks>It only informs: data Windows does not let it read count as none, and never stop the uninstall.</remarks>
    internal static int RingsKept(InstallPaths paths, WindowsPlaces? places = null)
    {
        places ??= WindowsPlaces.ForThisUser;
        try
        {
            return DataSharedWith(paths, places) is not null
                ? RingFolders(places).Sum(static folder => ScheduledRingTasks.Recorded(folder).Count)
                : 0;
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException)
        {
            Program.Log(unread.ToString());
            return 0;
        }
    }

    /// <summary>The notifications folder of every data root in BAXY's data (the product's is «1»).</summary>
    private static string[] RingFolders(WindowsPlaces places) =>
        Directory.Exists(places.Data)
            ? [.. Directory.GetDirectories(places.Data).Select(static root => Path.Combine(root, ScheduledRingTasks.FolderName))]
            : [];

    /// <summary>
    /// Everything the install and BAXY created, the window's uninstall and --uninstall --quiet alike: the folder, the Start
    /// menu entry, «Installed apps», BAXY's start with Windows, the alarms and reminders it set in the Task Scheduler
    /// (<see cref="RemoveRings"/>) and, when asked, its data. When the data cannot go (another BAXY uses them,
    /// <see cref="DataSharedWith"/>) nothing is removed, so a script never ends with half of what it asked for.
    /// </summary>
    /// <param name="held">The exe of the original that waits on this copy (--uninstall --quiet from the installed copy).
    /// Windows refuses to move the folder while it runs (W1: «Access denied» with the published single-file exe), so the
    /// folder is emptied around it and <see cref="DeleteHeld"/> takes it once the original ended, as Inno Setup does.</param>
    internal static void Uninstall(InstallPaths paths, bool deleteData, WindowsPlaces? places = null, string? held = null)
    {
        places ??= WindowsPlaces.ForThisUser;
        if (deleteData && DataSharedWith(paths, places) is { } other)
        {
            throw new InvalidOperationException($"the other BAXY in {other} keeps its data in {places.Data} too: they stay");
        }

        int kept = RingsKept(paths, places);
        if (held is null)
        {
            Remove(paths, places, deleteData);
        }
        else
        {
            // What cannot be deleted stops it before the entries go: «Installed apps» still offers to try again.
            EmptyAround(paths.Root, held);
            RemoveRings(paths, places);
            DeleteData(places, deleteData);
            RemoveEntries(paths, places);
            DeleteLeftovers(paths);
        }

        if (kept > 0)
        {
            Program.Log($"kept {kept} alarms and reminders: another BAXY uses the same data");
        }
    }

    /// <summary>
    /// UNI1 (REV8 U3): the data go after the alarms (their scripts are in the data, <see cref="RemoveRings"/>) and before
    /// the entries, so data that cannot be deleted stop the uninstall while «Installed apps» still offers to try again.
    /// </summary>
    private static void DeleteData(WindowsPlaces places, bool deleteData)
    {
        if (deleteData && Directory.Exists(places.Data))
        {
            InstallPaths.DeleteTree(places.Data);
        }
    }



    /// <summary>The exe <see cref="Uninstall"/> left for last, its mark and its folder, once the original that ran it ended.</summary>
    internal static void DeleteHeld(InstallPaths paths, string held)
    {
        try
        {
            File.Delete(held);
            File.Delete(Path.Combine(paths.Root, InstallPaths.MarkName));
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
    private static void Remove(InstallPaths paths, WindowsPlaces places, bool deleteData)
    {
        string leaving = MoveAway(paths);
        try
        {
            RemoveRings(paths, places);
            DeleteData(places, deleteData);
            RemoveEntries(paths, places);
        }
        catch (Exception failure) when (failure is IOException or UnauthorizedAccessException)
        {
            // Without this, «Installed apps» would point at an uninstaller that has just been moved away.
            if (Directory.Exists(leaving))
            {
                Directory.Move(leaving, paths.Root);
            }

            throw;
        }

        DeleteLeftovers(paths, leaving);
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

    /// <remarks>
    /// UNI2: only this installation's own entry goes (the one that names its folder, <see cref="InstalledBaxyEntries"/>),
    /// and only the shortcuts that start it: those of the other installations, and their entries, stay.
    /// COX-1: the shortcut and the Run value go only when they start this installation, and what they replaced of
    /// another BAXY comes back when what it starts is still there (Microsoft Learn, «Run and RunOnce Registry Keys»:
    /// Windows runs each value of Run at every sign-in, so one whose exe is gone would fail every time). A shortcut or a
    /// Run value the other BAXY wrote again after this one is its own and stays. UNI1 (REV8 U5): what was kept is read
    /// from the registry, where any program of the person's writes, so it goes back only when it starts the other BAXY.
    /// </remarks>
    private static void RemoveEntries(InstallPaths paths, WindowsPlaces places)
    {
        string? replacedCommand = null;
        byte[]? replacedLink = null;
        string? replacedTarget = null;
        string[] entries = [.. InstalledBaxyEntries.All(places.UninstallKey)
            .Where(entry => SameFolder(entry.Root, paths.Root))
            .Select(static entry => entry.Key)
            .OrderBy(entry => !string.Equals(entry, places.UninstallKey, StringComparison.OrdinalIgnoreCase))];
        if (entries.Length > 0)
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(entries[0]);
            replacedCommand = key?.GetValue(ReplacedAutostartValue) as string;
            replacedLink = key?.GetValue(ReplacedLinkValue) as byte[];
            replacedTarget = key?.GetValue(ReplacedLinkTargetValue) as string;
        }
        else
        {
            replacedCommand = TakeBackFromCopy(paths, places);
        }

        // «Installed apps» goes last: while something here fails, the uninstall can be run again and what was kept is there.
        using (RegistryKey? run = Registry.CurrentUser.OpenSubKey(places.RunKey, writable: true))
        {
            if (run?.GetValue(AutostartValue) is string command
                && command.Contains(paths.Root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                if (ExecutableOf(replacedCommand) is { } replacedExe && File.Exists(replacedExe) && IsInside(replacedExe, places.OtherBaxy))
                {
                    run.SetValue(AutostartValue, replacedCommand!);
                }
                else
                {
                    run.DeleteValue(AutostartValue);
                }
            }
        }

        // Only a shortcut known to start this installation goes; one that cannot be read may be another's.
        foreach (string link in SideLinks(places).Prepend(places.Link))
        {
            if (File.Exists(link) && ShellLink.Target(link) is { } linked && IsInside(linked, paths.Root))
            {
                File.Delete(link);
            }
        }

        // A kept shortcut whose target could not be read comes back as it was; one whose target is gone does not.
        if (!File.Exists(places.Link) && replacedLink is { Length: > 0 } && (replacedTarget is "" || File.Exists(replacedTarget)))
        {
            File.WriteAllBytes(places.Link, replacedLink);
        }

        foreach (string entry in entries)
        {
            Registry.CurrentUser.DeleteSubKeyTree(entry, throwOnMissingSubKey: false);
        }
    }

    /// <summary>
    /// Blind review of UNI2: an installation whose main entry a copy took before this fix, removed before it repaired
    /// it, takes back from that entry what it kept there: the Run value it replaced, when Windows still starts this
    /// one at sign-in, and the shortcut the copy kept, which was this one's own. Nothing when the entry did not take
    /// this one's place.
    /// </summary>
    private static string? TakeBackFromCopy(InstallPaths paths, WindowsPlaces places)
    {
        using RegistryKey? main = Registry.CurrentUser.OpenSubKey(places.UninstallKey, writable: true);
        if (main?.GetValue(ReplacedLinkTargetValue) is not string taken || !IsInside(taken, paths.Root))
        {
            return null;
        }

        string? command = null;
        using (RegistryKey? run = Registry.CurrentUser.OpenSubKey(places.RunKey))
        {
            if (run?.GetValue(AutostartValue) is string current
                && current.Contains(paths.Root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                command = main.GetValue(ReplacedAutostartValue) as string;
            }
        }

        if (command is not null)
        {
            main.DeleteValue(ReplacedAutostartValue, throwOnMissingValue: false);
        }

        main.DeleteValue(ReplacedLinkTargetValue, throwOnMissingValue: false);
        main.DeleteValue(ReplacedLinkValue, throwOnMissingValue: false);
        return command;
    }

    // The exe a Run command starts: the quoted path the App writes, or the command up to its first space.
    private static string? ExecutableOf(string? command)
    {
        string trimmed = command?.Trim() ?? string.Empty;
        string exe = trimmed.StartsWith('"')
            ? trimmed[1..Math.Max(1, trimmed.IndexOf('"', 1))]
            : trimmed.Split(' ', 2)[0];
        return Path.IsPathFullyQualified(exe) ? exe : null;
    }

    /// <summary>
    /// Everything in the folder but the exe that waits. Independent review of UNI1: the folder is marked as BAXY's first
    /// and the mark stays with the exe, so an uninstall stopped halfway, run again from that folder, takes that folder
    /// (<see cref="InstallPaths.ForUninstall"/>) and not the one «Installed apps» names.
    /// </summary>
    private static void EmptyAround(string root, string held)
    {
        if (!Directory.Exists(root))
        {
            return;
        }

        InstallPaths.MarkAsBaxys(root);
        string mark = Path.Combine(root, InstallPaths.MarkName);
        foreach (string entry in Directory.EnumerateFileSystemEntries(root))
        {
            if (string.Equals(Path.GetFullPath(entry), Path.GetFullPath(held), StringComparison.OrdinalIgnoreCase)
                || string.Equals(Path.GetFullPath(entry), mark, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (Directory.Exists(entry))
            {
                InstallPaths.DeleteTree(entry);
            }
            else
            {
                File.Delete(entry);
            }
        }
    }

    internal static void RemoveFolders(InstallPaths paths) => DeleteLeftovers(paths, MoveAway(paths));

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

    /// <param name="leaving">The folder this uninstall moved away: it goes whatever is in it.</param>
    private static void DeleteLeftovers(InstallPaths paths, string? leaving = null) =>
        DeleteAll([.. Removing(paths), paths.Staging, paths.Previous, paths.Downloads], leaving);

    private static void DeleteAll(IEnumerable<string> folders, string? leaving)
    {
        foreach (string folder in folders)
        {
            try
            {
                if (Directory.Exists(folder) && (string.Equals(folder, leaving, StringComparison.OrdinalIgnoreCase) || InstallPaths.IsBaxys(folder)))
                {
                    InstallPaths.DeleteTree(folder);
                }
                else if (Directory.Exists(folder))
                {
                    Program.Log($"left {folder}: it shares the name but holds nothing of BAXY's");
                }
            }
            catch (Exception left) when (left is IOException or UnauthorizedAccessException)
            {
                Program.Log(left.ToString());
            }
        }
    }
}
