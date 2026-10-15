using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría de estabilidad r19, hallazgo 4: the ring scripts and receipts of notifications that rang long ago
/// piled up in the data root. Setting a new notification removes those; a pending one (no receipt) and one that
/// rang recently (a recurring one rewrites its receipt each ring) stay, and so does any whose task the scheduler
/// still holds, whatever the age of its receipt (a daily one on a machine that stayed off for a month).
/// </summary>
[TestFixture]
public sealed class ScheduledNotificationPruneTests
{
    [Test]
    public void SpentNotificationsGoAndLiveOnesStay()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-alarm-prune-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            DateTimeOffset now = new(2026, 10, 9, 3, 0, 0, TimeSpan.Zero);
            string spent = Write(root, "BAXY-Alarm-" + new string('a', 32), now.AddDays(-31));
            string recent = Write(root, "BAXY-Reminder-" + new string('b', 32), now.AddDays(-2));
            string pending = Path.Combine(root, "BAXY-Alarm-" + new string('c', 32));
            File.WriteAllText(pending + ".ps1", "# ring");
            File.SetLastWriteTimeUtc(pending + ".ps1", now.AddDays(-90).UtcDateTime);
            string foreign = Path.Combine(root, "other.fired");
            File.WriteAllText(foreign, "x");
            File.SetLastWriteTimeUtc(foreign, now.AddDays(-90).UtcDateTime);

            WindowsScheduledNotificationAdapter.PruneSpentRingScripts(root, now, new HashSet<string>());

            Assert.Multiple(() =>
            {
                Assert.That(File.Exists(spent + ".ps1"), Is.False);
                Assert.That(File.Exists(spent + ".fired"), Is.False);
                Assert.That(File.Exists(recent + ".ps1"), Is.True);
                Assert.That(File.Exists(recent + ".fired"), Is.True);
                Assert.That(File.Exists(pending + ".ps1"), Is.True);
                Assert.That(File.Exists(foreign), Is.True);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public void AMissingRootIsNoFailure() =>
        Assert.DoesNotThrow(() => WindowsScheduledNotificationAdapter.PruneSpentRingScripts(
            Path.Combine(Path.GetTempPath(), "baxy-alarm-prune-missing-" + Guid.NewGuid().ToString("N")),
            DateTimeOffset.UtcNow,
            new HashSet<string>()));

    [Test]
    public void AStillRegisteredTaskKeepsItsScriptHoweverOldItsReceipt()
    {
        string root = NewRoot();
        try
        {
            DateTimeOffset now = new(2026, 10, 9, 3, 0, 0, TimeSpan.Zero);
            string daily = "BAXY-Reminder-" + new string('d', 32);
            string stem = Write(root, daily, now.AddDays(-45));

            WindowsScheduledNotificationAdapter.PruneSpentRingScripts(
                root, now, new HashSet<string>(StringComparer.OrdinalIgnoreCase) { daily });

            Assert.Multiple(() =>
            {
                Assert.That(File.Exists(stem + ".ps1"), Is.True);
                Assert.That(File.Exists(stem + ".fired"), Is.True);
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // Setting a notification reads the scheduler first: the daily reminder it still holds keeps its ring script
    // although its last ring is 45 days old; the one-shot it no longer holds goes.
    [Test]
    public async Task SettingANotificationKeepsTheScriptOfATaskTheSchedulerStillHolds()
    {
        string dataRoot = NewRoot();
        try
        {
            string scheduler = Path.Combine(dataRoot, "WindowsScheduledNotification.ps1");
            await File.WriteAllTextAsync(scheduler, "# fixture");
            string alarms = Path.Combine(dataRoot, "scheduled-notifications");
            Directory.CreateDirectory(alarms);
            DateTimeOffset now = DateTimeOffset.UtcNow;
            string daily = "BAXY-Reminder-" + new string('e', 32);
            string liveStem = Write(alarms, daily, now.AddDays(-45));
            string goneStem = Write(alarms, "BAXY-Alarm-" + new string('f', 32), now.AddDays(-45));
            var runner = new SchedulerRunner([daily]);
            var adapter = new WindowsScheduledNotificationAdapter(dataRoot, runner, scheduler);

            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "schedule.alarms",
                Arguments(now.AddHours(1)),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True);
                Assert.That(runner.Modes, Is.EqualTo(new[] { "diagnose", "schedule" }));
                Assert.That(File.Exists(liveStem + ".ps1"), Is.True);
                Assert.That(File.Exists(liveStem + ".fired"), Is.True);
                Assert.That(File.Exists(goneStem + ".ps1"), Is.False);
                Assert.That(File.Exists(goneStem + ".fired"), Is.False);
            });
        }
        finally
        {
            Directory.Delete(dataRoot, recursive: true);
        }
    }

    // Without a scheduler read that answered with its task list nothing is proven gone, so nothing goes.
    [Test]
    public async Task AFailedSchedulerReadDeletesNothing()
    {
        string dataRoot = NewRoot();
        try
        {
            string scheduler = Path.Combine(dataRoot, "WindowsScheduledNotification.ps1");
            await File.WriteAllTextAsync(scheduler, "# fixture");
            string alarms = Path.Combine(dataRoot, "scheduled-notifications");
            Directory.CreateDirectory(alarms);
            DateTimeOffset now = DateTimeOffset.UtcNow;
            string stem = Write(alarms, "BAXY-Reminder-" + new string('g', 32), now.AddDays(-45));
            var runner = new SchedulerRunner(liveTasks: null);
            var adapter = new WindowsScheduledNotificationAdapter(dataRoot, runner, scheduler);

            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "schedule.alarms",
                Arguments(now.AddHours(1)),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True);
                Assert.That(File.Exists(stem + ".ps1"), Is.True);
                Assert.That(File.Exists(stem + ".fired"), Is.True);
            });
        }
        finally
        {
            Directory.Delete(dataRoot, recursive: true);
        }
    }

    private static string NewRoot()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-alarm-prune-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        return root;
    }

    private static JsonElement Arguments(DateTimeOffset due)
    {
        using JsonDocument document = JsonDocument.Parse(JsonSerializer.Serialize(new
        {
            action = "create",
            at = due.ToLocalTime().ToString("yyyy-MM-ddTHH:mm:ss", System.Globalization.CultureInfo.InvariantCulture),
            kind = "alarm",
            title = "Prueba",
        }));
        return document.RootElement.Clone();
    }

    // The script backend's process: diagnose answers the given task list (or fails when there is none),
    // schedule answers the task it was asked to register.
    private sealed class SchedulerRunner(IReadOnlyList<string>? liveTasks) : IExternalProcessRunner
    {
        internal List<string> Modes { get; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            List<string> list = arguments.ToList();
            string mode = list[list.IndexOf("-Mode") + 1];
            Modes.Add(mode);
            if (mode == "diagnose")
            {
                return ValueTask.FromResult(liveTasks is null
                    ? new ExternalProcessResult(1, string.Empty, "scheduler unavailable")
                    : new ExternalProcessResult(0, JsonSerializer.Serialize(new
                    {
                        version = 1,
                        ok = true,
                        tasks = liveTasks.Select(name => new { taskName = name, state = "Ready" }).ToArray(),
                    }), string.Empty));
            }

            int taskIndex = list.IndexOf("-TaskName");
            string taskName = taskIndex >= 0 ? list[taskIndex + 1] : string.Empty;
            return ValueTask.FromResult(new ExternalProcessResult(0, JsonSerializer.Serialize(new
            {
                version = 1,
                ok = true,
                effectObserved = true,
                taskName,
                state = "Ready",
                nextRunUtc = DateTimeOffset.UtcNow.AddHours(1).ToString("O"),
                authority = "windows_task_scheduler_postread",
            }), string.Empty));
        }
    }

    private static string Write(string root, string taskName, DateTimeOffset rang)
    {
        string stem = Path.Combine(root, taskName);
        File.WriteAllText(stem + ".ps1", "# ring");
        File.WriteAllText(stem + ".fired", rang.ToString("O"));
        File.SetLastWriteTimeUtc(stem + ".fired", rang.UtcDateTime);
        return stem;
    }
}
