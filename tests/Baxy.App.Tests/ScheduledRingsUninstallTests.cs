using System.IO;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// INS-1: a store's uninstall has no uninstaller of BAXY's, so Baxy.exe --remove-scheduled-rings is what takes BAXY's
/// alarms out of Windows; it leaves them when another BAXY on the PC keeps the same data.
/// </summary>
[TestFixture]
public sealed class ScheduledRingsUninstallTests
{
    private string root = null!;
    private string own = null!;
    private string dataRoot = null!;
    private List<string> removedFrom = null!;

    [SetUp]
    public void SetUp()
    {
        root = Path.Combine(Path.GetTempPath(), "baxy-ins1-app-tests-" + Guid.NewGuid().ToString("N"));
        own = Path.Combine(root, "steamapps", "common", "BAXY", "app");
        dataRoot = Path.Combine(root, "data", "1");
        Directory.CreateDirectory(own);
        removedFrom = [];
    }

    [TearDown]
    public void TearDown() => Directory.Delete(root, recursive: true);

    private int Remove(string from)
    {
        removedFrom.Add(from);
        return 2;
    }

    [TestCase(new[] { "--remove-scheduled-rings" }, true)]
    [TestCase(new string[0], false)]
    [TestCase(new[] { "--remove-scheduled-rings", "extra" }, false)]
    [TestCase(new[] { "--from-windows-start" }, false)]
    [TestCase(new[] { "--REMOVE-SCHEDULED-RINGS" }, false)]
    public void Only_the_argument_alone_asks_for_it(string[] arguments, bool asked) =>
        Assert.That(ScheduledRingsUninstall.IsRequested(arguments), Is.EqualTo(asked));

    [Test]
    public void With_no_other_baxy_on_the_pc_the_rings_of_the_data_root_are_removed()
    {
        int code = ScheduledRingsUninstall.Run(dataRoot, own, [Path.Combine(root, "Programs", "BAXY")], Remove);

        Assert.That(code, Is.Zero);
        Assert.That(removedFrom, Is.EqualTo(new[] { dataRoot }));
    }

    [Test]
    public void Another_baxy_installed_keeps_its_alarms()
    {
        string other = Path.Combine(root, "Programs", "BAXY-App");
        Holding(Path.Combine(other, "app", "Baxy.exe"));

        int code = ScheduledRingsUninstall.Run(dataRoot, own, [Path.Combine(root, "Programs", "BAXY"), other], Remove);

        Assert.That(code, Is.Zero);
        Assert.That(removedFrom, Is.Empty);
    }

    [Test]
    public void The_installation_this_executable_runs_from_is_not_another_one()
    {
        string installation = Path.Combine(root, "steamapps", "common", "BAXY");

        ScheduledRingsUninstall.Run(dataRoot, own, [installation + Path.DirectorySeparatorChar], Remove);

        Assert.That(removedFrom, Is.EqualTo(new[] { dataRoot }));
    }

    [Test]
    public void A_folder_that_only_starts_with_the_same_letters_is_another_one()
    {
        string sibling = Path.Combine(root, "steamapps", "common", "BAXY", "ap");
        Holding(Path.Combine(sibling, "app", "Baxy.exe"));

        ScheduledRingsUninstall.Run(dataRoot, own, [sibling], Remove);

        Assert.That(removedFrom, Is.Empty);
    }

    // UPD1 (REV10 m4): an empty Programs\BAXY, or the folder of an old entry with no BAXY left in it, kept the alarms
    // ringing with no BAXY. The installer's own check since UNI1 (WindowsIntegration.ADifferentBaxyIsInstalled, DataSharedWith).
    [Test]
    public void A_folder_with_a_baxys_name_but_no_baxy_in_it_keeps_nothing()
    {
        string usual = Path.Combine(root, "Programs", "BAXY");
        Directory.CreateDirectory(usual);
        string entry = Path.Combine(root, "Programs", "BAXY-App");
        Holding(Path.Combine(entry, "BAXY-folder.mark"));

        ScheduledRingsUninstall.Run(dataRoot, own, [usual, entry], Remove);

        Assert.That(removedFrom, Is.EqualTo(new[] { dataRoot }));
    }

    [TestCase("Baxy.Setup.exe")]
    [TestCase("current")]
    [TestCase(@"versions\1.0.0\x")]
    public void The_other_baxy_with_its_own_setup_keeps_its_alarms(string inside)
    {
        Holding(Path.Combine(root, "Programs", "BAXY", inside));

        ScheduledRingsUninstall.Run(dataRoot, own, [Path.Combine(root, "Programs", "BAXY")], Remove);

        Assert.That(removedFrom, Is.Empty);
    }

    private static void Holding(string file)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(file)!);
        File.WriteAllText(file, "x");
    }

    [Test]
    public void A_scheduler_that_refuses_is_the_exit_code()
    {
        int code = ScheduledRingsUninstall.Run(
            dataRoot, own, [], static _ => throw new IOException("task_delete_failed:0x80070005"));

        Assert.That(code, Is.EqualTo(ScheduledRingsUninstall.Refused));
    }
}
