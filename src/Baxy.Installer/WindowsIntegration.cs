using Microsoft.Win32;

namespace Baxy.Installer;

/// <summary>The Start menu entry, «Installed apps» and the copy of this installer that uninstalls.</summary>
internal static class WindowsIntegration
{
    private const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\BAXY-App";
    private const string InstallerName = "BAXY-Instalador.exe";
    private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string AutostartValue = "BAXY";

    private static string LinkPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.Programs),
        "BAXY.lnk");

    internal static void Register(InstallPaths paths, string version, long installedBytes)
    {
        string installer = Path.Combine(paths.Root, InstallerName);
        File.Copy(Environment.ProcessPath!, installer, overwrite: true);
        string licenses = Path.Combine(paths.Root, "licenses");
        Directory.CreateDirectory(licenses);
        File.WriteAllText(Path.Combine(licenses, "BAXY-licencia-es.txt"), LicenseText("es"));
        File.WriteAllText(Path.Combine(licenses, "BAXY-license-en.txt"), LicenseText("en"));
        File.WriteAllText(Path.Combine(licenses, "Installer-fonts-OFL.txt"), Resource("Baxy.Installer.fonts.OFL.txt"));
        ShellLink.Write(LinkPath, paths.App, "BAXY");
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(UninstallKey);
        key.SetValue("DisplayName", "BAXY");
        key.SetValue("DisplayVersion", version);
        key.SetValue("Publisher", "REDSOULTM");
        key.SetValue("InstallLocation", paths.Root);
        key.SetValue("DisplayIcon", paths.App);
        key.SetValue("UninstallString", $"\"{installer}\" --uninstall");
        key.SetValue("URLInfoAbout", "https://github.com/REDSOULTM/BAXY");
        key.SetValue("NoModify", 1, RegistryValueKind.DWord);
        key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
        key.SetValue("EstimatedSize", (int)(installedBytes / 1024), RegistryValueKind.DWord);
    }

    internal static string LicenseText(string language) => Resource($"Baxy.Installer.license.{language}");

    private static string Resource(string name)
    {
        using Stream stream = typeof(WindowsIntegration).Assembly.GetManifestResourceStream(name)
            ?? throw new InvalidDataException($"{name} is not in this build");
        using StreamReader reader = new(stream);
        return reader.ReadToEnd();
    }

    /// <summary>A folder in use refuses the move and nothing has changed yet, so the person can close BAXY and try again.</summary>
    internal static void Remove(InstallPaths paths)
    {
        string leaving = MoveAway(paths);
        try
        {
            if (File.Exists(LinkPath))
            {
                File.Delete(LinkPath);
            }

            Registry.CurrentUser.DeleteSubKeyTree(UninstallKey, throwOnMissingSubKey: false);
            using RegistryKey? run = Registry.CurrentUser.OpenSubKey(RunKey, writable: true);
            if (run?.GetValue(AutostartValue) is string command && command.Contains(paths.Root, StringComparison.OrdinalIgnoreCase))
            {
                run.DeleteValue(AutostartValue);
            }
        }
        catch (Exception failure) when (failure is IOException or UnauthorizedAccessException)
        {
            // Without this, «Installed apps» would point at an uninstaller that has just been moved away.
            Directory.Move(leaving, paths.Root);
            throw;
        }

        DeleteLeftovers(paths);
    }

    internal static void RemoveFolders(InstallPaths paths)
    {
        MoveAway(paths);
        DeleteLeftovers(paths);
    }

    /// <summary>The other BAXY (the one with its own setup) keeps its data in the same folder as this one.</summary>
    internal static bool ADifferentBaxyIsInstalled() => Directory.Exists(Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Programs",
        "BAXY"));

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

    private static void DeleteLeftovers(InstallPaths paths)
    {
        string parent = Path.GetDirectoryName(paths.Root)!;
        string[] removing = Directory.Exists(parent)
            ? Directory.GetDirectories(parent, Path.GetFileName(paths.Root) + ".removing-*")
            : [];
        foreach (string folder in removing.Concat([paths.Staging, paths.Previous, paths.Downloads]))
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
