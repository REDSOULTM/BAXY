using System.Diagnostics;
using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// UNI1 (blind review REV8, U3/U4/U5): a link inside the data left the uninstall half done with no way to try again,
/// folders beside BAXY's that only share its name were deleted without knowing they are BAXY's, and «what I replaced»
/// went back to Run\BAXY whatever it started. Every folder and registry key here is the test's own.
/// </summary>
[TestFixture]
internal sealed class UninstallLeftoversTests
{
    private string directory = string.Empty;
    private string keys = string.Empty;
    private WindowsPlaces places = null!;
    private InstallPaths registered = null!;
    private string memory = string.Empty;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
        keys = @"Software\BAXY-Installer-Tests\" + Path.GetRandomFileName();
        places = new WindowsPlaces(
            Path.Combine(directory, "Start", "BAXY.lnk"),
            keys + @"\Uninstall\BAXY-App",
            keys + @"\Run",
            Path.Combine(directory, "data"),
            Path.Combine(directory, "other-baxy"));
        Directory.CreateDirectory(Path.GetDirectoryName(places.Link)!);
        Registry.CurrentUser.CreateSubKey(keys + @"\Uninstall").Dispose();

        registered = new InstallPaths(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.GetDirectoryName(registered.App)!);
        File.WriteAllText(registered.App, "the app");
        WindowsIntegration.Register(registered, "1.3.4", 1000, places);
        memory = Path.Combine(places.Data, "1", "memory.db");
        Directory.CreateDirectory(Path.GetDirectoryName(memory)!);
        File.WriteAllText(memory, "what BAXY remembers");
    }

    [TearDown]
    public void TearDown()
    {
        Registry.CurrentUser.DeleteSubKeyTree(keys, throwOnMissingSubKey: false);
        string parent = Path.GetDirectoryName(keys)!;
        bool empty;
        using (RegistryKey? tests = Registry.CurrentUser.OpenSubKey(parent))
        {
            empty = tests is { SubKeyCount: 0, ValueCount: 0 };
        }

        if (empty)
        {
            Registry.CurrentUser.DeleteSubKey(parent, throwOnMissingSubKey: false);
        }

        // .NET's recursive delete refuses a junction inside the tree: the links go first, as links.
        foreach (string link in Directory.EnumerateDirectories(directory, "*", SearchOption.AllDirectories)
            .Where(found => new DirectoryInfo(found).LinkTarget is not null).ToArray())
        {
            Directory.Delete(link);
        }

        Directory.Delete(directory, recursive: true);
    }

    // U3: a junction inside the data stopped «delete your data» with BAXY already out of «Installed apps».
    [Test]
    public void A_link_inside_the_data_goes_as_a_link_and_what_it_points_to_stays()
    {
        string outside = Path.Combine(directory, "outside");
        Directory.CreateDirectory(outside);
        string precious = Path.Combine(outside, "precious.txt");
        File.WriteAllText(precious, "the person's");
        Junction(Path.Combine(places.Data, "1", "link"), outside);
        Junction(Path.Combine(registered.Root, "link"), outside);

        WindowsIntegration.Uninstall(registered, deleteData: true, places);

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(places.Data), Is.False);
            Assert.That(Directory.Exists(registered.Root), Is.False);
            Assert.That(Directory.GetDirectories(directory, "BAXY-App.removing-*"), Is.Empty);
            Assert.That(File.Exists(precious), Is.True, "a link is never followed");
            Assert.That(WindowsIntegration.RegisteredRoot(places), Is.Null);
        });
    }

    // U3: data that cannot be deleted stop the uninstall before the entries go, so «Installed apps» can run it again.
    [Test]
    public void Data_that_cannot_go_leave_baxy_in_installed_apps_to_try_again()
    {
        using (new FileStream(memory, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            Assert.Catch<IOException>(() => WindowsIntegration.Uninstall(registered, deleteData: true, places));

            Assert.That(WindowsIntegration.RegisteredRoot(places), Is.EqualTo(registered.Root));
            Assert.That(File.Exists(registered.App), Is.True, "the folder is back where «Installed apps» points");
        }

        WindowsIntegration.Uninstall(InstallPaths.ForUninstall(registered.Root, places), deleteData: true, places);

        Assert.That(Directory.Exists(places.Data), Is.False);
        Assert.That(WindowsIntegration.RegisteredRoot(places), Is.Null);
    }

    // U4: a backup the person named BAXY-App.old, or any BAXY-App.removing-…, is not BAXY's for having that name.
    [Test]
    public void Folders_beside_that_only_share_the_name_stay()
    {
        string backup = Path.Combine(registered.Previous, "my-backup.txt");
        string removing = Path.Combine(registered.Root + ".removing-not-baxys", "something.txt");
        foreach (string file in new[] { backup, removing })
        {
            Directory.CreateDirectory(Path.GetDirectoryName(file)!);
            File.WriteAllText(file, "the person's");
        }

        WindowsIntegration.Uninstall(registered, deleteData: false, places);

        Assert.That(File.Exists(backup), Is.True);
        Assert.That(File.Exists(removing), Is.True);
        Assert.That(Directory.Exists(registered.Root), Is.False);
    }

    // What BAXY left beside its folder still goes: its mark, its app, or nothing at all.
    [Test]
    public void Baxys_own_folders_beside_still_go()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(new InstallPaths(registered.Previous).App)!);
        File.WriteAllText(new InstallPaths(registered.Previous).App, "the app before");
        InstallPaths.MarkAsBaxys(registered.Downloads);
        File.WriteAllText(Path.Combine(registered.Downloads, "part.001"), "x");
        Directory.CreateDirectory(registered.Root + ".removing-0123");

        WindowsIntegration.Uninstall(registered, deleteData: false, places);

        Assert.That(Directory.GetDirectories(directory, "BAXY-App.*"), Is.Empty);
    }

    // U5: «what I replaced» is read back from the registry, where any program of the person's writes; it goes back to
    // Run only when it starts the other BAXY.
    [Test]
    public void Only_the_other_baxys_start_goes_back_to_run()
    {
        string planted = $"\"{Environment.SystemDirectory}\\cmd.exe\" /c echo planted";
        SetReplaced(planted);

        WindowsIntegration.Uninstall(registered, deleteData: false, places);

        Assert.That(Run(), Is.Null);
    }

    [Test]
    public void The_other_baxys_start_still_goes_back_to_run()
    {
        string otherExe = Path.Combine(places.OtherBaxy, "versions", "1.1.1", "Baxy.exe");
        Directory.CreateDirectory(Path.GetDirectoryName(otherExe)!);
        File.WriteAllText(otherExe, "the other app");
        SetReplaced($"\"{otherExe}\" --from-windows-start");

        WindowsIntegration.Uninstall(registered, deleteData: false, places);

        Assert.That(Run(), Is.EqualTo($"\"{otherExe}\" --from-windows-start"));
    }

    private void SetReplaced(string command)
    {
        using (RegistryKey entry = Registry.CurrentUser.OpenSubKey(places.UninstallKey, writable: true)!)
        {
            entry.SetValue(WindowsIntegration.ReplacedAutostartValue, command);
        }

        using RegistryKey run = Registry.CurrentUser.CreateSubKey(places.RunKey);
        run.SetValue(WindowsIntegration.AutostartValue, $"\"{registered.App}\" --from-windows-start");
    }

    private string? Run()
    {
        using RegistryKey? run = Registry.CurrentUser.OpenSubKey(places.RunKey);
        return run?.GetValue(WindowsIntegration.AutostartValue) as string;
    }

    private static void Junction(string link, string target)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(link)!);
        using Process made = Process.Start(new ProcessStartInfo("cmd.exe", $"/d /c mklink /J \"{link}\" \"{target}\"")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
        })!;
        made.WaitForExit();
        Assert.That(made.ExitCode, Is.Zero, "mklink /J");
    }
}
