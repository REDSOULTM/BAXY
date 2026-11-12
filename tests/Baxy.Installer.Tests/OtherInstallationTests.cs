using Baxy.Providers.Windows.External;
using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// COX-1: another BAXY installed beside this one (its own setup, its own folder) shares the Start-menu name «BAXY», the
/// Run value «BAXY» and the data folder. Installing and starting this one took the first two; uninstalling it took them
/// away, so the other was left with no Start entry and no start with Windows, and its alarms stayed without the screen
/// saying so. Each installation removes only what is its own and gives back what it replaced. Every folder and
/// registry key here is the test's own.
/// </summary>
[TestFixture]
internal sealed class OtherInstallationTests
{
    private const string Alarm = "BAXY-Alarm-0123456789abcdef0123456789abcdef";

    private string directory = string.Empty;
    private string keys = string.Empty;
    private WindowsPlaces places = null!;
    private InstallPaths paths = null!;
    private string otherExe = string.Empty;
    private string otherCommand = string.Empty;

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
            Path.Combine(directory, "other-baxy"))
        {
            Scheduler = new NoScheduler(),
        };
        Directory.CreateDirectory(Path.GetDirectoryName(places.Link)!);
        Registry.CurrentUser.CreateSubKey(keys + @"\Uninstall").Dispose();
        paths = new InstallPaths(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.GetDirectoryName(paths.App)!);
        File.WriteAllText(paths.App, "the app");

        // The other BAXY: its folder, its exe, its shortcut and its start with Windows, there before this one.
        otherExe = Path.Combine(places.OtherBaxy, "versions", "1.0", "Baxy.exe");
        Directory.CreateDirectory(Path.GetDirectoryName(otherExe)!);
        File.WriteAllText(otherExe, "the other app");
        otherCommand = $"\"{otherExe}\" --from-windows-start";
        ShellLink.Write(places.Link, otherExe, "BAXY");
        using RegistryKey run = Registry.CurrentUser.CreateSubKey(places.RunKey);
        run.SetValue(WindowsIntegration.AutostartValue, otherCommand);
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
    public void Installing_beside_the_other_takes_the_start_entry_and_uninstalling_gives_it_back_as_it_was()
    {
        byte[] before = File.ReadAllBytes(places.Link);

        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        Assert.That(ShellLink.Target(places.Link), Is.EqualTo(paths.App), "the name the person looks for opens the BAXY just installed");

        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(File.Exists(places.Link), Is.True, "the other BAXY keeps its Start entry");
        Assert.That(File.ReadAllBytes(places.Link), Is.EqualTo(before), "byte for byte: its icon, arguments and folder too");
    }

    [Test]
    public void The_start_with_windows_this_baxy_took_goes_back_to_the_other_on_uninstall()
    {
        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        // What the App does at its start (WindowsAutostartRegistration): it keeps what it replaces, then writes its own.
        using (RegistryKey uninstall = Registry.CurrentUser.OpenSubKey(places.UninstallKey, writable: true)!)
        {
            uninstall.SetValue(WindowsIntegration.ReplacedAutostartValue, otherCommand);
        }

        SetRun($"\"{paths.App}\" --from-windows-start");

        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(Run(), Is.EqualTo(otherCommand));
    }

    [Test]
    public void What_the_other_baxy_wrote_again_after_this_one_stays()
    {
        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        // The other BAXY was opened later and took both back.
        ShellLink.Write(places.Link, otherExe, "BAXY");
        SetRun(otherCommand);

        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(ShellLink.Target(places.Link), Is.EqualTo(otherExe));
        Assert.That(Run(), Is.EqualTo(otherCommand));
    }

    [Test]
    public void Nothing_comes_back_that_would_start_an_exe_that_is_gone()
    {
        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        using (RegistryKey uninstall = Registry.CurrentUser.OpenSubKey(places.UninstallKey, writable: true)!)
        {
            uninstall.SetValue(WindowsIntegration.ReplacedAutostartValue, otherCommand);
        }

        SetRun($"\"{paths.App}\" --from-windows-start");
        File.Delete(otherExe);

        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(File.Exists(places.Link), Is.False);
        Assert.That(Run(), Is.Null);
    }

    // A shortcut the shell cannot read is not known to be this BAXY's: it is kept, and comes back as it was.
    [Test]
    public void A_shortcut_that_cannot_be_read_is_kept_and_given_back()
    {
        byte[] unreadable = [0x42, 0x41, 0x58, 0x59];
        File.WriteAllBytes(places.Link, unreadable);

        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(File.ReadAllBytes(places.Link), Is.EqualTo(unreadable));
    }

    [Test]
    public void Without_another_baxy_the_uninstall_takes_its_own_entries_as_before()
    {
        File.Delete(places.Link);
        using (RegistryKey run = Registry.CurrentUser.OpenSubKey(places.RunKey, writable: true)!)
        {
            run.DeleteValue(WindowsIntegration.AutostartValue);
        }

        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        SetRun($"\"{paths.App}\" --from-windows-start");

        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(File.Exists(places.Link), Is.False);
        Assert.That(Run(), Is.Null);
    }

    // The alarms are the data's, and the other BAXY uses the same data: they stay, and the screen says so with how many.
    [TestCase("es", "seguirán sonando")]
    [TestCase("en", "keep ringing")]
    public void The_uninstall_screen_names_the_alarms_that_stay_with_the_other_baxy(string language, string words)
    {
        string ringFolder = Path.Combine(places.Data, "1", ScheduledRingTasks.FolderName);
        Directory.CreateDirectory(ringFolder);
        File.WriteAllText(Path.Combine(ringFolder, Alarm + ".ps1"), "# BAXY ring v2");
        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        Texts texts = language == "es" ? Texts.Spanish : Texts.English;

        Assert.That(WindowsIntegration.RingsToRemove(paths, places), Is.Zero);
        Assert.That(WindowsIntegration.RingsKept(paths, places), Is.EqualTo(1));
        string body = texts.UninstallBodyFor(rings: 0, dataBytes: 0, string.Empty, kept: 1, places.OtherBaxy);
        Assert.That(body, Does.Contain(words).And.Contain(places.OtherBaxy));
        // UNI1: the data stay with the other BAXY too, and the screen says so instead of «you decide whether it stays».
        Assert.That(
            texts.UninstallBodyFor(rings: 0, dataBytes: 0, string.Empty, kept: 0, places.OtherBaxy),
            Is.EqualTo(string.Format(System.Globalization.CultureInfo.CurrentCulture, texts.UninstallBodyShared, places.OtherBaxy)));
    }

    private void SetRun(string command)
    {
        using RegistryKey run = Registry.CurrentUser.CreateSubKey(places.RunKey);
        run.SetValue(WindowsIntegration.AutostartValue, command);
    }

    private string? Run()
    {
        using RegistryKey? run = Registry.CurrentUser.OpenSubKey(places.RunKey);
        return run?.GetValue(WindowsIntegration.AutostartValue) as string;
    }

    /// <summary>No alarm is removed in these cases: a scheduler that is never opened.</summary>
    private sealed class NoScheduler : ITaskSchedulerHost
    {
        public ITaskSchedulerSession Open() => throw new AssertionException("the scheduler was opened");

        public int? ToastsEnabledSetting() => null;

        public string CurrentUserSid() => "S-1-5-21-1-2-3-1001";
    }
}
