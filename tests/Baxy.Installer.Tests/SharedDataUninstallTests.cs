using Baxy.Providers.Windows.External;
using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// UNI1 (blind review REV8, U1/U2/U6): «uninstall and delete your data» deleted the data folder of a BAXY that stays
/// installed: from a copy in another folder while the one «Installed apps» names uses the same data, and with a --dir
/// that holds no BAXY (a mistyped folder), which uninstalled nothing, deleted the data and said «uninstalled». The data
/// go only when no other BAXY uses them, and an uninstall that finds no BAXY does nothing. Every folder and registry key
/// here is the test's own.
/// </summary>
[TestFixture]
internal sealed class SharedDataUninstallTests
{
    private const string Alarm = "BAXY-Alarm-0123456789abcdef0123456789abcdef";

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
            Path.Combine(directory, "other-baxy"))
        {
            Scheduler = new NoScheduler(),
        };
        Directory.CreateDirectory(Path.GetDirectoryName(places.Link)!);
        Registry.CurrentUser.CreateSubKey(keys + @"\Uninstall").Dispose();

        // The BAXY «Installed apps» names, with its data and one alarm.
        registered = Baxy("BAXY-App");
        WindowsIntegration.Register(registered, "1.3.4", 1000, places);
        string root = Path.Combine(places.Data, "1");
        Directory.CreateDirectory(Path.Combine(root, ScheduledRingTasks.FolderName));
        memory = Path.Combine(root, "memory.db");
        File.WriteAllText(memory, "what BAXY remembers");
        File.WriteAllText(Path.Combine(root, ScheduledRingTasks.FolderName, Alarm + ".ps1"), "# BAXY ring v2");
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

    // U1: the code already knew the registered BAXY uses the data (it left its alarms); the same check now keeps the data.
    [Test]
    public void A_copy_in_another_folder_never_deletes_the_data_the_registered_baxy_uses()
    {
        InstallPaths copy = InstallPaths.ForUninstall(Baxy("Copy").Root, places);

        Assert.That(WindowsIntegration.DataSharedWith(copy, places), Is.EqualTo(registered.Root));
        Assert.That(WindowsIntegration.RingsToRemove(copy, places), Is.Zero);
        Assert.That(WindowsIntegration.RingsKept(copy, places), Is.EqualTo(1), "the screen names the alarms that stay");
        Assert.Throws<InvalidOperationException>(() => WindowsIntegration.Uninstall(copy, deleteData: true, places));
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(memory), Is.True, "the registered BAXY keeps its data");
            Assert.That(File.Exists(copy.App), Is.True, "nothing is removed when the data cannot go with it");
            Assert.That(WindowsIntegration.RegisteredRoot(places), Is.EqualTo(registered.Root));
        });

        WindowsIntegration.Uninstall(copy, deleteData: false, places);

        Assert.That(Directory.Exists(copy.Root), Is.False, "keeping the data, the copy goes");
        Assert.That(File.Exists(memory), Is.True);
    }

    [Test]
    public void The_registered_baxy_alone_still_deletes_its_data()
    {
        File.Delete(Path.Combine(places.Data, "1", ScheduledRingTasks.FolderName, Alarm + ".ps1"));
        InstallPaths copy = Baxy("Copy");

        Assert.That(WindowsIntegration.DataSharedWith(registered, places), Is.Null, "an unregistered copy is not known to use them");
        WindowsIntegration.Uninstall(registered, deleteData: true, places);

        Assert.That(Directory.Exists(places.Data), Is.False);
        Assert.That(File.Exists(copy.App), Is.True);
    }

    // An «Installed apps» entry whose folder is gone names no BAXY that uses the data.
    [Test]
    public void A_registered_folder_that_is_gone_shares_nothing()
    {
        InstallPaths copy = Baxy("Copy");
        Directory.Delete(registered.Root, recursive: true);

        Assert.That(WindowsIntegration.DataSharedWith(copy, places), Is.Null);
    }

    [TestCase("es", "no te ofrezco borrarlos")]
    [TestCase("en", "I don’t offer to delete it")]
    public void The_screen_says_why_it_does_not_offer_to_delete_the_data(string language, string why)
    {
        Texts texts = Texts.For(language);

        string shared = texts.UninstallBodyFor(rings: 0, dataBytes: 0, places.Data, kept: 1, sharedWith: registered.Root);

        Assert.That(shared, Does.Contain(why).And.Contain(registered.Root));
        Assert.That(shared, Does.Not.Contain(texts.UninstallBody), "not «you decide whether it stays» when it cannot go");
        Assert.That(texts.UninstallBodyFor(rings: 0, dataBytes: 0, places.Data), Is.EqualTo(texts.UninstallBody));
    }

    // U2: a mistyped --dir found no BAXY, uninstalled nothing, deleted the data and the log said «uninstalled».
    [Test]
    public void An_uninstall_of_a_folder_that_does_not_exist_is_refused_before_anything_is_touched()
    {
        string mistyped = Path.Combine(directory, "BAXY-Ap");

        ArgumentException refused = Assert.Throws<NothingToUninstallException>(() => InstallPaths.ForUninstall(mistyped, places))!;

        Assert.That(refused.Message, Does.Contain(mistyped));
        Assert.That(File.Exists(memory), Is.True);
        Assert.That(File.Exists(registered.App), Is.True);
    }

    [Test]
    public void An_uninstall_without_a_folder_that_finds_no_baxy_is_refused()
    {
        Registry.CurrentUser.DeleteSubKeyTree(places.UninstallKey);
        InstallPaths usual = new(Path.Combine(directory, "Nothing-here"));
        string downloaded = Path.Combine(directory, "Downloads", WindowsIntegration.InstallerName);

        Assert.Throws<NothingToUninstallException>(() => InstallPaths.ForUninstall(null, places, downloaded, usual));
        Assert.That(InstallPaths.ForUninstall(null, places, downloaded, registered), Is.EqualTo(registered));
    }

    // U6: the uninstaller kept inside a copy, opened by hand without --dir, removes that copy, not the registered one.
    [Test]
    public void An_uninstaller_inside_a_copy_takes_its_own_folder()
    {
        InstallPaths copy = Baxy("Copy");
        string inside = Path.Combine(copy.Root, WindowsIntegration.InstallerName);
        string downloaded = Path.Combine(directory, "Downloads", WindowsIntegration.InstallerName);

        Assert.That(InstallPaths.ForUninstall(null, places, inside), Is.EqualTo(copy));
        Assert.That(InstallPaths.ForUninstall(null, places, downloaded), Is.EqualTo(registered));
    }

    // U3 retry: an uninstall stopped after the folder was emptied around the held exe can run again from «Installed apps».
    [Test]
    public void The_registered_folder_with_only_its_uninstaller_left_can_be_uninstalled_again()
    {
        File.Delete(registered.App);
        File.WriteAllText(Path.Combine(registered.Root, WindowsIntegration.InstallerName), "exe");

        Assert.That(InstallPaths.ForUninstall(registered.Root, places), Is.EqualTo(registered));
        Assert.Throws<NothingToUninstallException>(() => InstallPaths.ForUninstall(Path.Combine(directory, "Downloads-like"), places));
    }

    // Independent review of UNI1: an uninstall of a copy stopped after its folder was emptied around the exe that waits
    // (a file held open by another program); run again from that copy, it took the registered BAXY instead, whole.
    [Test]
    public void A_copy_emptied_halfway_is_still_what_its_uninstaller_removes()
    {
        InstallPaths copy = Baxy("Copy");
        string exe = Path.Combine(copy.Root, WindowsIntegration.InstallerName);
        File.WriteAllText(exe, "exe");
        string busy = Path.Combine(copy.Root, "zz-busy.txt");
        using (new FileStream(busy, FileMode.Create, FileAccess.Write, FileShare.None))
        {
            Assert.Catch<IOException>(() => WindowsIntegration.Uninstall(copy, deleteData: false, places, held: exe));
        }

        Assert.That(copy.HoldsBaxy, Is.False, "its app went before the stop");
        Assert.That(InstallPaths.ForUninstall(null, places, exe), Is.EqualTo(copy));
        Assert.That(InstallPaths.ForUninstall(copy.Root, places), Is.EqualTo(copy));

        WindowsIntegration.Uninstall(copy, deleteData: false, places, held: exe);
        WindowsIntegration.DeleteHeld(copy, exe);

        Assert.That(Directory.Exists(copy.Root), Is.False, "its mark goes with the exe");
        Assert.That(File.Exists(registered.App), Is.True);
    }

    // Independent review of UNI1: a BAXY in the usual folder, not the one «Installed apps» names, uses the same data.
    [Test]
    public void A_baxy_in_the_usual_folder_keeps_the_data_too()
    {
        InstallPaths usual = Baxy("Usual");
        WindowsPlaces withUsual = places with { UsualRoot = usual.Root };

        Assert.That(WindowsIntegration.DataSharedWith(registered, withUsual), Is.EqualTo(usual.Root));
        Assert.That(WindowsIntegration.DataSharedWith(usual, withUsual), Is.EqualTo(registered.Root), "from the usual one, the registered one");
        Registry.CurrentUser.DeleteSubKeyTree(places.UninstallKey);
        Assert.That(WindowsIntegration.DataSharedWith(usual, withUsual), Is.Null, "the usual one alone is not another");
        Assert.Throws<InvalidOperationException>(() => WindowsIntegration.Uninstall(registered, deleteData: true, withUsual));
        Assert.That(File.Exists(memory), Is.True);
    }

    // U6: an empty folder with the other BAXY's name is not the other BAXY; what its setup puts there is.
    [TestCase(null, false)]
    [TestCase("Baxy.Setup.exe", true)]
    [TestCase(@"versions\1.1.1\Baxy.exe", true)]
    [TestCase("current", true)]
    public void The_other_baxy_is_what_its_setup_leaves_not_a_folder_name(string? file, bool installed)
    {
        Directory.CreateDirectory(places.OtherBaxy);
        if (file is not null)
        {
            string path = Path.Combine(places.OtherBaxy, file);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, "x");
        }

        Assert.That(WindowsIntegration.ADifferentBaxyIsInstalled(places), Is.EqualTo(installed));
        Assert.That(WindowsIntegration.DataSharedWith(registered, places), Is.EqualTo(installed ? places.OtherBaxy : null));
    }

    private InstallPaths Baxy(string name)
    {
        InstallPaths paths = new(Path.Combine(directory, name));
        Directory.CreateDirectory(Path.GetDirectoryName(paths.App)!);
        File.WriteAllText(paths.App, "the app");
        return paths;
    }

    /// <summary>No alarm is removed in these cases: a scheduler that is never opened.</summary>
    private sealed class NoScheduler : ITaskSchedulerHost
    {
        public ITaskSchedulerSession Open() => throw new AssertionException("the scheduler was opened");

        public int? ToastsEnabledSetting() => null;

        public string CurrentUserSid() => "S-1-5-21-1-2-3-1001";
    }
}
