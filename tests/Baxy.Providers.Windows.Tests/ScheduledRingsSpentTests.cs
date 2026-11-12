using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// PRV-2: a one-time alarm or reminder that rang stayed registered in the Task Scheduler for good (112 of them on the
/// PC this was measured on, every one Ready with no next run). Once it rang and will not ring again, its task and its
/// script go; whatever may still ring stays, and so does the receipt the diagnosis reads.
/// </summary>
[TestFixture]
public sealed class ScheduledRingsSpentTests
{
    private const string Rang = "BAXY-Alarm-0123456789abcdef0123456789abcdef";
    private const string Daily = "BAXY-Alarm-11111111111111111111111111111111";
    private const string ToRing = "BAXY-Reminder-22222222222222222222222222222222";
    private const string Missed = "BAXY-Reminder-33333333333333333333333333333333";
    private const string AnotherRoots = "BAXY-Alarm-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private const string SomeoneElses = "Someone-else-daily-backup";
    private const int Disabled = 1;
    private const int Ready = 3;
    private const int Running = 4;
    private static readonly DateTime Tomorrow = new(2026, 11, 10, 7, 0, 0, DateTimeKind.Local);

    private string dataRoot = null!;
    private string rings = null!;
    private FakeScheduler scheduler = null!;

    [SetUp]
    public void SetUp()
    {
        dataRoot = Path.Combine(Path.GetTempPath(), "baxy-prv2-tests-" + Guid.NewGuid().ToString("N"));
        rings = AlarmRingHandoff.Folder(dataRoot);
        Directory.CreateDirectory(rings);
        scheduler = new FakeScheduler();
        // A one-time alarm that rang: Windows keeps it Ready, with no next run.
        Record(Rang, Ready, next: null, rang: true);
        // A daily one that rang yesterday rings again tomorrow.
        Record(Daily, Ready, Tomorrow, rang: true);
        // A one-time reminder still to ring, and one whose time passed with the PC off: Windows starts it when it can
        // (StartWhenAvailable), and until then it has no next run either. Neither rang: no receipt.
        Record(ToRing, Ready, Tomorrow, rang: false);
        Record(Missed, Ready, next: null, rang: false);
        scheduler.Tasks[AnotherRoots] = new ScheduledTaskSnapshot(AnotherRoots, Ready, null, null, 0);
        scheduler.Tasks[SomeoneElses] = new ScheduledTaskSnapshot(SomeoneElses, Ready, null, null, 0);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(dataRoot, recursive: true);

    [Test]
    public void A_one_time_ring_that_rang_leaves_the_scheduler_with_its_script_and_what_may_still_ring_stays()
    {
        int removed = ScheduledRingsRemoval.RemoveSpent(scheduler, dataRoot);

        Assert.Multiple(() =>
        {
            Assert.That(removed, Is.EqualTo(1));
            Assert.That(scheduler.Tasks.Keys, Is.EquivalentTo(new[] { Daily, ToRing, Missed, AnotherRoots, SomeoneElses }));
            Assert.That(File.Exists(Script(Rang)), Is.False);
            Assert.That(new[] { Daily, ToRing, Missed }.All(name => File.Exists(Script(name))), Is.True);
            // What it wrote when it rang is what «why did my alarm not ring» reads: it stays its 30 days.
            Assert.That(File.Exists(Receipt(Rang)), Is.True);
        });
    }

    [TestCase(Running, TestName = "The_script_of_a_ring_that_still_runs_is_left_to_end")]
    [TestCase(Disabled, TestName = "A_task_the_person_disabled_is_not_one_that_ended")]
    public void A_task_that_is_not_ready_stays(int state)
    {
        scheduler.Tasks[Rang] = new ScheduledTaskSnapshot(Rang, state, null, null, 0);

        Assert.That(ScheduledRingsRemoval.RemoveSpent(scheduler, dataRoot), Is.Zero);
        Assert.That(scheduler.Tasks.ContainsKey(Rang) && File.Exists(Script(Rang)), Is.True);
    }

    [TestCase(AlarmRingHandoff.RingingExtension, TestName = "A_ring_the_App_still_rings_stays_until_it_ends")]
    [TestCase(AlarmRingHandoff.DueExtension, TestName = "A_ring_handed_over_and_not_taken_yet_stays")]
    public void A_ring_in_course_stays(string extension)
    {
        File.WriteAllText(Path.Combine(rings, Rang + extension), "{}");

        Assert.That(ScheduledRingsRemoval.RemoveSpent(scheduler, dataRoot), Is.Zero);
        Assert.That(scheduler.Tasks.ContainsKey(Rang) && File.Exists(Script(Rang)), Is.True);
    }

    [Test]
    public void A_folder_where_nothing_rang_never_opens_the_scheduler()
    {
        File.Delete(Receipt(Rang));
        File.Delete(Receipt(Daily));

        Assert.That(ScheduledRingsRemoval.RemoveSpent(scheduler, dataRoot), Is.Zero);
        Assert.That(scheduler.Opened, Is.Zero);
    }

    [Test]
    public void The_script_of_a_ring_that_rang_and_has_no_task_any_more_goes_too()
    {
        scheduler.Tasks.Remove(Rang);

        Assert.That(ScheduledRingsRemoval.RemoveSpent(scheduler, dataRoot), Is.EqualTo(1));
        Assert.That(File.Exists(Script(Rang)), Is.False);
    }

    [Test]
    public void A_scheduler_that_refuses_is_told_and_the_ring_stays_recorded_for_the_next_time()
    {
        scheduler.DeleteFailure = new TaskSchedulerHostException("task_delete_failed:0x80070005");

        IOException refused = Assert.Throws<IOException>(() => ScheduledRingsRemoval.RemoveSpent(scheduler, dataRoot))!;

        Assert.Multiple(() =>
        {
            Assert.That(refused.Message, Does.Contain("task_delete_failed:0x80070005"));
            Assert.That(scheduler.Tasks.ContainsKey(Rang), Is.True);
            Assert.That(File.Exists(Script(Rang)), Is.True);
        });
    }

    private string Script(string task) => Path.Combine(rings, task + ".ps1");

    private string Receipt(string task) => Path.Combine(rings, task + ".fired");

    private void Record(string task, int state, DateTime? next, bool rang)
    {
        scheduler.Tasks[task] = new ScheduledTaskSnapshot(task, state, next, null, 0);
        File.WriteAllText(Script(task), "ring");
        if (rang)
        {
            File.WriteAllText(Receipt(task), """{"rangUtc":"2026-11-09T10:00:00.0000000+00:00","rungBy":"app"}""");
        }
    }

    private sealed class FakeScheduler : ITaskSchedulerHost
    {
        internal Dictionary<string, ScheduledTaskSnapshot> Tasks { get; } = new(StringComparer.OrdinalIgnoreCase);
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
            public IReadOnlyList<string> TaskNames() => [.. owner.Tasks.Keys];

            public IReadOnlyList<ScheduledTaskSnapshot> Read(string namePrefix) =>
                [.. owner.Tasks.Values.Where(task => task.Name.StartsWith(namePrefix, StringComparison.OrdinalIgnoreCase))];

            public ScheduledTaskSnapshot? Find(string name) => owner.Tasks.GetValueOrDefault(name);

            public void Register(string name, string xml) =>
                owner.Tasks[name] = new ScheduledTaskSnapshot(name, Ready, null, null, 0);

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
