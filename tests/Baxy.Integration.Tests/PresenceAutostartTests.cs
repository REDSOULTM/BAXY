using Baxy.App;
using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class PresenceAutostartTests
{
    [Test]
    public void HideToTrayUnlessTheTrayAsksToQuit()
    {
        Assert.Multiple(() =>
        {
            Assert.That(PresencePolicy.HideInsteadOfQuit(true, false), Is.True);
            Assert.That(PresencePolicy.HideInsteadOfQuit(true, true), Is.False);
            Assert.That(PresencePolicy.HideInsteadOfQuit(false, false), Is.False);
        });
    }

    [Test]
    public void RunKeyRoundTripsTheRunningExecutableWithTrayArgument()
    {
        string testKey = @"Software\BAXY\goal10-autostart-" + Guid.NewGuid().ToString("N");
        const string executable = @"C:\Program Files\BAXY\Baxy.exe";
        try
        {
            WindowsAutostart.EnsureRegistered(executable, testKey);
            string? stored = WindowsAutostart.ReadCommand(testKey);

            Assert.Multiple(() =>
            {
                Assert.That(WindowsAutostart.IsRegistered(executable, testKey), Is.True);
                Assert.That(stored, Is.EqualTo("\"" + executable + "\" --tray"));
                Assert.That(stored, Does.Contain(WindowsAutostart.TrayArgument));
            });

            WindowsAutostart.Unregister(testKey);
            Assert.That(WindowsAutostart.ReadCommand(testKey), Is.Null);
        }
        finally
        {
            Registry.CurrentUser.DeleteSubKeyTree(testKey, throwOnMissingSubKey: false);
        }
    }

    [Test]
    public void ProductHostHidesOnCloseAndRegistersAutostart()
    {
        string app = File.ReadAllText(RepositoryPath("src", "Baxy.App", "App.xaml.cs"));
        string window = File.ReadAllText(RepositoryPath("src", "Baxy.App", "MainWindow.xaml.cs"));
        string project = File.ReadAllText(RepositoryPath("src", "Baxy.App", "Baxy.App.csproj"));

        Assert.Multiple(() =>
        {
            Assert.That(app, Does.Contain("WindowsAutostart.EnsureRegistered"));
            Assert.That(app, Does.Contain("TrayPresence"));
            Assert.That(app, Does.Contain("WindowsAutostart.TrayArgument"));
            Assert.That(window, Does.Contain("PresencePolicy.HideInsteadOfQuit"));
            Assert.That(window, Does.Contain("HideToTray"));
            Assert.That(project, Does.Contain("<UseWindowsForms>true</UseWindowsForms>"));
        });
    }

    private static string RepositoryPath(params string[] path)
    {
        DirectoryInfo? current = new(TestContext.CurrentContext.TestDirectory);
        while (current is not null && !File.Exists(Path.Combine(current.FullName, "Baxy.slnx")))
        {
            current = current.Parent;
        }

        if (current is null)
        {
            throw new AssertionException("Could not locate the BAXY repository root.");
        }

        return Path.Combine([current.FullName, .. path]);
    }
}
