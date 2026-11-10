using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// INS-5: the last step, after BAXY's files are in place. When Windows refuses it, that is its own failure (BAXY is
/// installed), BAXY can already be removed from «Installed apps», and the step can be done again alone. Every place is a
/// temporary folder or a registry key of the test's own.
/// </summary>
[TestFixture]
internal sealed class RegistrationTests
{
    private string directory = string.Empty;
    private string keys = string.Empty;
    private WindowsPlaces places = null!;
    private InstallPaths paths = null!;

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
        Registry.CurrentUser.CreateSubKey(keys + @"\Uninstall").Dispose();
        paths = new InstallPaths(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.Combine(paths.Root, "app"));
        File.WriteAllText(paths.App, "the app");
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

        Directory.Delete(directory, recursive: true);
    }

    [Test]
    public void A_shortcut_Windows_refuses_is_a_registration_that_failed_with_BAXY_already_removable()
    {
        // The Start-menu folder cannot hold the shortcut: a file has its name.
        File.WriteAllText(Path.GetDirectoryName(places.Link)!, "not a folder");

        Assert.That(
            () => WindowsIntegration.Register(paths, "9.9.9", 1000, places),
            Throws.InstanceOf<NotRegisteredException>());

        Assert.That(WindowsIntegration.RegisteredRoot(places), Is.EqualTo(paths.Root), "the entry of «Installed apps»");
        Assert.That(File.Exists(Path.Combine(paths.Root, WindowsIntegration.InstallerName)), Is.True, "what that entry runs");
    }

    [Test]
    public void The_step_alone_finishes_once_Windows_lets_it()
    {
        string start = Path.GetDirectoryName(places.Link)!;
        File.WriteAllText(start, "not a folder");
        Assert.That(
            () => WindowsIntegration.Register(paths, "9.9.9", 1000, places),
            Throws.InstanceOf<NotRegisteredException>());
        File.Delete(start);
        Directory.CreateDirectory(start);

        WindowsIntegration.Register(paths, "9.9.9", 1000, places);

        Assert.That(File.Exists(places.Link), Is.True);
        Assert.That(File.ReadAllText(paths.App), Is.EqualTo("the app"), "BAXY's files are not touched again");
    }
}
