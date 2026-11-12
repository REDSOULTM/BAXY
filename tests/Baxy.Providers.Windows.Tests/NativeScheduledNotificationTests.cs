using System.Globalization;
using System.Security;
using System.Text.Json;
using System.Xml.Linq;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using NUnit.Framework.Constraints;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M119: BAXY's alarms and reminders answered through the Task Scheduler COM API: the task registered is the one
/// Task Scheduler stored for the captured fixtures, and each mode answers its JSON line.
/// </summary>
[TestFixture]
public sealed class NativeScheduledNotificationTests
{
    // schedule takes the person's local time; seconds keep the trigger exact.
    private static string LocalAt(DateTimeOffset due) =>
        due.ToLocalTime().ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);

    private const string Sid = "S-1-5-21-1-2-3-1001";

    [TestCase("alarm", null, "once-alarm.xml")]
    [TestCase("reminder", null, "once-reminder.xml")]
    [TestCase("reminder", "daily", "daily-reminder.xml")]
    [TestCase("alarm", "hourly", "hourly-alarm.xml")]
    public async Task ScheduledTaskDefinitionIsTheRegisteredOne(
        string kind, string? recurrence, string fixture)
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(3).AddMilliseconds(437);
        string recurrenceJson = recurrence is null ? "" : $",\"recurrence\":\"{recurrence}\"";

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"{{kind}}","title":"Tomar agua"{{recurrenceJson}}}"""),
            CancellationToken.None);

        FakeTask task = scheduler.Tasks.Values.Single();
        string ring = Path.Combine(temporary.Path, "scheduled-notifications", task.Name + ".ps1");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(XNode.DeepEquals(
                    XElement.Parse(task.Xml!),
                    XElement.Parse(Golden(fixture, ring, StartBoundary(due)))),
                Is.True, task.Xml);
            Assert.That(receipt.Result?.GetProperty("taskName").GetString(), Is.EqualTo(task.Name));
            Assert.That(receipt.Result?.GetProperty("state").GetString(), Is.EqualTo("Ready"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_task_scheduler_postread"));
        });
    }

    [Test]
    public async Task TimerDurationKeepsTheWholeSecond()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddSeconds(90.75);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"reminder","title":"Temporizador de 90 segundos"}"""),
            CancellationToken.None);

        DateTimeOffset whole = new(due.Ticks - due.Ticks % TimeSpan.TicksPerSecond, due.Offset);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("nextRunUtc").GetString(),
                Is.EqualTo(whole.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture)));
            Assert.That(scheduler.Tasks.Values.Single().Xml, Does.Contain(
                "<StartBoundary>" + StartBoundary(due) + "</StartBoundary>"));
        });
    }

    [Test]
    public async Task ReminderTitleIsListedFromItsRingScript()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(5);
        await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"reminder","title":"Llamar a mamá & papá"}"""),
            CancellationToken.None);

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"list"}"""), CancellationToken.None);

        JsonElement item = listed.Result!.Value.GetProperty("notifications")[0];
        Assert.Multiple(() =>
        {
            Assert.That(listed.Verified, Is.True, listed.ErrorCode);
            Assert.That(item.GetProperty("kind").GetString(), Is.EqualTo("reminder"));
            Assert.That(item.GetProperty("title").GetString(), Is.EqualTo("Llamar a mamá & papá"));
            Assert.That(item.GetProperty("state").GetString(), Is.EqualTo("Ready"));
        });
    }

    // V5E060: «make it 6:45 instead» came as a create with no title, which the catalog allows; the provider required
    // one, threw, and the catch said the scheduler failed when it was never touched. With no title the notification
    // shows BAXY alone (no words added), it is scheduled and read back, and the result names no title.
    [Test]
    public async Task CreateWithoutTitleIsScheduledAndReadBack()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(4);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"alarm"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"list"}"""), CancellationToken.None);

        FakeTask task = scheduler.Tasks.Values.Single();
        string ring = File.ReadAllText(
            Path.Combine(temporary.Path, "scheduled-notifications", task.Name + ".ps1"));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("taskName").GetString(), Is.EqualTo(task.Name));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_task_scheduler_postread"));
            Assert.That(receipt.Result?.TryGetProperty("title", out _), Is.False);
            Assert.That(ring, Does.Not.Contain("$title"));
            Assert.That(listed.Verified, Is.True, listed.ErrorCode);
            Assert.That(listed.Result!.Value.GetProperty("notifications")[0].TryGetProperty("title", out _), Is.False);
        });
    }

    // An argument of the wrong type fails before any effect with its own code, never as a scheduler failure.
    [TestCase("""{"action":"create","inMinutes":30,"kind":"alarm","title":5}""", "notification_title_invalid")]
    [TestCase("""{"action":"create","inMinutes":30,"kind":"alarm","title":"   "}""", "notification_title_invalid")]
    [TestCase("""{"action":"create","inMinutes":30,"kind":"alarm","recurrence":1}""", "notification_recurrence_invalid")]
    public async Task AnInvalidArgumentFailsBeforeTheSchedulerWithItsOwnCode(string arguments, string code)
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json(arguments), CancellationToken.None);

        string root = Path.Combine(temporary.Path, "scheduled-notifications");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(scheduler.Tasks, Is.Empty);
            Assert.That(Directory.Exists(root) && Directory.EnumerateFiles(root).Any(), Is.False);
        });
    }

    [Test]
    public async Task CancelByClockRemovesTheBoundTaskAndVerifiesItsAbsence()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = new DateTimeOffset(DateTime.Today.AddDays(1).AddHours(17)).ToUniversalTime();
        ExternalCapabilityReceipt scheduled = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"alarm","title":"Alarma"}"""),
            CancellationToken.None);
        string taskName = scheduled.Result!.Value.GetProperty("taskName").GetString()!;

        ExternalCapabilityReceipt canceled = await adapter.InvokeAsync(
            "schedule.alarms",
            Json("""{"action":"cancel","kind":"alarm","at":"17:00"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(canceled.Verified, Is.True, canceled.ErrorCode);
            Assert.That(canceled.EffectObserved, Is.True);
            Assert.That(canceled.Result?.GetProperty("taskName").GetString(), Is.EqualTo(taskName));
            Assert.That(canceled.Result?.GetProperty("canceled").GetBoolean(), Is.True);
            Assert.That(canceled.Result?.GetProperty("expectedNextRunUtc").GetString(),
                Is.EqualTo(due.ToString("O", CultureInfo.InvariantCulture)));
            Assert.That(scheduler.Tasks, Is.Empty);
        });
    }

    [Test]
    public async Task SchedulerUnavailableFailsBeforeAnyEffectAndSaysSo()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler
        {
            OpenFailure = new TaskSchedulerHostException("task_scheduler_connect_failed:0x80070005"),
        };
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(1);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"alarm","title":"Prueba"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_scheduler_unavailable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(scheduler.Tasks, Is.Empty);
        });
    }

    [Test]
    public async Task RegisterFailureChangedNothingAndSaysSo()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler
        {
            RegisterFailure = new TaskSchedulerHostException("task_register_failed:0x80041318"),
        };
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(1);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"reminder","title":"Prueba"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_scheduler_unavailable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    // Renew al máximo (w8): a schedule that fails before its Register (the ring script gone, the due time passed
    // meanwhile) changed nothing and says so with its cause, never a bare process failure read as «may have changed».
    [TestCase("ring_script_missing", 1)]
    [TestCase("due_time_not_future", -1)]
    public async Task AScheduleThatFailsBeforeRegisteringSaysNothingChanged(string cause, int hours)
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        string ring = Path.Combine(temporary.Path, "ring.ps1");
        if (cause != "ring_script_missing")
            File.WriteAllText(ring, "# ring");
        var backend = new NativeScheduledNotificationBackend(scheduler);

        ExternalProcessResult result = await backend.RunAsync(
            new ScheduledNotificationRequest("schedule", "alarm")
            {
                TaskName = TaskName("Alarm", 'a'),
                DueUtc = DateTimeOffset.UtcNow.AddHours(hours).ToString("O"),
                RingScriptPath = ring,
            },
            CancellationToken.None);

        using JsonDocument line = JsonDocument.Parse(result.Output);
        Assert.Multiple(() =>
        {
            Assert.That(result.ExitCode, Is.Zero);
            Assert.That(line.RootElement.GetProperty("ok").GetBoolean(), Is.False);
            Assert.That(line.RootElement.GetProperty("effectBoundaryCrossed").GetBoolean(), Is.False);
            Assert.That(line.RootElement.GetProperty("error").GetString(), Is.EqualTo(cause));
            Assert.That(scheduler.Tasks, Is.Empty);
        });
    }

    // Auditoría final 2: the diagnosis reads what each ring wrote, not only how many rang.
    [Test]
    public async Task DiagnosisReadsWhatEachRingWrote()
    {
        using TemporaryDirectory temporary = new();
        string alarms = Path.Combine(temporary.Path, "scheduled-notifications");
        Directory.CreateDirectory(alarms);
        string shown = Path.Combine(alarms, TaskName("Alarm", 'a') + ".fired");
        string hidden = Path.Combine(alarms, TaskName("Reminder", 'b') + ".fired");
        await File.WriteAllTextAsync(shown, """{"rangUtc":"2026-10-14T07:00:00.0000000+00:00","notificationShown":true,"sound":"wav"}""");
        await File.WriteAllTextAsync(hidden, """{"rangUtc":"2026-10-15T07:00:00.0000000+00:00","notificationShown":false,"sound":"beep"}""");
        File.SetLastWriteTimeUtc(shown, DateTime.UtcNow.AddDays(-1));
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, new FakeTaskScheduler());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"diagnose"}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("firedReceiptCount").GetInt32(), Is.EqualTo(2));
            Assert.That(result.GetProperty("firedNotShownCount").GetInt32(), Is.EqualTo(1));
            Assert.That(result.GetProperty("healthy").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("firedReceipts")[0].GetProperty("taskName").GetString(),
                Is.EqualTo(TaskName("Reminder", 'b')));
            Assert.That(result.GetProperty("firedReceipts")[0].GetProperty("notificationShown").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("firedReceipts")[0].GetProperty("sound").GetString(), Is.EqualTo("beep"));
        });
    }

    // ALR1: a ring the open App took wrote rungBy app and no notification: it rang, with the App's card, and it is not a
    // notification Windows failed to show.
    [Test]
    public async Task DiagnosisCountsARingTheAppRangAsRung()
    {
        using TemporaryDirectory temporary = new();
        string alarms = Path.Combine(temporary.Path, "scheduled-notifications");
        Directory.CreateDirectory(alarms);
        await File.WriteAllTextAsync(Path.Combine(alarms, TaskName("Alarm", 'c') + ".fired"),
            """{"rangUtc":"2026-11-08T07:00:00.0000000+00:00","rungBy":"app"}""");
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, new FakeTaskScheduler());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"diagnose"}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("firedNotShownCount").GetInt32(), Is.EqualTo(0));
            Assert.That(result.TryGetProperty("firedShownUnreadCount", out _), Is.False);
            Assert.That(result.GetProperty("firedReceipts")[0].GetProperty("rungBy").GetString(), Is.EqualTo("app"));
        });
    }

    [Test]
    public async Task DiagnosisSaysASchedulerThatDoesNotAnswer()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler
        {
            OpenFailure = new TaskSchedulerHostException("task_scheduler_connect_failed:0x800706BA"),
        };
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"diagnose"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result!.Value.GetProperty("schedulerRunning").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("healthy").GetBoolean(), Is.False);
            Assert.That(receipt.Result!.Value.TryGetProperty("taskCount", out _), Is.False);
            Assert.That(receipt.Result!.Value.TryGetProperty("tasks", out _), Is.False);
        });
    }

    // A scheduler that does not answer listed nothing: the list fails and says why, never an empty list.
    [Test]
    public async Task AListFromASchedulerThatDoesNotAnswerIsNoEmptyList()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler
        {
            OpenFailure = new TaskSchedulerHostException("task_scheduler_connect_failed:0x800706BA"),
        };
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"list"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_scheduler_unavailable"));
            Assert.That(receipt.Result, Is.Null);
        });
    }

    // Its tasks unread, a scheduler that does not answer proves no task gone: an old ring script stays.
    [Test]
    public async Task ASchedulerThatDoesNotAnswerLetsNoRingScriptGo()
    {
        using TemporaryDirectory temporary = new();
        string alarms = Path.Combine(temporary.Path, "scheduled-notifications");
        Directory.CreateDirectory(alarms);
        string stem = Path.Combine(alarms, TaskName("Reminder", 'd'));
        await File.WriteAllTextAsync(stem + ".ps1", "# ring");
        await File.WriteAllTextAsync(stem + ".fired", """{"rangUtc":"2026-08-01T07:00:00.0000000+00:00"}""");
        File.SetLastWriteTimeUtc(stem + ".fired", DateTime.UtcNow.AddDays(-45));
        var scheduler = new FakeTaskScheduler
        {
            OpenFailure = new TaskSchedulerHostException("task_scheduler_connect_failed:0x800706BA"),
        };
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.UtcNow.AddHours(1))}}","kind":"reminder","title":"Prueba"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_scheduler_unavailable"));
            Assert.That(File.Exists(stem + ".ps1"), Is.True);
            Assert.That(File.Exists(stem + ".fired"), Is.True);
        });
    }

    // BAXY Renew (notebook): through the handler the model's call goes through, a list, a diagnosis and a cancel
    // with nothing pending are done with what they read (before, every one came back external_verification_failed
    // with no result).
    [Test]
    public async Task TheHandlerReturnsTheListTheSchedulerReadBack()
    {
        using TemporaryDirectory temporary = new();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, new FakeTaskScheduler());
        await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.UtcNow.AddHours(2))}}","kind":"reminder","title":"Regar"}"""),
            CancellationToken.None);

        OperationOutcome outcome = await Handle(adapter, """{"action":"list"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(outcome.Result!.Value.GetProperty("notifications")[0].GetProperty("title").GetString(),
                Is.EqualTo("Regar"));
        });
    }

    [Test]
    public async Task TheHandlerReturnsTheDiagnosisTheSchedulerReadBack()
    {
        using TemporaryDirectory temporary = new();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, new FakeTaskScheduler());

        OperationOutcome outcome = await Handle(adapter, """{"action":"diagnose"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("authority").GetString(),
                Is.EqualTo("windows_task_scheduler_notification_diagnostics_postread"));
        });
    }

    [Test]
    public async Task TheHandlerSaysNothingWasPendingToCancel()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel","kind":"alarm"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("canceled").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("pendingFound").GetBoolean(), Is.False);
            Assert.That(scheduler.Tasks, Is.Empty);
        });
    }

    [Test]
    public async Task TheHandlerReportsACancelThatDeletedThePendingOne()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.UtcNow.AddHours(2))}}","kind":"alarm","title":"Despertar"}"""),
            CancellationToken.None);

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel","kind":"alarm"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("canceled").GetBoolean(), Is.True);
            Assert.That(outcome.Result!.Value.TryGetProperty("pendingFound", out _), Is.False);
            Assert.That(scheduler.Tasks, Is.Empty);
        });
    }

    // Renew al máximo (w9): a cancel by kind canceled the newest of that kind and the result named none of it. The one
    // pending is canceled by its identity and named (title and local time), so the model can say which.
    [Test]
    public async Task ACancelByKindNamesTheOneItCanceled()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(2);
        await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"alarm","title":"Despertar"}"""),
            CancellationToken.None);

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel","kind":"alarm"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("title").GetString(), Is.EqualTo("Despertar"));
            Assert.That(outcome.Result!.Value.GetProperty("nextRunLocal").GetString(), Is.EqualTo(
                due.ToLocalTime().ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture)));
            Assert.That(outcome.Result!.Value.GetProperty("authority").GetString(),
                Is.EqualTo("windows_task_scheduler_exact_identity_absence_postread"));
            Assert.That(scheduler.Tasks, Is.Empty);
        });
    }

    // Renew al máximo (w9): with several of the kind pending, the newest was canceled in silence. None is canceled now:
    // the failure lists them (title and local time each), and (aid cancel_scope) says at names the one.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task ACancelByKindWithSeveralPendingCancelsNoneAndListsThem(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        foreach ((int hours, string title) in new[] { (2, "Despertar"), (3, "Pastilla") })
        {
            await adapter.InvokeAsync(
                "schedule.alarms",
                Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.UtcNow.AddHours(hours))}}","kind":"alarm","title":"{{title}}"}"""),
                CancellationToken.None);
        }

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel","kind":"alarm"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("notification_cancel_ambiguous"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("pendingCount").GetInt32(), Is.EqualTo(2));
            Assert.That(outcome.Result!.Value.GetProperty("pending")[0].GetProperty("title").GetString(),
                Is.EqualTo("Despertar"));
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.EqualTo(hint));
            Assert.That(scheduler.Tasks, Has.Count.EqualTo(2));
        });
    }

    // Renew al máximo (w5): a cancel with no kind and no time looked only among reminders, so the one alarm pending
    // was «nothing pending» (a done call the model reads as «la cancelé») and kept ringing. It is canceled now.
    [Test]
    public async Task ACancelWithNoKindCancelsTheOneAlarmPending()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.UtcNow.AddHours(2))}}","kind":"alarm","title":"Despertar"}"""),
            CancellationToken.None);

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("kind").GetString(), Is.EqualTo("alarm"));
            Assert.That(outcome.Result!.Value.GetProperty("canceled").GetBoolean(), Is.True);
            Assert.That(scheduler.Tasks, Is.Empty);
        });
    }

    // Renew al máximo (w5): with an alarm and a reminder pending and no kind, nothing is canceled before the person's
    // words name one: the failure carries both, and (aid cancel_scope) says nothing was canceled.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task ACancelWithNoKindAndBothKindsPendingCancelsNothingAndListsThem(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        foreach (string kind in new[] { "alarm", "reminder" })
        {
            await adapter.InvokeAsync(
                "schedule.alarms",
                Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.UtcNow.AddHours(2))}}","kind":"{{kind}}","title":"{{kind}}"}"""),
                CancellationToken.None);
        }

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("notification_kind_ambiguous"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("pending").GetArrayLength(), Is.EqualTo(2));
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.EqualTo(hint));
            Assert.That(scheduler.Tasks, Has.Count.EqualTo(2));
        });
    }

    // Renew al máximo (w5): a cancel that found nothing pending says, as a sentence (aid cancel_scope), that nothing
    // was canceled; «canceled:false» on a done call was read as «la cancelé».
    [TestCase("""{"action":"cancel","kind":"alarm"}""", "nothing was canceled: no alarm set by BAXY is pending")]
    [TestCase("""{"action":"cancel"}""", "nothing was canceled: no alarm or reminder set by BAXY is pending")]
    public async Task ACancelWithNothingPendingSaysNothingWasCanceled(string arguments, string next)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use("all");
        using TemporaryDirectory temporary = new();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, new FakeTaskScheduler());

        OperationOutcome outcome = await Handle(adapter, arguments);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("pendingFound").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(next));
        });
    }

    // ALR5 (B4): «recuérdamelo después de almuerzo» while a reminder rang went as a cancel. One that rang once is no
    // longer pending, so «the only one pending» was another reminder, and that one was deleted. While one of the kind
    // rings a cancel with no time deletes nothing and says what rings and what answers it.
    [TestCase("""{"action":"cancel"}""")]
    [TestCase("""{"action":"cancel","kind":"reminder"}""")]
    public async Task ACancelWithNoTimeWhileOneOfTheKindRingsDeletesNothingAndSaysWhatRings(string arguments)
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.UtcNow.AddHours(2))}}","kind":"reminder","title":"Dentista"}"""),
            CancellationToken.None);
        using Mutex app = Rings(temporary, TaskName("Reminder", 'a'), "comprar pan", "15:00");

        OperationOutcome outcome = await Handle(adapter, arguments);

        JsonElement result = outcome.Result ?? default;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("notification_cancel_rings_now"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(scheduler.Tasks, Has.Count.EqualTo(1));
            Assert.That(Told(result, "canceled")?.GetBoolean(), Is.False);
            Assert.That(Told(result, "ringingNow")?[0].GetProperty("title").GetString(), Is.EqualTo("comprar pan"));
            Assert.That(Told(result, "next")?.GetString(), Does.StartWith("nothing was canceled: "));
        });
    }

    // What rings is of another kind than the one named: the cancel is of one that is set, as before.
    [Test]
    public async Task ACancelOfTheOtherKindWhileOneRingsCancelsTheOnePending()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.UtcNow.AddHours(2))}}","kind":"alarm","title":"Despertar"}"""),
            CancellationToken.None);
        using Mutex app = Rings(temporary, TaskName("Reminder", 'a'), "comprar pan", "15:00");

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel","kind":"alarm"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("canceled").GetBoolean(), Is.True);
            Assert.That(scheduler.Tasks, Is.Empty);
        });
    }

    // A time names one that is set: the one at that time is canceled while another rings, but never the one ringing
    // (a daily one is pending for its next time while it rings).
    [TestCase(false)]
    [TestCase(true)]
    public async Task ACancelAtATimeWhileOneRingsCancelsTheOneSetThenButNeverTheOneRinging(bool itRings)
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = new DateTimeOffset(DateTime.Today.AddDays(1).AddHours(17)).ToUniversalTime();
        ExternalCapabilityReceipt set = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"alarm","title":"Pastilla","recurrence":"daily"}"""),
            CancellationToken.None);
        string taskName = set.Result!.Value.GetProperty("taskName").GetString()!;
        using Mutex app = Rings(temporary, itRings ? taskName : TaskName("Reminder", 'a'), "Pastilla", "17:00");

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel","at":"17:00"}""");

        JsonElement result = outcome.Result ?? default;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.EqualTo(!itRings), outcome.ErrorCode);
            Assert.That(outcome.ErrorCode, Is.EqualTo(itRings ? "notification_cancel_rings_now" : null));
            Assert.That(itRings && outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(scheduler.Tasks, Has.Count.EqualTo(itRings ? 1 : 0));
            Assert.That(Told(result, "canceled")?.GetBoolean(), Is.EqualTo(!itRings));
            Assert.That(Told(result, "next")?.GetString(),
                itRings ? Does.StartWith("nothing was canceled: that one rings now") : (IResolveConstraint)Is.Null);
        });
    }

    // ALR5 (B4): «recuérdamelo a las once» while it rang went as a cancel at 11:00; the bare «not found» was followed by
    // «te lo recordaré a las once» with nothing set. While something rings the failure says nothing was canceled nor set
    // and that it still rings; with nothing ringing it is as it was.
    [TestCase(true)]
    [TestCase(false)]
    public async Task ACancelAtATimeNoneIsSetForSaysWhileOneRingsThatNothingWasSetAndItRingsOn(bool rings)
    {
        using TemporaryDirectory temporary = new();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, new FakeTaskScheduler());
        using Mutex? app = rings ? Rings(temporary, TaskName("Reminder", 'a'), "comprar pan", "09:00") : null;

        OperationOutcome outcome = await Handle(adapter, """{"action":"cancel","at":"11:00"}""");

        JsonElement result = outcome.Result ?? default;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("notification_clock_not_found"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(Told(result, "canceled")?.GetBoolean(), Is.EqualTo(rings ? (bool?)false : null));
            Assert.That(Told(result, "ringingNow")?.GetArrayLength(), Is.EqualTo(rings ? (int?)1 : null));
            Assert.That(Told(result, "next")?.GetString(), rings
                ? Does.StartWith("nothing was canceled and nothing was set: none is set for 11:00. What rings now")
                : (IResolveConstraint)Is.Null);
        });
    }

    private static JsonElement? Told(JsonElement result, string name) =>
        result.ValueKind == JsonValueKind.Object && result.TryGetProperty(name, out JsonElement value) ? value : null;

    // An open App holding this data root's rings (its mutex) with one ring taken, as the hand-over leaves it.
    private static Mutex Rings(TemporaryDirectory temporary, string taskName, string? title, string clock)
    {
        string alarms = AlarmRingHandoff.Folder(temporary.Path);
        Directory.CreateDirectory(alarms);
        var held = new Mutex(false, AlarmRingHandoff.MutexName(alarms));
        string due = Path.Combine(alarms, taskName + AlarmRingHandoff.DueExtension);
        File.WriteAllText(due, JsonSerializer.Serialize(new Dictionary<string, string?>
        {
            ["rangUtc"] = DateTimeOffset.UtcNow.ToString("O"),
            ["title"] = title,
            ["clock"] = clock,
        }));
        Assert.That(AlarmRingHandoff.Take(due), Is.Not.Null);
        return held;
    }

    private static ValueTask<OperationOutcome> Handle(WindowsScheduledNotificationAdapter adapter, string arguments) =>
        new ExternalCapabilityHandler("schedule.alarms", new AdapterProvider(adapter)).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", Json(arguments)), CancellationToken.None);

    private sealed class AdapterProvider(WindowsScheduledNotificationAdapter adapter) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            adapter.InvokeAsync(operation, arguments, cancellationToken);
    }

    [Test]
    public async Task DeletionFailureAfterTheAttemptIsAnAmbiguousFailure()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(1);
        await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(due)}}","kind":"reminder","title":"Prueba"}"""),
            CancellationToken.None);
        scheduler.DeleteFailure = new TaskSchedulerHostException("task_delete_failed:0x800706BA");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"cancel","kind":"reminder"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_scheduler_process_failed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    private static WindowsScheduledNotificationAdapter Adapter(
        TemporaryDirectory temporary, FakeTaskScheduler scheduler) =>
        new(temporary.Path, new NativeScheduledNotificationBackend(scheduler));

    private static string Golden(string fixture, string ringScript, string startBoundary)
    {
        string text = File.ReadAllText(Path.Combine(
            AppContext.BaseDirectory, "Fixtures", "ScheduledNotification", fixture));
        return text
            .Replace("{USER_SID}", Sid, StringComparison.Ordinal)
            .Replace("{RING_SCRIPT}", SecurityElement.Escape(ringScript), StringComparison.Ordinal)
            .Replace("{START_BOUNDARY}", startBoundary, StringComparison.Ordinal);
    }

    private static string StartBoundary(DateTimeOffset due)
    {
        DateTimeOffset local = due.ToLocalTime();
        return local.ToString("yyyy-MM-dd'T'HH:mm:ss", CultureInfo.InvariantCulture)
            + local.ToString("zzz", CultureInfo.InvariantCulture);
    }

    private static string TaskName(string kind, char digit) => TaskName(kind, new string(digit, 32));

    private static string TaskName(string kind, string id) => $"BAXY-{kind}-{id}";

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private sealed class FakeTask(string name)
    {
        internal string Name { get; } = name;
        internal string? Xml { get; set; }
        internal int State { get; set; } = 3;
        internal DateTime? NextRunLocal { get; set; }
        internal DateTime? LastRunLocal { get; set; } = new DateTime(1999, 11, 30);
        internal int LastTaskResult { get; set; } = 267011;
    }

    /// <summary>An in-memory Task Scheduler folder that computes the next run from the trigger it gets.</summary>
    private sealed class FakeTaskScheduler : ITaskSchedulerHost
    {
        internal Dictionary<string, FakeTask> Tasks { get; } = new(StringComparer.OrdinalIgnoreCase);
        internal string Sid { get; set; } = NativeScheduledNotificationTests.Sid;
        internal int? Toast { get; set; }
        internal Exception? OpenFailure { get; set; }
        internal Exception? RegisterFailure { get; set; }
        internal Exception? DeleteFailure { get; set; }

        public ITaskSchedulerSession Open() =>
            OpenFailure is null ? new Session(this) : throw OpenFailure;

        public int? ToastsEnabledSetting() => Toast;

        public string CurrentUserSid() => Sid;

        private sealed class Session(FakeTaskScheduler owner) : ITaskSchedulerSession
        {
            public IReadOnlyList<string> TaskNames() => owner.Tasks.Keys.ToList();

            public IReadOnlyList<ScheduledTaskSnapshot> Read(string namePrefix) =>
                TaskNames().Where(name => name.StartsWith(namePrefix, StringComparison.OrdinalIgnoreCase))
                    .Select(name => Find(name)!).ToList();

            public ScheduledTaskSnapshot? Find(string name) =>
                owner.Tasks.TryGetValue(name, out FakeTask? task)
                    ? new ScheduledTaskSnapshot(task.Name, task.State, task.NextRunLocal, task.LastRunLocal, task.LastTaskResult)
                    : null;

            public void Register(string name, string xml)
            {
                if (owner.RegisterFailure is not null) throw owner.RegisterFailure;
                XNamespace ns = "http://schemas.microsoft.com/windows/2004/02/mit/task";
                string start = XElement.Parse(xml).Descendants(ns + "StartBoundary").Single().Value;
                DateTime next = DateTimeOffset.Parse(start, CultureInfo.InvariantCulture).LocalDateTime;
                owner.Tasks[name] = new FakeTask(name)
                {
                    Xml = xml,
                    NextRunLocal = DateTime.SpecifyKind(next, DateTimeKind.Unspecified),
                };
            }

            public void Delete(string name)
            {
                if (owner.DeleteFailure is not null) throw owner.DeleteFailure;
                if (!owner.Tasks.Remove(name)) throw new TaskSchedulerHostException("task_delete_failed:0x80070002");
            }

            public void Dispose()
            {
            }
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-m119-tests-" + Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }
}
