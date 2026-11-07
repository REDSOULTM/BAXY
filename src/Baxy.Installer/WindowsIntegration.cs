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
}

/// <summary>The Start menu entry, «Installed apps» and the copy of this installer that uninstalls.</summary>
internal static class WindowsIntegration
{
    internal const string InstallerName = "BAXY-Instalador.exe";

    /// <summary>The App's own Run value (src/Baxy.App/WindowsAutostartRegistration.cs).</summary>
    internal const string AutostartValue = "BAXY";

    internal static void Register(InstallPaths paths, string version, long installedBytes, WindowsPlaces? places = null)
    {
        places ??= WindowsPlaces.ForThisUser;
        string installer = Path.Combine(paths.Root, InstallerName);
        File.Copy(Environment.ProcessPath!, installer, overwrite: true);
        string licenses = Path.Combine(paths.Root, "licenses");
        Directory.CreateDirectory(licenses);
        File.WriteAllText(Path.Combine(licenses, "BAXY-licencia-es.txt"), LicenseText("es"));
        File.WriteAllText(Path.Combine(licenses, "BAXY-license-en.txt"), LicenseText("en"));
        File.WriteAllText(Path.Combine(licenses, "Installer-fonts-OFL.txt"), Resource("Baxy.Installer.fonts.OFL.txt"));
        ShellLink.Write(places.Link, paths.App, "BAXY");
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(places.UninstallKey);
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

    /// <summary>The data are BAXY's alone unless the other BAXY, which shares their folder, is installed.</summary>
    internal static bool ADifferentBaxyIsInstalled(WindowsPlaces? places = null) =>
        Directory.Exists((places ?? WindowsPlaces.ForThisUser).OtherBaxy);

    /// <summary>
    /// Everything the install and BAXY created, the window's uninstall and --uninstall --quiet alike: the folder, the Start
    /// menu entry, «Installed apps», BAXY's start with Windows and, when asked, its data. When the data cannot go (the
    /// other BAXY shares them) nothing is removed, so a script never ends with half of what it asked for.
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

        bool ownsTheEntries = RegisteredRoot(places) is not { } registered
            || string.Equals(Path.TrimEndingDirectorySeparator(registered), paths.Root, StringComparison.OrdinalIgnoreCase);
        if (held is null)
        {
            Remove(paths, places, ownsTheEntries);
        }
        else
        {
            // What cannot be deleted stops it before the entries go: «Installed apps» still offers to try again.
            EmptyAround(paths.Root, held);
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
