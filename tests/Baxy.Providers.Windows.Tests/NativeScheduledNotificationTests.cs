using System.Diagnostics;
using System.Globalization;
using System.Security;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml.Linq;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M119: notification.* answered through the Task Scheduler COM API instead of a powershell.exe
/// per call. The native backend must register the task WindowsScheduledNotification.ps1 registers
/// and print the JSON line the script prints for the same scheduler state.
/// </summary>
[TestFixture]
public sealed class NativeScheduledNotificationTests
{
    private const string Sid = "S-1-5-21-1-2-3-1001";

    [TestCase("alarm", null, "once-alarm.xml")]
    [TestCase("reminder", null, "once-reminder.xml")]
    [TestCase("reminder", "daily", "daily-reminder.xml")]
    [TestCase("alarm", "hourly", "hourly-alarm.xml")]
    public async Task ScheduledTaskDefinitionIsTheOneTheScriptRegisters(
        string kind, string? recurrence, string fixture)
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        var runner = new RecordingRunner();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler, runner);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(3).AddMilliseconds(437);
        string recurrenceJson = recurrence is null ? "" : $",\"recurrence\":\"{recurrence}\"";

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due:O}}","kind":"{{kind}}","title":"Tomar agua"{{recurrenceJson}}}"""),
            CancellationToken.None);

        FakeTask task = scheduler.Tasks.Values.Single();
        string ring = Path.Combine(temporary.Path, "scheduled-notifications", task.Name + ".ps1");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(runner.Calls, Is.Zero, "the script is not run when the scheduler answers");
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
    public async Task TimerDurationKeepsTheWholeSecondTheScriptKeeps()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler, new RecordingRunner());
        DateTimeOffset due = DateTimeOffset.UtcNow.AddSeconds(90.75);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due:O}}","kind":"reminder","title":"Temporizador de 90 segundos"}"""),
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
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler, new RecordingRunner());
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(5);
        await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due:O}}","kind":"reminder","title":"Llamar a mamá & papá"}"""),
            CancellationToken.None);

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "notification.list", Json("{}"), CancellationToken.None);

        JsonElement item = listed.Result!.Value.GetProperty("notifications")[0];
        Assert.Multiple(() =>
        {
            Assert.That(listed.Verified, Is.True, listed.ErrorCode);
            Assert.That(item.GetProperty("kind").GetString(), Is.EqualTo("reminder"));
            Assert.That(item.GetProperty("title").GetString(), Is.EqualTo("Llamar a mamá & papá"));
            Assert.That(item.GetProperty("state").GetString(), Is.EqualTo("Ready"));
        });
    }

    [Test]
    public async Task CancelByClockRemovesTheBoundTaskAndVerifiesItsAbsence()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler, new RecordingRunner());
        DateTimeOffset due = new DateTimeOffset(DateTime.Today.AddDays(1).AddHours(17)).ToUniversalTime();
        ExternalCapabilityReceipt scheduled = await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due:O}}","kind":"alarm","title":"Alarma"}"""),
            CancellationToken.None);
        string taskName = scheduled.Result!.Value.GetProperty("taskName").GetString()!;

        ExternalCapabilityReceipt canceled = await adapter.InvokeAsync(
            "notification.cancel.at",
            Json("""{"kind":"alarm","hour":5,"period":"pm"}"""),
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
    public async Task SchedulerUnavailableFallsBackToTheScriptWithADiagnostic()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler
        {
            OpenFailure = new TaskSchedulerHostException("task_scheduler_connect_failed:0x80070005"),
        };
        var runner = new RecordingRunner();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler, runner);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(1);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due:O}}","kind":"alarm","title":"Prueba"}"""),
            CancellationToken.None);

        string diagnostic = Path.Combine(temporary.Path, "notification-scheduler-fallback.jsonl");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(runner.Calls, Is.EqualTo(1));
            Assert.That(runner.Arguments, Does.Contain("schedule"));
            Assert.That(receipt.Result?.GetProperty("taskName").GetString(), Is.EqualTo(runner.TaskName));
            Assert.That(File.Exists(diagnostic), Is.True);
            Assert.That(File.ReadAllText(diagnostic), Does.Contain("task_scheduler_connect_failed"));
        });
    }

    [Test]
    public async Task RegisterFailureChangedNothingSoTheScriptIsAsked()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler
        {
            RegisterFailure = new TaskSchedulerHostException("task_register_failed:0x80041318"),
        };
        var runner = new RecordingRunner();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler, runner);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(1);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due:O}}","kind":"reminder","title":"Prueba"}"""),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.That(runner.Calls, Is.EqualTo(1));
    }

    [Test]
    public async Task DeletionFailureAfterTheAttemptIsNeverRetriedByTheScript()
    {
        using TemporaryDirectory temporary = new();
        var scheduler = new FakeTaskScheduler();
        var runner = new RecordingRunner();
        WindowsScheduledNotificationAdapter adapter = Adapter(temporary, scheduler, runner);
        DateTimeOffset due = DateTimeOffset.UtcNow.AddHours(1);
        await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due:O}}","kind":"reminder","title":"Prueba"}"""),
            CancellationToken.None);
        scheduler.DeleteFailure = new TaskSchedulerHostException("task_delete_failed:0x800706BA");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.cancel.latest", Json("""{"kind":"reminder"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_scheduler_process_failed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(runner.Calls, Is.Zero);
        });
    }

    // The script itself, with the scheduler cmdlets replaced by functions over the same state the
    // fake scheduler holds: both must print the same JSON (nothing real is read or removed).
    [TestCase("resolve-at", "alarm", "-Hour 5 -Minute 0 -Period pm", "single")]
    [TestCase("resolve-at", "alarm", "-Hour 6 -Minute 45", "ambiguous")]
    [TestCase("resolve-at", "reminder", "-Hour 9 -Minute 15", "none")]
    [TestCase("cancel-exact", "alarm", "", "exact")]
    [TestCase("cancel-exact", "alarm", "", "changed")]
    [TestCase("cancel-exact", "alarm", "", "missing")]
    [TestCase("cancel", "reminder", "", "latest")]
    [TestCase("cancel", "alarm", "", "latest-none")]
    [TestCase("diagnose", "reminder", "", "diagnose")]
    public async Task NativeAnswerEqualsTheScriptAnswerForTheSameSchedulerState(
        string mode, string kind, string extra, string scenario)
    {
        using TemporaryDirectory temporary = new();
        string alarmRoot = Path.Combine(temporary.Path, "scheduled-notifications");
        Directory.CreateDirectory(alarmRoot);
        DateTime tomorrow = DateTime.Today.AddDays(1);
        string ownAlarm = TaskName("Alarm", 'a');
        string ownAlarmEarly = TaskName("Alarm", 'b');
        string ownAlarmEarlyTwin = TaskName("Alarm", 'c');
        string otherRunAlarm = TaskName("Alarm", 'd');
        string ownReminderFirst = TaskName("Reminder", 'e');
        string ownReminderLast = TaskName("Reminder", 'f');
        string rangReminder = TaskName("Reminder", '1');
        var tasks = new List<SpecTask>
        {
            new(ownAlarm, 3, tomorrow.AddHours(17), new DateTime(1999, 11, 30), 267011),
            new(ownAlarmEarly, 3, tomorrow.AddHours(6).AddMinutes(45), new DateTime(1999, 11, 30), 267011),
            new(ownAlarmEarlyTwin, 3, tomorrow.AddHours(18).AddMinutes(45), new DateTime(1999, 11, 30), 267011),
            new(otherRunAlarm, 3, tomorrow.AddHours(17), new DateTime(1999, 11, 30), 267011),
            new(ownReminderFirst, 3, tomorrow.AddHours(9), new DateTime(1999, 11, 30), 267011),
            new(ownReminderLast, 3, tomorrow.AddHours(10), new DateTime(1999, 11, 30), 267011),
            new(rangReminder, 3, null, DateTime.Today.AddHours(8), 0),
            new(TaskName("Reminder", '2'), 1, null, DateTime.Today.AddHours(7), unchecked((int)0x80070002)),
            new("OneDrive Standalone Update Task", 3, tomorrow.AddHours(1), DateTime.Today, 0),
        };
        DateTime stamp = DateTime.UtcNow.AddMinutes(-30);
        foreach (string own in new[] { ownAlarm, ownAlarmEarly, ownAlarmEarlyTwin, rangReminder, ownReminderFirst, ownReminderLast })
        {
            string ring = Path.Combine(alarmRoot, own + ".ps1");
            await File.WriteAllTextAsync(ring, "# ring");
            File.SetLastWriteTimeUtc(ring, stamp = stamp.AddMinutes(1));
        }
        await File.WriteAllTextAsync(Path.Combine(alarmRoot, rangReminder + ".fired"), "fired");
        string arguments = $"-Mode {mode} -Kind {kind} {extra}";
        var request = new ScheduledNotificationRequest(mode, kind) { AlarmRoot = alarmRoot };
        Match hour = Regex.Match(extra, @"-Hour (\d+) -Minute (\d+)(?: -Period (\w+))?");
        if (hour.Success)
        {
            request = request with
            {
                Hour = int.Parse(hour.Groups[1].Value, CultureInfo.InvariantCulture),
                Minute = int.Parse(hour.Groups[2].Value, CultureInfo.InvariantCulture),
                Period = hour.Groups[3].Success ? hour.Groups[3].Value : null,
            };
        }
        if (mode == "cancel-exact")
        {
            string name = scenario == "missing" ? TaskName("Alarm", '9') : ownAlarm;
            DateTimeOffset expected = new DateTimeOffset(tomorrow.AddHours(scenario == "changed" ? 18 : 17))
                .ToUniversalTime();
            request = request with { AlarmRoot = null, TaskName = name, DueUtc = expected.ToString("O", CultureInfo.InvariantCulture) };
            arguments = $"-Mode {mode} -Kind {kind} -TaskName {name} -DueUtc {request.DueUtc}";
        }
        else
        {
            arguments += $" -AlarmRoot '{alarmRoot.Replace("'", "''", StringComparison.Ordinal)}'";
        }
        const int toast = 1;

        string script = await RunStubbedScriptAsync(tasks, toast, arguments);
        var scheduler = FakeTaskScheduler.From(tasks, toast);
        var backend = new NativeScheduledNotificationBackend(
            scheduler, new ThrowingBackend(Path.Combine(temporary.Path, "fallback.jsonl")),
            Path.Combine(temporary.Path, "fallback.jsonl"));
        ExternalProcessResult native = await backend.RunAsync(request, CancellationToken.None);

        Assert.That(native.ExitCode, Is.Zero, native.Error);
        string expectedLine = script.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).Last();
        string nativeLine = native.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).Last();
        Assert.That(Canonical(nativeLine), Is.EqualTo(Canonical(expectedLine)), nativeLine);
        if (scenario is "exact" or "latest")
            Assert.That(scheduler.Deleted, Is.EqualTo(new[] { scenario == "exact" ? ownAlarm : ownReminderLast }));
    }

    /// <summary>
    /// Opt-in: the real Task Scheduler, in a test folder that is removed at the end. The script
    /// (with -TaskPath pointed at that folder) and the native backend register the same request;
    /// the stored task XML must be equal, and both calls are timed.
    /// </summary>
    [Test]
    [Explicit("Registers real tasks in a unique Task Scheduler test folder and removes them.")]
    public void RealSchedulerStoresTheSameTaskForScriptAndNative()
    {
        using TemporaryDirectory temporary = new();
        string script = Path.Combine(AppContext.BaseDirectory, "WindowsScheduledNotification.ps1");
        string folderName = "BAXY-M119-Test-" + Guid.NewGuid().ToString("N");
        string folderPath = "\\" + folderName;
        string scriptTaskPath = folderPath + "\\"; // Register-ScheduledTask -TaskPath ends with a backslash
        string patched = Path.Combine(temporary.Path, "patched.ps1");
        string source = File.ReadAllText(script);
        string patchedText = source
            .Replace("    Register-ScheduledTask `", "    Register-ScheduledTask -TaskPath $env:M119_TASK_PATH `", StringComparison.Ordinal)
            .Replace("    $info = Get-ScheduledTaskInfo -TaskName $TaskName\n",
                "    $info = Get-ScheduledTaskInfo -TaskPath $env:M119_TASK_PATH -TaskName $TaskName\n", StringComparison.Ordinal);
        Assert.That(patchedText, Does.Contain("-TaskPath $env:M119_TASK_PATH -TaskName"));
        File.WriteAllText(patched, patchedText);
        string alarmRoot = Path.Combine(temporary.Path, "scheduled-notifications");
        Directory.CreateDirectory(alarmRoot);

        using ITaskSchedulerSession comApartment = new WindowsTaskSchedulerHost().Open();
        ITaskSchedulerService service = WindowsTaskSchedulerHost.Connect();
        ITaskSchedulerFolder? root = null;
        ITaskSchedulerFolder? folder = null;
        var report = new StringBuilder();
        try
        {
            WindowsTaskSchedulerHost.ThrowOnFailure(service.GetFolder("\\", out root), "root");
            WindowsTaskSchedulerHost.ThrowOnFailure(root!.CreateFolder(folderName, default, out folder), "create");
            var native = new NativeScheduledNotificationBackend(
                new WindowsTaskSchedulerHost(folderPath), new ThrowingBackend(Path.Combine(temporary.Path, "fallback.jsonl")),
                Path.Combine(temporary.Path, "fallback.jsonl"));
            var scriptBackend = new ScriptScheduledNotificationBackend(new ExternalProcessRunner(), patched);
            Environment.SetEnvironmentVariable("M119_TASK_PATH", scriptTaskPath);

            foreach ((string kind, string? recurrence) in new[] { ("alarm", (string?)null), ("reminder", "daily"), ("alarm", "hourly") })
            {
                DateTimeOffset due = DateTimeOffset.UtcNow.AddDays(2).AddMilliseconds(321);
                string nativeName = TaskName(kind == "alarm" ? "Alarm" : "Reminder", Guid.NewGuid().ToString("N"));
                string scriptName = TaskName(kind == "alarm" ? "Alarm" : "Reminder", Guid.NewGuid().ToString("N"));
                string ring = Path.Combine(alarmRoot, "ring.ps1");
                File.WriteAllText(ring, "# ring");
                string mode = recurrence is null ? "schedule" : "schedule-recurring";
                ScheduledNotificationRequest Request(string name) => new(mode, kind)
                {
                    TaskName = name,
                    DueUtc = due.ToString("O", CultureInfo.InvariantCulture),
                    RingScriptPath = ring,
                    Recurrence = recurrence,
                };

                var clock = Stopwatch.StartNew();
                ExternalProcessResult nativeResult = Run(native, Request(nativeName));
                long nativeMs = clock.ElapsedMilliseconds;
                clock.Restart();
                ExternalProcessResult scriptResult = Run(scriptBackend, Request(scriptName));
                long scriptMs = clock.ElapsedMilliseconds;
                report.AppendLine(CultureInfo.InvariantCulture,
                    $"{mode}/{kind}/{recurrence ?? "once"}: native {nativeMs} ms, script {scriptMs} ms");

                Assert.That(nativeResult.ExitCode, Is.Zero, nativeResult.Error);
                Assert.That(scriptResult.ExitCode, Is.Zero, scriptResult.Error);
                Assert.That(
                    Canonical(nativeResult.Output.Trim()).Replace(nativeName, "{TASK}", StringComparison.Ordinal),
                    Is.EqualTo(Canonical(scriptResult.Output.Trim().Split('\n').Last()).Replace(scriptName, "{TASK}", StringComparison.Ordinal)));
                Assert.That(
                    StoredXml(folder!, nativeName).Replace(nativeName, "{TASK}", StringComparison.Ordinal),
                    Is.EqualTo(StoredXml(folder!, scriptName).Replace(scriptName, "{TASK}", StringComparison.Ordinal)));
            }

            // A clock cancellation end to end on the real scheduler, natively.
            string clockName = TaskName("Alarm", Guid.NewGuid().ToString("N"));
            DateTimeOffset clockDue = new DateTimeOffset(DateTime.Today.AddDays(3).AddHours(4).AddMinutes(17)).ToUniversalTime();
            string clockRing = Path.Combine(alarmRoot, clockName + ".ps1");
            File.WriteAllText(clockRing, "# ring");
            _ = Run(native, new ScheduledNotificationRequest("schedule", "alarm")
            {
                TaskName = clockName,
                DueUtc = clockDue.ToString("O", CultureInfo.InvariantCulture),
                RingScriptPath = clockRing,
            });
            var resolveClock = Stopwatch.StartNew();
            ExternalProcessResult resolved = Run(native,
                new ScheduledNotificationRequest("resolve-at", "alarm") { Hour = 4, Minute = 17, Period = "am", AlarmRoot = alarmRoot });
            long resolveMs = resolveClock.ElapsedMilliseconds;
            using JsonDocument resolution = JsonDocument.Parse(resolved.Output);
            Assert.That(resolution.RootElement.GetProperty("taskName").GetString(), Is.EqualTo(clockName), resolved.Output);
            var cancelClock = Stopwatch.StartNew();
            ExternalProcessResult canceled = Run(native,
                new ScheduledNotificationRequest("cancel-exact", "alarm")
                {
                    TaskName = clockName,
                    DueUtc = resolution.RootElement.GetProperty("nextRunUtc").GetString(),
                });
            long cancelMs = cancelClock.ElapsedMilliseconds;
            using JsonDocument cancellation = JsonDocument.Parse(canceled.Output);
            Assert.That(cancellation.RootElement.GetProperty("canceled").GetBoolean(), Is.True, canceled.Output);
            var diagnoseClock = Stopwatch.StartNew();
            ExternalProcessResult diagnosed = Run(native,
                new ScheduledNotificationRequest("diagnose", "reminder") { AlarmRoot = alarmRoot });
            long diagnoseMs = diagnoseClock.ElapsedMilliseconds;
            Assert.That(diagnosed.ExitCode, Is.Zero, diagnosed.Error);
            report.AppendLine(CultureInfo.InvariantCulture,
                $"resolve-at native {resolveMs} ms, cancel-exact native {cancelMs} ms, diagnose native {diagnoseMs} ms");
            TestContext.Out.WriteLine(report.ToString());
        }
        finally
        {
            Environment.SetEnvironmentVariable("M119_TASK_PATH", null);
            if (folder is not null)
            {
                foreach (string name in TaskNames(folder))
                    _ = folder.DeleteTask(name, 0);
                WindowsTaskSchedulerHost.Release(folder);
            }
            if (root is not null)
            {
                _ = root.DeleteFolder(folderName, 0);
                int gone = root.GetFolder(folderName, out ITaskSchedulerFolder? left);
                WindowsTaskSchedulerHost.Release(left);
                WindowsTaskSchedulerHost.Release(root);
                Assert.That(gone, Is.LessThan(0), "the test folder was removed");
            }
            WindowsTaskSchedulerHost.Release(service);
        }
    }

    /// <summary>
    /// Opt-in and read-only: the user's real Task Scheduler root, where BAXY's notifications live.
    /// diagnose and resolve-at read the same tasks through the script and natively; both answers and
    /// both times are compared. M119_ALARM_ROOT may name a real data root's scheduled-notifications.
    /// </summary>
    [Test]
    [Explicit("Reads the user's real Task Scheduler root folder; changes nothing.")]
    public void RealRootReadsAnswerLikeTheScript()
    {
        using TemporaryDirectory temporary = new();
        string alarmRoot = Environment.GetEnvironmentVariable("M119_ALARM_ROOT") is { Length: > 0 } configured
            ? configured
            : temporary.Path;
        var native = new NativeScheduledNotificationBackend(
            new WindowsTaskSchedulerHost(), new ThrowingBackend(Path.Combine(temporary.Path, "fallback.jsonl")),
            Path.Combine(temporary.Path, "fallback.jsonl"));
        var script = new ScriptScheduledNotificationBackend(
            new ExternalProcessRunner(), Path.Combine(AppContext.BaseDirectory, "WindowsScheduledNotification.ps1"));
        var report = new StringBuilder();
        foreach (ScheduledNotificationRequest request in new[]
                 {
                     new ScheduledNotificationRequest("diagnose", "reminder") { AlarmRoot = alarmRoot },
                     new ScheduledNotificationRequest("resolve-at", "alarm") { Hour = 6, Minute = 15, AlarmRoot = alarmRoot },
                 })
        {
            var clock = Stopwatch.StartNew();
            ExternalProcessResult nativeResult = Run(native, request);
            long nativeMs = clock.ElapsedMilliseconds;
            clock.Restart();
            ExternalProcessResult scriptResult = Run(script, request);
            long scriptMs = clock.ElapsedMilliseconds;
            Assert.That(nativeResult.ExitCode, Is.Zero, nativeResult.Error);
            Assert.That(scriptResult.ExitCode, Is.Zero, scriptResult.Error);
            string nativeLine = Canonical(nativeResult.Output.Trim());
            Assert.That(nativeLine, Is.EqualTo(Canonical(scriptResult.Output.Trim().Split('\n').Last())));
            report.AppendLine(CultureInfo.InvariantCulture,
                $"{request.Mode}: native {nativeMs} ms, script {scriptMs} ms, {nativeLine.Length} chars equal");
        }
        TestContext.Out.WriteLine(report.ToString());
    }

    private static ExternalProcessResult Run(
        IScheduledNotificationBackend backend, ScheduledNotificationRequest request) =>
        backend.RunAsync(request, CancellationToken.None).AsTask().GetAwaiter().GetResult();

    private static WindowsScheduledNotificationAdapter Adapter(
        TemporaryDirectory temporary, FakeTaskScheduler scheduler, RecordingRunner runner)
    {
        string script = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        File.WriteAllText(script, "# fixture");
        return new WindowsScheduledNotificationAdapter(temporary.Path, scheduler, runner, script);
    }

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

    private static string StoredXml(ITaskSchedulerFolder folder, string name)
    {
        WindowsTaskSchedulerHost.ThrowOnFailure(folder.GetTask(name, out IRegisteredTask? task), "get");
        try
        {
            WindowsTaskSchedulerHost.ThrowOnFailure(task!.GetXml(out string? xml), "xml");
            return xml!;
        }
        finally
        {
            WindowsTaskSchedulerHost.Release(task);
        }
    }

    private static List<string> TaskNames(ITaskSchedulerFolder folder)
    {
        List<string> names = [];
        if (folder.GetTasks(1, out IRegisteredTaskCollection? tasks) < 0 || tasks is null) return names;
        try
        {
            _ = tasks.GetCount(out int count);
            for (int index = 1; index <= count; index++)
            {
                if (tasks.GetItem(TaskSchedulerVariant.Int32(index), out IRegisteredTask? task) < 0) continue;
                if (task!.GetName(out string? name) >= 0 && name is not null) names.Add(name);
                WindowsTaskSchedulerHost.Release(task);
            }
        }
        finally
        {
            WindowsTaskSchedulerHost.Release(tasks);
        }
        return names;
    }

    private static async Task<string> RunStubbedScriptAsync(IReadOnlyList<SpecTask> tasks, int? toast, string arguments)
    {
        const string stubs = """
            $global:Spec = ConvertFrom-Json $env:M119_SPEC
            $global:Tasks = [ordered]@{}
            foreach ($entry in $global:Spec.tasks) { $global:Tasks[$entry.name] = $entry }
            $invariant = [Globalization.CultureInfo]::InvariantCulture
            function Get-ScheduledTask { param([string]$TaskName, $ErrorAction)
                foreach ($name in @($global:Tasks.Keys)) {
                    if ($name -like $TaskName) {
                        $states = @('Unknown', 'Disabled', 'Queued', 'Ready', 'Running')
                        [pscustomobject]@{ TaskName = $name; State = $states[$global:Tasks[$name].state] }
                    }
                } }
            function Get-ScheduledTaskInfo { param([string]$TaskName, $ErrorAction)
                $task = $global:Tasks[$TaskName]
                if ($null -eq $task) { throw 'task_missing' }
                [pscustomobject]@{
                    NextRunTime = $(if ($task.next) { [datetime]::Parse($task.next, $invariant) } else { $null })
                    LastRunTime = $(if ($task.last) { [datetime]::Parse($task.last, $invariant) } else { $null })
                    LastTaskResult = [uint32]$task.result
                } }
            function Unregister-ScheduledTask { param([string]$TaskName, $Confirm) $global:Tasks.Remove($TaskName) }
            function Get-Service { param($Name, $ErrorAction) [pscustomobject]@{ Status = 'Running' } }
            function Get-ItemProperty { param($Path, $ErrorAction)
                if ($null -eq $global:Spec.toast) { $null } else { [pscustomobject]@{ NOC_GLOBAL_SETTING_TOASTS_ENABLED = $global:Spec.toast } } }

            """;
        string spec = JsonSerializer.Serialize(new
        {
            toast,
            tasks = tasks.Select(task => new
            {
                name = task.Name,
                state = task.State,
                next = task.Next?.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture),
                last = task.Last?.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture),
                result = (uint)task.Result,
            }),
        });
        string script = Path.Combine(AppContext.BaseDirectory, "WindowsScheduledNotification.ps1");
        var start = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                     stubs + $"& '{script.Replace("'", "''", StringComparison.Ordinal)}' {arguments}" })
            start.ArgumentList.Add(argument);
        start.Environment["M119_SPEC"] = spec;
        using Process process = Process.Start(start)!;
        Task<string> output = process.StandardOutput.ReadToEndAsync();
        Task<string> error = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(60));
        Assert.That(process.ExitCode, Is.Zero, await error);
        return await output;
    }

    // Property order and number spelling differ between ConvertTo-Json and Utf8JsonWriter; the values may not.
    private static string Canonical(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        var text = new StringBuilder();
        Write(document.RootElement);
        return text.ToString();

        void Write(JsonElement element)
        {
            switch (element.ValueKind)
            {
                case JsonValueKind.Object:
                    text.Append('{');
                    foreach (JsonProperty property in element.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal))
                    {
                        text.Append(property.Name).Append(':');
                        Write(property.Value);
                        text.Append(',');
                    }
                    text.Append('}');
                    break;
                case JsonValueKind.Array:
                    text.Append('[');
                    foreach (JsonElement item in element.EnumerateArray())
                    {
                        Write(item);
                        text.Append(',');
                    }
                    text.Append(']');
                    break;
                case JsonValueKind.String:
                    text.Append(JsonSerializer.Serialize(element.GetString()));
                    break;
                case JsonValueKind.Number:
                    text.Append(element.GetDecimal().ToString(CultureInfo.InvariantCulture));
                    break;
                default:
                    text.Append(element.GetRawText());
                    break;
            }
        }
    }

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private sealed record SpecTask(string Name, int State, DateTime? Next, DateTime? Last, int Result);

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
        internal List<string> Deleted { get; } = [];
        internal string Sid { get; set; } = NativeScheduledNotificationTests.Sid;
        internal int? Toast { get; set; }
        internal Exception? OpenFailure { get; set; }
        internal Exception? RegisterFailure { get; set; }
        internal Exception? DeleteFailure { get; set; }

        internal static FakeTaskScheduler From(IEnumerable<SpecTask> tasks, int? toast)
        {
            var scheduler = new FakeTaskScheduler { Toast = toast };
            foreach (SpecTask task in tasks)
            {
                scheduler.Tasks[task.Name] = new FakeTask(task.Name)
                {
                    State = task.State,
                    NextRunLocal = task.Next,
                    LastRunLocal = task.Last,
                    LastTaskResult = task.Result,
                };
            }
            return scheduler;
        }

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
                owner.Deleted.Add(name);
            }

            public void Dispose()
            {
            }
        }
    }

    private sealed class ThrowingBackend(string diagnostic) : IScheduledNotificationBackend
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            ScheduledNotificationRequest request, CancellationToken cancellationToken) =>
            throw new AssertionException("the script fallback was not expected: " + request.Mode + " "
                + (File.Exists(diagnostic) ? File.ReadAllText(diagnostic) : "(no diagnostic)"));
    }

    private sealed class RecordingRunner : IExternalProcessRunner
    {
        internal int Calls { get; private set; }
        internal string TaskName { get; private set; } = string.Empty;
        internal IReadOnlyList<string> Arguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            Calls++;
            Arguments = arguments.ToArray();
            int taskIndex = arguments.ToList().IndexOf("-TaskName");
            TaskName = taskIndex >= 0 ? arguments[taskIndex + 1] : string.Empty;
            string output = JsonSerializer.Serialize(new
            {
                version = 1,
                ok = true,
                effectObserved = true,
                taskName = TaskName,
                state = "Ready",
                nextRunUtc = DateTimeOffset.UtcNow.AddHours(1).ToString("O", CultureInfo.InvariantCulture),
                authority = "windows_task_scheduler_postread",
            });
            return ValueTask.FromResult(new ExternalProcessResult(0, output, string.Empty));
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
