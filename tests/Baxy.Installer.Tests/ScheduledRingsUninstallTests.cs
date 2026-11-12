using Baxy.Providers.Windows.External;
using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// INS-1: uninstalling left the alarms and reminders BAXY had set in the Task Scheduler, so a PC with no BAXY kept
/// ringing them. The uninstall removes the tasks BAXY recorded (one ring script per task in its data), and nothing
/// else. The scheduler here is a double and every folder and registry key is the test's own: the Task Scheduler of the
/// machine that runs them is never opened.
/// </summary>
[TestFixture]
internal sealed class ScheduledRingsUninstallTests
{
    private const string Alarm = "BAXY-Alarm-0123456789abcdef0123456789abcdef";
    private const string Reminder = "BAXY-Reminder-fedcba9876543210fedcba9876543210";
    // Of that shape, but with no script in this BAXY's data: set from another data root or by another program.
    private const string NotRecorded = "BAXY-Alarm-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private const string Foreign = "Someone-else-daily-backup";

    private string directory = string.Empty;
    private string keys = string.Empty;
    private FakeScheduler scheduler = null!;
    private WindowsPlaces places = null!;
    private string rings = string.Empty;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
        keys = @"Software\BAXY-Installer-Tests\" + Path.GetRandomFileName();
        scheduler = new FakeScheduler();
        places = new WindowsPlaces(
            Path.Combine(directory, "Start", "BAXY.lnk"),
            keys + @"\Uninstall\BAXY-App",
            keys + @"\Run",
            Path.Combine(directory, "data"),
            Path.Combine(directory, "other-baxy"))
        {
            Scheduler = scheduler,
        };
        Directory.CreateDirectory(Path.GetDirectoryName(places.Link)!);
        Registry.CurrentUser.CreateSubKey(keys + @"\Uninstall").Dispose();
        // BAXY's data root is the folder «1» of its data (MemoryOperationProtector.ResolveDataRoot).
        rings = Path.Combine(places.Data, "1", ScheduledRingTasks.FolderName);
        Directory.CreateDirectory(rings);
        foreach (string task in new[] { Alarm, Reminder })
        {
            scheduler.Tasks.Add(task);
            File.WriteAllText(Path.Combine(rings, task + ".ps1"), "# BAXY ring v2");
        }

        File.WriteAllText(Path.Combine(rings, Alarm + ".fired"), "{}");
        File.WriteAllText(Path.Combine(rings, Reminder + ".answer"), "stop");
        File.WriteAllText(Path.Combine(rings, "notes.txt"), "not a ring");
        scheduler.Tasks.Add(NotRecorded);
        scheduler.Tasks.Add(Foreign);
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
    public void Uninstalling_and_keeping_the_data_removes_the_tasks_baxy_set_and_their_files_and_nothing_else()
    {
        InstallPaths paths = Installed();
        File.WriteAllText(Path.Combine(places.Data, "1", "memory.db"), "mine");

        Assert.That(WindowsIntegration.RingsToRemove(paths, places), Is.EqualTo(2));
        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.Multiple(() =>
        {
            Assert.That(scheduler.Tasks, Is.EquivalentTo(new[] { NotRecorded, Foreign }),
                "only the tasks BAXY recorded go: another program's and one with no script here stay");
            Assert.That(Directory.GetFiles(rings).Select(Path.GetFileName), Is.EqualTo(new[] { "notes.txt" }),
                "the scripts and receipts of the removed rings go with them");
            Assert.That(File.Exists(Path.Combine(places.Data, "1", "memory.db")), Is.True, "the data stay");
            Assert.That(Directory.Exists(paths.Root), Is.False);
        });
    }

    [Test]
    public void Uninstalling_and_deleting_the_data_removes_the_tasks_too()
    {
        InstallPaths paths = Installed();

        WindowsIntegration.Uninstall(paths, deleteData: true, places);

        Assert.That(scheduler.Tasks, Is.EquivalentTo(new[] { NotRecorded, Foreign }));
        Assert.That(Directory.Exists(places.Data), Is.False);
    }

    // The published exe's quiet uninstall from the installed copy (the folder is emptied around the held exe).
    [Test]
    public void The_uninstall_around_a_held_exe_removes_the_tasks_too()
    {
        InstallPaths paths = Installed();
        string exe = Path.Combine(paths.Root, WindowsIntegration.InstallerName);

        WindowsIntegration.Uninstall(paths, deleteData: false, places, held: exe);

        Assert.That(scheduler.Tasks, Is.EquivalentTo(new[] { NotRecorded, Foreign }));
        Assert.That(WindowsIntegration.RegisteredRoot(places), Is.Null);
    }

    // The other BAXY (its own setup) shares the data folder: the alarms are as much its own, and it rings them.
    [Test]
    public void With_the_other_baxy_installed_its_alarms_stay()
    {
        InstallPaths paths = Installed();
        // UNI1: what the other BAXY's setup leaves in its folder (src/Baxy.Setup/CanonicalWindowsPaths.cs).
        Directory.CreateDirectory(Path.Combine(places.OtherBaxy, "versions"));

        Assert.That(WindowsIntegration.RingsToRemove(paths, places), Is.Zero);
        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(scheduler.Tasks, Has.Count.EqualTo(4));
        Assert.That(File.Exists(Path.Combine(rings, Alarm + ".ps1")), Is.True);
        Assert.That(scheduler.Opened, Is.Zero);
    }

    // A copy in another folder is removed while «Installed apps» names the BAXY that stays: the alarms are that one's.
    [Test]
    public void Uninstalling_another_folder_leaves_the_alarms_of_the_registered_one()
    {
        Installed();
        InstallPaths other = new(Path.Combine(directory, "Copy"));
        Directory.CreateDirectory(Path.GetDirectoryName(other.App)!);
        File.WriteAllText(other.App, "the app");

        Assert.That(WindowsIntegration.RingsToRemove(other, places), Is.Zero);
        WindowsIntegration.Uninstall(other, deleteData: false, places);

        Assert.That(scheduler.Tasks, Has.Count.EqualTo(4));
        Assert.That(scheduler.Opened, Is.Zero);
    }

    // A scheduler that refuses stops the uninstall while «Installed apps» still offers it: nothing is said to be
    // uninstalled with alarms left behind, and the person can try again.
    [Test]
    public void A_scheduler_that_refuses_stops_the_uninstall_before_the_entries_go()
    {
        InstallPaths paths = Installed();
        scheduler.DeleteFailure = new TaskSchedulerHostException("task_delete_failed:0x80070005");

        IOException refused = Assert.Throws<IOException>(() => WindowsIntegration.Uninstall(paths, deleteData: true, places))!;

        Assert.Multiple(() =>
        {
            Assert.That(refused.Message, Does.Contain("task_delete_failed:0x80070005"));
            Assert.That(File.Exists(paths.App), Is.True, "the folder is back where it was");
            Assert.That(WindowsIntegration.RegisteredRoot(places), Is.EqualTo(paths.Root));
            Assert.That(File.Exists(places.Link), Is.True);
            Assert.That(Directory.Exists(places.Data), Is.True);
            Assert.That(File.Exists(Path.Combine(rings, Alarm + ".ps1")), Is.True, "the record of the task not removed stays");
        });

        scheduler.DeleteFailure = null;
        WindowsIntegration.Uninstall(paths, deleteData: true, places);

        Assert.That(scheduler.Tasks, Is.EquivalentTo(new[] { NotRecorded, Foreign }));
        Assert.That(Directory.Exists(paths.Root), Is.False);
    }

    [Test]
    public void A_scheduler_that_does_not_open_stops_the_uninstall_too()
    {
        InstallPaths paths = Installed();
        scheduler.OpenFailure = new TaskSchedulerHostException("task_scheduler_open_failed");

        Assert.Throws<IOException>(() => WindowsIntegration.Uninstall(paths, deleteData: false, places));

        Assert.That(File.Exists(paths.App), Is.True);
        Assert.That(WindowsIntegration.RegisteredRoot(places), Is.EqualTo(paths.Root));
    }

    // A ring whose task is already gone (it was deleted by hand in the Task Scheduler) only leaves its files to remove.
    [Test]
    public void A_recorded_ring_whose_task_is_gone_only_loses_its_files()
    {
        InstallPaths paths = Installed();
        scheduler.Tasks.Remove(Reminder);

        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(scheduler.Tasks, Is.EquivalentTo(new[] { NotRecorded, Foreign }));
        Assert.That(Directory.GetFiles(rings).Select(Path.GetFileName), Is.EqualTo(new[] { "notes.txt" }));
    }

    [Test]
    public void With_no_alarm_set_the_scheduler_is_never_opened()
    {
        InstallPaths paths = Installed();
        Directory.Delete(rings, recursive: true);

        Assert.That(WindowsIntegration.RingsToRemove(paths, places), Is.Zero);
        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(scheduler.Opened, Is.Zero);
        Assert.That(scheduler.Tasks, Has.Count.EqualTo(4));
    }

    // The screen says what the uninstall does to them, in both languages, only when there is something to say.
    [TestCase("es", "alarmas")]
    [TestCase("en", "alarms")]
    public void The_uninstall_screen_says_the_alarms_go_only_when_some_will(string language, string word)
    {
        Texts texts = language == "es" ? Texts.Spanish : Texts.English;

        Assert.That(texts.UninstallBodyFor(rings: 2, dataBytes: 0, string.Empty), Does.StartWith(texts.UninstallBody).And.Contain(word));
        Assert.That(texts.UninstallBodyFor(rings: 0, dataBytes: 0, string.Empty), Is.EqualTo(texts.UninstallBody));
    }

    private InstallPaths Installed()
    {
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.Combine(paths.Root, "app"));
        File.WriteAllText(paths.App, "the app");
        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        return paths;
    }

    /// <summary>A Task Scheduler folder in memory: the names registered in it.</summary>
    private sealed class FakeScheduler : ITaskSchedulerHost
    {
        internal HashSet<string> Tasks { get; } = new(StringComparer.OrdinalIgnoreCase);

        internal int Opened { get; private set; }

        internal Exception? OpenFailure { get; set; }

        internal Exception? DeleteFailure { get; set; }

        public ITaskSchedulerSession Open()
        {
            Opened++;
            return OpenFailure is null ? new Session(this) : throw OpenFailure;
        }

        public int? ToastsEnabledSetting() => null;

        public string CurrentUserSid() => "S-1-5-21-1-2-3-1001";

        private sealed class Session(FakeScheduler owner) : ITaskSchedulerSession
        {
            public IReadOnlyList<string> TaskNames() => [.. owner.Tasks];

            public IReadOnlyList<ScheduledTaskSnapshot> Read(string namePrefix) =>
                [.. owner.Tasks.Where(name => name.StartsWith(namePrefix, StringComparison.OrdinalIgnoreCase))
                    .Select(static name => new ScheduledTaskSnapshot(name, 3, null, null, 0))];

            public ScheduledTaskSnapshot? Find(string name) =>
                owner.Tasks.Contains(name) ? new ScheduledTaskSnapshot(name, 3, null, null, 0) : null;

            public void Register(string name, string xml) => owner.Tasks.Add(name);

            public void Delete(string name)
            {
                if (owner.DeleteFailure is not null)
                {
                    throw owner.DeleteFailure;
                }

                if (!owner.Tasks.Remove(name))
                {
                    throw new TaskSchedulerHostException("task_delete_failed:0x80070002");
                }
            }

            public void Dispose()
            {
            }
        }
    }
}
