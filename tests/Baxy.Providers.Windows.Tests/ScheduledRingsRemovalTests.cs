using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// INS-1: what the App runs for a store's uninstall (Baxy.exe --remove-scheduled-rings) removes the tasks its data root
/// recorded, by their exact name, and nothing else in the scheduler.
/// </summary>
[TestFixture]
public sealed class ScheduledRingsRemovalTests
{
    private const string Alarm = "BAXY-Alarm-0123456789abcdef0123456789abcdef";
    private const string Reminder = "BAXY-Reminder-fedcba9876543210fedcba9876543210";
    private const string AnotherRoots = "BAXY-Alarm-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private const string SomeoneElses = "Someone-else-daily-backup";

    private string dataRoot = null!;
    private string rings = null!;
    private FakeScheduler scheduler = null!;

    [SetUp]
    public void SetUp()
    {
        dataRoot = Path.Combine(Path.GetTempPath(), "baxy-ins1-tests-" + Guid.NewGuid().ToString("N"));
        rings = AlarmRingHandoff.Folder(dataRoot);
        Directory.CreateDirectory(rings);
        scheduler = new FakeScheduler();
        scheduler.Tasks.UnionWith([Alarm, Reminder, AnotherRoots, SomeoneElses]);
        File.WriteAllText(Path.Combine(rings, Alarm + ".ps1"), "ring");
        File.WriteAllText(Path.Combine(rings, Alarm + ".fired"), "2026-11-09T07:00:00");
        File.WriteAllText(Path.Combine(rings, Reminder + ".ps1"), "ring");
        File.WriteAllText(Path.Combine(rings, "notes.txt"), "not a ring");
    }

    [TearDown]
    public void TearDown() => Directory.Delete(dataRoot, recursive: true);

    [Test]
    public void The_rings_the_data_root_recorded_leave_the_scheduler_with_their_files_and_nothing_else_does()
    {
        int removed = ScheduledRingsRemoval.RemoveAll(scheduler, dataRoot);

        Assert.Multiple(() =>
        {
            Assert.That(removed, Is.EqualTo(2));
            Assert.That(scheduler.Tasks, Is.EquivalentTo(new[] { AnotherRoots, SomeoneElses }));
            Assert.That(Directory.GetFiles(rings).Select(Path.GetFileName), Is.EquivalentTo(new[] { "notes.txt" }));
        });
    }

    [Test]
    public void A_data_root_with_no_ring_never_opens_the_scheduler()
    {
        string empty = Path.Combine(dataRoot, "empty");

        Assert.That(ScheduledRingsRemoval.RemoveAll(scheduler, empty), Is.Zero);
        Assert.That(scheduler.Opened, Is.Zero);
    }

    [Test]
    public void A_scheduler_that_refuses_is_told_and_the_ring_stays_recorded()
    {
        scheduler.DeleteFailure = new TaskSchedulerHostException("task_delete_failed:0x80070005");

        IOException refused = Assert.Throws<IOException>(() => ScheduledRingsRemoval.RemoveAll(scheduler, dataRoot))!;

        Assert.Multiple(() =>
        {
            Assert.That(refused.Message, Does.Contain("task_delete_failed:0x80070005"));
            Assert.That(scheduler.Tasks, Does.Contain(Alarm));
            Assert.That(File.Exists(Path.Combine(rings, Alarm + ".ps1")), Is.True);
        });
    }

    [Test]
    public void A_ring_script_named_like_nothing_baxy_sets_is_not_a_task_to_remove()
    {
        File.WriteAllText(Path.Combine(rings, "BAXY-Backup-0123456789abcdef0123456789abcdef.ps1"), "someone's");
        scheduler.Tasks.Add("BAXY-Backup-0123456789abcdef0123456789abcdef");

        ScheduledRingsRemoval.RemoveAll(scheduler, dataRoot);

        Assert.That(scheduler.Tasks, Does.Contain("BAXY-Backup-0123456789abcdef0123456789abcdef"));
        Assert.That(File.Exists(Path.Combine(rings, "BAXY-Backup-0123456789abcdef0123456789abcdef.ps1")), Is.True);
    }

    private sealed class FakeScheduler : ITaskSchedulerHost
    {
        internal HashSet<string> Tasks { get; } = new(StringComparer.OrdinalIgnoreCase);
        internal int Opened { get; private set; }
        internal Exception? DeleteFailure { get; set; }

        public ITaskSchedulerSession Open()
        {
            Opened++;
            return new Session(this);
        }

        public int? ToastsEnabledSetting() => null;

        public string CurrentUserSid() => "S-1-5-21-1-2-3-1001";

        private sealed class Session(FakeScheduler owner) : ITaskSchedulerSession
        {
            public IReadOnlyList<string> TaskNames() => [.. owner.Tasks];

            public IReadOnlyList<ScheduledTaskSnapshot> Read(string namePrefix) =>
                [.. owner.Tasks.Where(name => name.StartsWith(namePrefix, StringComparison.OrdinalIgnoreCase)).Select(name => Find(name)!)];

            public ScheduledTaskSnapshot? Find(string name) =>
                owner.Tasks.Contains(name) ? new ScheduledTaskSnapshot(name, 3, null, null, 0) : null;

            public void Register(string name, string xml) => owner.Tasks.Add(name);

            public void Delete(string name)
            {
                if (owner.DeleteFailure is not null) throw owner.DeleteFailure;
                owner.Tasks.Remove(name);
            }

            public void Dispose()
            {
            }
        }
    }
}
