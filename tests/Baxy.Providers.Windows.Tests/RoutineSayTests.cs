using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Xml;
using System.Xml.Linq;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Routines;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// RUT4 (owner, 2026-11-10: «todos los días a las 10 dime buen día… una vez y listo»; documentacion/RUTINAS.md §4): a
/// routine at a time is kept only with its Task Scheduler task set and read back, it only says texts, its receipt says
/// when and how it will say them, and turning it off or deleting it takes the task away. The scheduler here is a fake:
/// nothing of this PC's is touched.
/// </summary>
[TestFixture]
public sealed class RoutineSayTests
{
    // Tuesday 2026-11-10, 21:30 at UTC-3.
    private static readonly TimeZoneInfo Zone = TimeZoneInfo.CreateCustomTimeZone("rut4", TimeSpan.FromHours(-3), "rut4", "rut4");
    private static readonly DateTimeOffset Now = new(2026, 11, 10, 21, 30, 0, TimeSpan.FromHours(-3));

    // The schema of a task (Microsoft Learn, Task Scheduler schema).
    private static readonly XNamespace TaskNs = "http://schemas.microsoft.com/windows/2004/02/mit/task";

    private static readonly string PowerShell =
        Path.Combine(Environment.SystemDirectory, @"WindowsPowerShell\v1.0\powershell.exe");

    // Invented words with what a script file read in the PC's own code page would break.
    private const string Words = "¡Ánimo! Mañana toca regar el jardín y contar «pingüinos» de cartón.";

    // The one call of the script that puts a notification on the screen.
    private const string ShowCall =
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($note)";

    // Longer than the script's own wait for the App; a script still running then is ended and the test fails.
    private static readonly TimeSpan Limit = TimeSpan.FromSeconds(60);

    private sealed record ActionRun(
        int? Exit, IReadOnlyList<AlarmRingHandoff.Ring> Taken, JsonNode? Receipt, string[] Left, string Errors);

    private string _root = string.Empty;
    private FakeScheduler _scheduler = new();
    private Clock _clock = new(Now);

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-routine-say-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
        _scheduler = new FakeScheduler();
        _clock = new Clock(Now);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    // The owner's first example: saved with its task, and the receipt says when it is first said and what happens then.
    [Test]
    public async Task ADailyRoutineAtATimeIsKeptWithItsTaskAndTheReceiptSaysWhenAndHow()
    {
        OperationOutcome outcome = await Run("""
            {"action":"create","at":"10:00","repeat":"daily","steps":["say: Buen día, que te vaya muy bien el trabajo."]}
            """);

        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        JsonObject receipt = Result(outcome);
        JsonObject routine = receipt["routine"]!.AsObject();
        string task = _scheduler.Tasks.Keys.Single();
        Assert.Multiple(() =>
        {
            Assert.That(routine["name"]!.GetValue<string>(), Is.EqualTo("10:00"));
            Assert.That(routine["trigger"]!.ToJsonString(), Is.EqualTo("""{"at":"10:00","repeat":"daily"}"""));
            Assert.That(routine["steps"]![0]!["say"]!.GetValue<string>(), Does.StartWith("Buen día"));
            Assert.That(receipt["saved"]!.GetValue<bool>(), Is.True);
            Assert.That(receipt["nextRunLocal"]!.GetValue<string>(), Is.EqualTo("2026-11-11 10:00"));
            Assert.That(receipt["scheduledFor"]!.GetValue<string>(), Is.EqualTo("tomorrow"));
            Assert.That(receipt["runsWhen"]!.GetValue<string>(), Does.Contain("By itself at 10:00 every day")
                .And.Contain("aloud once").And.Contain("nothing rings").And.Contain("closed").And.Contain("notification"));
            Assert.That(task, Does.Match("^BAXY-Say-[0-9a-f]{32}$"));
            Assert.That(ScheduledRingTasks.IsRingTask(task), Is.True, "the uninstaller and the spent prune take it");
            Assert.That(_scheduler.Xml[task], Does.Contain("<CalendarTrigger>").And.Contain("<DaysInterval>1</DaysInterval>")
                .And.Contain("<WakeToRun>false</WakeToRun>").And.Contain("<StartWhenAvailable>true</StartWhenAvailable>"));
            Assert.That(ScheduledRingScript.ReadTitle(Script(task)), Is.EqualTo("Buen día, que te vaya muy bien el trabajo."));
            Assert.That(Store().Read(), Has.Count.EqualTo(1));
        });
    }

    // Days of the week: a weekly trigger on them, first on the next of those days; all seven is every day.
    [Test]
    public async Task DaysOfTheWeekSetAWeeklyTaskAndTheFirstTimeIsTheNextOfThoseDays()
    {
        OperationOutcome outcome = await Run("""
            {"action":"create","name":"pausa","at":"9:00","repeat":"days","days":["fri","MON","thu"],"steps":["say: Estira las piernas."]}
            """);
        OperationOutcome every = await Run("""
            {"action":"create","name":"todos","at":"07:30","days":["mon","tue","wed","thu","fri","sat","sun"],"steps":["say: Arriba."]}
            """);

        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        JsonObject receipt = Result(outcome);
        string xml = _scheduler.Xml.Values.First();
        Assert.Multiple(() =>
        {
            Assert.That(receipt["routine"]!["trigger"]!.ToJsonString(),
                Is.EqualTo("""{"at":"09:00","repeat":"days","days":["mon","thu","fri"]}"""));
            // Tuesday night: the next of Monday, Thursday and Friday is Thursday the 12th.
            Assert.That(receipt["nextRunLocal"]!.GetValue<string>(), Is.EqualTo("2026-11-12 09:00"));
            Assert.That(receipt["scheduledFor"]!.GetValue<string>(), Is.EqualTo("Thursday 2026-11-12"));
            Assert.That(receipt["runsWhen"]!.GetValue<string>(), Does.Contain("every mon, thu, fri"));
            Assert.That(xml, Does.Contain("<ScheduleByWeek>").And.Contain("<WeeksInterval>1</WeeksInterval>")
                .And.Contain("<Monday />").And.Contain("<Thursday />").And.Contain("<Friday />").And.Not.Contain("<Tuesday />"));
            Assert.That(Result(every)["routine"]!["trigger"]!.ToJsonString(), Is.EqualTo("""{"at":"07:30","repeat":"daily"}"""));
        });
    }

    // Said once: the next time that clock comes (its date is kept), or the date and time given; one that has passed is
    // refused and nothing is saved; once its time has passed the routine is no longer in the list.
    [Test]
    public async Task ARoutineSaidOnceKeepsItsDateRefusesAPastOneAndLeavesTheListAfterItsTime()
    {
        OperationOutcome tonight = await Run("""{"action":"create","name":"ropa","at":"22:15","steps":["say: Saca la ropa."]}""");
        OperationOutcome dated = await Run("""{"action":"create","name":"viaje","at":"2026-11-14T08:00","repeat":"once","steps":["say: Buen viaje."]}""");
        OperationOutcome past = await Run("""{"action":"create","name":"tarde","at":"2026-11-10T18:00","steps":["say: Ya pasó."]}""");
        OperationOutcome datedDaily = await Run("""{"action":"create","name":"mal","at":"2026-11-14T08:00","repeat":"daily","steps":["say: x"]}""");

        Assert.Multiple(() =>
        {
            Assert.That(Result(tonight)["routine"]!["trigger"]!.ToJsonString(),
                Is.EqualTo("""{"at":"22:15","repeat":"once","date":"2026-11-10"}"""));
            Assert.That(Result(tonight)["scheduledFor"]!.GetValue<string>(), Is.EqualTo("today"));
            Assert.That(Result(tonight)["runsWhen"]!.GetValue<string>(), Does.Contain("one time only"));
            Assert.That(_scheduler.Xml.Values.First(), Does.Contain("<TimeTrigger>").And.Not.Contain("Schedule"));
            Assert.That(Result(dated)["nextRunLocal"]!.GetValue<string>(), Is.EqualTo("2026-11-14 08:00"));
            Assert.That(past.ErrorCode, Is.EqualTo("routine_time_passed"));
            Assert.That(Result(past)["saved"]!.GetValue<bool>(), Is.False);
            Assert.That(Result(past)["nowLocal"]!.GetValue<string>(), Is.EqualTo("2026-11-10 21:30"));
            Assert.That(datedDaily.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(_scheduler.Tasks, Has.Count.EqualTo(2));
        });

        _clock.Now = Now.AddHours(1);
        OperationOutcome listed = await Run("""{"action":"list"}""");
        Assert.That(Result(listed)["routines"]!.AsArray().Select(static routine => routine!["name"]!.GetValue<string>()),
            Is.EqualTo(new[] { "viaje" }));
    }

    // At its time nobody is there to be asked: a tool step is refused, with a phrase and a time it is neither, and the
    // days are the week's. Nothing is saved and no task is set.
    [TestCase("""{"action":"create","at":"10:00","repeat":"daily","steps":["media.control {\"action\":\"pause\"}"]}""", "routine_invalid_step")]
    [TestCase("""{"action":"create","at":"10:00","repeat":"days","days":["lunes"],"steps":["say: hola"]}""", "invalid_arguments")]
    [TestCase("""{"action":"create","at":"10:00","repeat":"days","steps":["say: hola"]}""", "invalid_arguments")]
    [TestCase("""{"action":"create","at":"10:00","repeat":"daily","days":["mon"],"steps":["say: hola"]}""", "invalid_arguments")]
    [TestCase("""{"action":"create","at":"las diez","steps":["say: hola"]}""", "invalid_arguments")]
    public async Task WhatARoutineAtATimeCannotBeIsRefusedAndNothingIsKept(string json, string code)
    {
        OperationOutcome outcome = await Run(json);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            Assert.That(Store().Read(), Is.Empty);
            Assert.That(_scheduler.Tasks, Is.Empty);
        });
    }

    // Off: its task goes and it stays in the list. On again: the task is back. Deleted: neither is left. By its name or
    // by its time, as the person says it.
    [Test]
    public async Task TurningItOffTakesItsTaskAwayTurningItOnSetsItAgainAndDeletingLeavesNothing()
    {
        await Run("""{"action":"create","name":"ánimo","at":"08:00","repeat":"daily","steps":["say: Ánimo."]}""");
        string task = _scheduler.Tasks.Keys.Single();

        OperationOutcome off = await Run("""{"action":"disable","name":"Animo"}""");
        bool taskWhileOff = _scheduler.Tasks.ContainsKey(task), scriptWhileOff = File.Exists(Script(task));
        OperationOutcome on = await Run("""{"action":"enable","name":"08:00"}""");
        bool taskWhileOn = _scheduler.Tasks.ContainsKey(task);
        OperationOutcome deleted = await Run("""{"action":"delete","name":"ánimo"}""");

        Assert.Multiple(() =>
        {
            Assert.That(off.Succeeded && on.Succeeded && deleted.Succeeded, Is.True);
            Assert.That(Result(off)["routine"]!["active"]!.GetValue<bool>(), Is.False);
            Assert.That(taskWhileOff, Is.False);
            Assert.That(scriptWhileOff, Is.False);
            Assert.That(Result(on)["routine"]!["active"]!.GetValue<bool>(), Is.True);
            Assert.That(Result(on)["nextRunLocal"]!.GetValue<string>(), Is.EqualTo("2026-11-11 08:00"));
            Assert.That(taskWhileOn, Is.True);
            Assert.That(_scheduler.Tasks, Is.Empty);
            Assert.That(File.Exists(Script(task)), Is.False);
            Assert.That(Store().Read(), Is.Empty);
        });
    }

    // A change keeps what it leaves out: new words at the same time, or a new time for the same words; the one task
    // is set again with them.
    [Test]
    public async Task AChangeSetsTheSameTaskAgainWithTheNewWordsOrTheNewTime()
    {
        await Run("""{"action":"create","name":"café","at":"16:00","repeat":"daily","steps":["say: Hora del café."]}""");
        string task = _scheduler.Tasks.Keys.Single();

        OperationOutcome words = await Run("""{"action":"change","name":"café","steps":["say: Un cafecito."]}""");
        string? said = ScheduledRingScript.ReadTitle(Script(task));
        OperationOutcome time = await Run("""{"action":"change","name":"café","at":"17:15"}""");

        Assert.Multiple(() =>
        {
            Assert.That(words.Succeeded && time.Succeeded, Is.True);
            Assert.That(said, Is.EqualTo("Un cafecito."));
            Assert.That(Result(words)["routine"]!["trigger"]!.ToJsonString(), Is.EqualTo("""{"at":"16:00","repeat":"daily"}"""));
            Assert.That(Result(time)["routine"]!["trigger"]!.ToJsonString(), Is.EqualTo("""{"at":"17:15","repeat":"daily"}"""));
            Assert.That(Result(time)["nextRunLocal"]!.GetValue<string>(), Is.EqualTo("2026-11-11 17:15"));
            Assert.That(_scheduler.Tasks.Keys, Is.EqualTo(new[] { task }));
            Assert.That(ScheduledRingScript.ReadTitle(Script(task)), Is.EqualTo("Un cafecito."));
        });
    }

    // A scheduler that does not answer, or a task read back with no next run: the routine is not saved (it would never
    // speak), and one that cannot lose its task is not deleted (it would still speak).
    [Test]
    public async Task WithoutItsTaskReadBackNothingIsSavedAndWithItsTaskStillThereNothingIsDeleted()
    {
        _scheduler.OpenFailure = new TaskSchedulerHostException("down");
        OperationOutcome down = await Run("""{"action":"create","at":"10:00","repeat":"daily","steps":["say: hola"]}""");
        _scheduler.OpenFailure = null;
        _scheduler.NoNextRun = true;
        OperationOutcome unread = await Run("""{"action":"create","at":"10:00","repeat":"daily","steps":["say: hola"]}""");
        _scheduler.NoNextRun = false;
        await Run("""{"action":"create","name":"queda","at":"10:00","repeat":"daily","steps":["say: hola"]}""");
        _scheduler.OpenFailure = new TaskSchedulerHostException("down");
        OperationOutcome kept = await Run("""{"action":"delete","name":"queda"}""");
        _scheduler.OpenFailure = null;

        Assert.Multiple(() =>
        {
            Assert.That(down.ErrorCode, Is.EqualTo("routine_scheduler_unavailable"));
            Assert.That(Result(down)["saved"]!.GetValue<bool>(), Is.False);
            Assert.That(unread.ErrorCode, Is.EqualTo("routine_task_not_verified"));
            Assert.That(kept.ErrorCode, Is.EqualTo("routine_scheduler_unavailable"));
            Assert.That(Store().Read().Select(static routine => routine["name"]!.GetValue<string>()), Is.EqualTo(new[] { "queda" }));
            Assert.That(_scheduler.Tasks, Has.Count.EqualTo(1));
        });
    }

    // REV11 B-1: a task registered whose reading back fails is taken off again: BAXY says it was not saved, the routine
    // is not in the list, and no BAXY-Say task is left speaking every day with nothing in the list (nor in «Olvidar todo»).
    [Test]
    public async Task ATaskRegisteredThatCannotBeReadBackDoesNotStaySpeakingWithNoRoutine()
    {
        _scheduler.FindFailure = new TaskSchedulerHostException("read back failed");
        OperationOutcome unread = await Run("""{"action":"create","at":"10:00","repeat":"daily","steps":["say: hola"]}""");
        _scheduler.FindFailure = null;

        Assert.Multiple(() =>
        {
            Assert.That(unread.ErrorCode, Is.EqualTo("routine_task_not_verified"));
            Assert.That(Store().Read(), Is.Empty);
            Assert.That(_scheduler.Tasks, Is.Empty, "the task registered is taken off again");
        });
    }

    // Held-out th02/th05: a «phrase» written beside a time is left out, and the receipt says it; held-out th11/th12: a
    // name that is no routine's comes back with each routine and what runs it, to choose from.
    [Test]
    public async Task APhraseBesideATimeIsLeftOutAndANameThatIsNoneComesBackWithWhatRunsEachOne()
    {
        OperationOutcome timed = await Run("""
            {"action":"create","name":"ventilar","phrase":"por las mañanas","at":"08:40","repeat":"daily","steps":["say: Abre las ventanas."]}
            """);
        OperationOutcome missing = await Run("""{"action":"disable","name":"la de por las mañanas"}""");

        Assert.Multiple(() =>
        {
            Assert.That(timed.Succeeded, Is.True, timed.ErrorCode);
            Assert.That(Result(timed)["routine"]!["trigger"]!.ToJsonString(), Is.EqualTo("""{"at":"08:40","repeat":"daily"}"""));
            Assert.That(Result(timed)["ignored"]!.GetValue<string>(), Does.StartWith("phrase"));
            Assert.That(Result(timed)["runsWhen"]!.GetValue<string>(), Does.StartWith("By itself at 08:40 every day"));
            Assert.That(missing.ErrorCode, Is.EqualTo("routine_not_found"));
            Assert.That(Result(missing)["routines"]!.ToJsonString(),
                Is.EqualTo("""[{"name":"ventilar","trigger":{"at":"08:40","repeat":"daily"}}]"""));
            Assert.That(Result(missing)["next"]!.GetValue<string>(), Does.Contain("call again with the name"));
        });
    }

    // REM4 (REV14 A-R2): «despertar» at 07:00, saved first, and another at 07:00 with no name of its own (FreeName:
    // «07:00»). A name is looked for over the whole list, its own name first: «07:00» deletes, turns off or changes the
    // routine called so, never «despertar» for being first in the list at that clock.
    [TestCase("delete")]
    [TestCase("disable")]
    [TestCase("change")]
    public async Task ANameIsTheRoutineSoNamedNotAnotherFirstAtThatClock(string action)
    {
        await Run("""{"action":"create","name":"despertar","at":"07:00","repeat":"daily","steps":["say: arriba"]}""");
        OperationOutcome other = await Run("""{"action":"create","at":"07:00","repeat":"daily","steps":["say: toma la pastilla"]}""");
        string named = Result(other)["routine"]!["name"]!.GetValue<string>();
        var call = new JsonObject { ["action"] = action, ["name"] = named };
        if (action == "change")
        {
            call["steps"] = new JsonArray("say: toma dos pastillas");
        }

        OperationOutcome outcome = await Run(call.ToJsonString());

        IReadOnlyList<JsonObject> kept = Store().Read();
        JsonObject wake = kept.Single(routine => (string?)routine["name"] == "despertar");
        Assert.Multiple(() =>
        {
            Assert.That(named, Is.EqualTo("07:00"));
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(wake["active"]!.GetValue<bool>(), Is.True);
            Assert.That(wake["steps"]![0]!["say"]!.GetValue<string>(), Is.EqualTo("arriba"));
            Assert.That(kept, Has.Count.EqualTo(action == "delete" ? 1 : 2));
        });
    }

    // REM6 (REV15 B-2): after their «sí» the mind names the routine it asked about by its id. Kept, that one is done;
    // gone meanwhile (one said once is pruned two minutes after its time), nothing is done, never another routine that
    // answers to the name it was asked by: «despertar» at the same clock, or one whose phrase is that name.
    [TestCase("delete")]
    [TestCase("disable")]
    [TestCase("change")]
    public async Task AnIdIsThatRoutineAndOneGoneTouchesNoOther(string action)
    {
        await Run("""{"action":"create","name":"despertar","at":"07:00","repeat":"daily","steps":["say: arriba"]}""");
        OperationOutcome other = await Run("""{"action":"create","at":"07:00","repeat":"daily","steps":["say: toma la pastilla"]}""");
        await Run("""{"action":"create","name":"estudio","phrase":"lectura","order":"silencia el chat"}""");
        OperationOutcome read = await Run("""{"action":"create","name":"lectura","phrase":"modo lectura","order":"baja el brillo"}""");
        string pill = Result(other)["routine"]!["id"]!.GetValue<string>();
        string reading = Result(read)["routine"]!["id"]!.GetValue<string>();
        JsonObject Call(string id)
        {
            var call = new JsonObject { ["action"] = action, ["name"] = id };
            if (action == "change")
            {
                call["steps"] = new JsonArray("say: toma dos pastillas");
            }

            return call;
        }

        OperationOutcome kept = await Run(Call(pill).ToJsonString());
        await Run($$"""{"action":"delete","name":"{{pill}}"}""");
        await Run($$"""{"action":"delete","name":"{{reading}}"}""");
        string before = string.Join("|", Store().Read().Select(static routine => routine.ToJsonString()));
        OperationOutcome gone = await Run(Call(pill).ToJsonString());
        OperationOutcome goneByPhrase = await Run(Call(reading).ToJsonString());

        Assert.Multiple(() =>
        {
            Assert.That(kept.Succeeded, Is.True, kept.ErrorCode);
            Assert.That(gone.ErrorCode, Is.EqualTo("routine_not_found"));
            Assert.That(goneByPhrase.ErrorCode, Is.EqualTo("routine_not_found"));
            Assert.That(string.Join("|", Store().Read().Select(static routine => routine.ToJsonString())), Is.EqualTo(before));
            Assert.That(Store().Read().Select(static routine => (string?)routine["name"]),
                Is.EquivalentTo(new[] { "despertar", "estudio" }));
        });
    }

    // A routine with a phrase says what fires it, and it is not a time; changed to a time it loses its phrase.
    [Test]
    public async Task ARoutineWithAPhraseNeverTouchesTheSchedulerAndSaysItHasNoTime()
    {
        OperationOutcome outcome = await Run("""{"action":"create","phrase":"tiempo","steps":["media.control {\"action\":\"toggle\"}"]}""");
        OperationOutcome deleted = await Run("""{"action":"delete","name":"tiempo"}""");

        Assert.Multiple(() =>
        {
            Assert.That(Result(outcome)["runsWhen"]!.GetValue<string>(), Does.Contain("«tiempo» alone").And.Contain("not a time"));
            Assert.That(deleted.Succeeded, Is.True);
            Assert.That(_scheduler.Opened, Is.Zero);
        });
    }

    // The script of a routine's task: handed to the open App as the rings are; with BAXY closed an ordinary notification
    // (no alarm or reminder scenario, no Snooze or Dismiss), and with notifications off nothing sounds.
    [Test]
    public void TheScriptOfARoutineHandsItsTextOverAndWithBaxyClosedShowsAnOrdinaryNotificationOnce()
    {
        string task = "BAXY-Say-" + new string('a', 32);
        string alarm = "BAXY-Alarm-" + new string('b', 32);
        ScheduledRingScript.Write(Path.Combine(_root, task + ".ps1"), "Saca la ropa.", "18:00");
        ScheduledRingScript.Write(Path.Combine(_root, alarm + ".ps1"), "Despierta", "07:00");
        string say = File.ReadAllText(Path.Combine(_root, task + ".ps1"));
        string ring = File.ReadAllText(Path.Combine(_root, alarm + ".ps1"));
        string toast = ScheduledRingScript.ToastXml("say", "Saca <la> ropa.", "18:00");

        Assert.Multiple(() =>
        {
            Assert.That(say, Does.StartWith(ScheduledRingScript.Marker).And.Contain("TryOpenExisting").And.Contain("rungBy='app'"));
            Assert.That(say, Does.Not.Contain("Alarm01.wav").And.Not.Contain("Beep").And.Not.Contain("History.Remove"));
            Assert.That(ring, Does.Contain("Alarm01.wav"), "an alarm still rings with notifications off");
            Assert.That(toast, Is.EqualTo("<toast><visual><binding template=\"ToastGeneric\"><text>BAXY</text>"
                + "<text>Saca &lt;la&gt; ropa.</text></binding></visual></toast>"));
            Assert.That(ScheduledRingScript.ToastXml("reminder", "x", "18:00"), Does.Contain("scenario=\"reminder\"").And.Contain("snooze"));
            Assert.That(ScheduledRingTasks.Kind(task), Is.EqualTo("say"));
            Assert.That(ScheduledRingTasks.Kind(alarm), Is.EqualTo("alarm"));
            Assert.That(ScheduledRingTasks.Kind("BAXY-Reminder-" + new string('c', 32)), Is.EqualTo("reminder"));
        });
    }

    // ENCARGO_RUT4 §3 (owner: «cuando te diga audífonos, cambia a los audífonos…»): a step that names a sound device is
    // looked up among the PC's when the routine is saved, by the call's own comparison. One device: saved. None, or
    // several: nothing is saved and the devices there are go back; a device list that cannot be read saves it.
    [TestCase("Halvik", true, null)]
    [TestCase("halvk strato", true, null)]
    [TestCase("Zerquon", false, "audio_device_not_matched")]
    [TestCase("Quiltec", false, "audio_device_ambiguous")]
    public async Task AStepThatNamesASoundDeviceIsSavedOnlyWhenThePcHasThatOneDevice(string said, bool saved, string? problem)
    {
        var provider = new Devices("Altavoces (Sornel R40)", "Auriculares (Halvik Strato 7)", "Quiltec One", "Quiltec Two");
        var handler = new RoutinesHandler(_root, _clock, new RoutineSayTasks(_root, _scheduler),
            (operation, arguments, token) => RoutineStepTargets.MissingAsync(provider, operation, arguments, token));
        var call = new JsonObject
        {
            ["action"] = "create",
            ["phrase"] = "audífonos",
            ["steps"] = new JsonArray("media.control {\"action\":\"pause\"}", "audio.device.set " + new JsonObject { ["device"] = said }.ToJsonString()),
        };
        using JsonDocument arguments = JsonDocument.Parse(call.ToJsonString());

        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.EqualTo(saved));
            Assert.That(Store().Read(), Has.Count.EqualTo(saved ? 1 : 0));
            Assert.That(provider.Asked, Is.EqualTo(new[] { "audio.device.list" }), "a read; nothing is set");
            if (!saved)
            {
                JsonObject result = Result(outcome);
                Assert.That(outcome.ErrorCode, Is.EqualTo("routine_invalid_step"));
                Assert.That(result["problem"]!.GetValue<string>(), Is.EqualTo(problem));
                Assert.That(result["step"]!.GetValue<int>(), Is.EqualTo(2));
                Assert.That(result["saved"]!.GetValue<bool>(), Is.False);
                Assert.That(result["devices"]!.AsArray().Select(static device => device!.GetValue<string>()),
                    problem == "audio_device_ambiguous"
                        ? Is.EqualTo(new[] { "Quiltec One", "Quiltec Two" })
                        : Has.Exactly(4).Items);
                Assert.That(result["next"]!.GetValue<string>(), Does.StartWith("nothing was saved"));
            }
        });
    }

    [Test]
    public async Task ADeviceListThatCannotBeReadDoesNotKeepARoutineFromBeingSaved()
    {
        var provider = new Devices { Fails = true };

        JsonObject? missing = await RoutineStepTargets.MissingAsync(
            provider, "audio.device.set", new JsonObject { ["device"] = "Halvik" }, CancellationToken.None);
        JsonObject? other = await RoutineStepTargets.MissingAsync(
            provider, "media.control", new JsonObject { ["action"] = "pause" }, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing, Is.Null);
            Assert.That(other, Is.Null);
            Assert.That(provider.Asked, Is.EqualTo(new[] { "audio.device.list" }), "only the step that names a device reads them");
        });
    }

    // Two data roots never share a task: the name comes from the root and the routine's id.
    [Test]
    public void TheTaskNameIsOfThisDataRootAndThisRoutine()
    {
        var here = new RoutineSayTasks(_root, _scheduler);
        var there = new RoutineSayTasks(_root + "-otro", _scheduler);

        Assert.Multiple(() =>
        {
            Assert.That(here.TaskName("r-0a1b2c"), Is.EqualTo(here.TaskName("r-0a1b2c")).And.Not.EqualTo(here.TaskName("r-0a1b2d")));
            Assert.That(there.TaskName("r-0a1b2c"), Is.Not.EqualTo(here.TaskName("r-0a1b2c")));
            Assert.That(Regex.IsMatch(here.TaskName("r-0a1b2c"), "^BAXY-Say-[0-9a-f]{32}$"), Is.True);
        });
    }

    // RUT8: the task as the scheduler would read it. Well formed, all of it in the Task Scheduler's namespace, one
    // trigger with its start (the instant asked, written at this PC's wall clock, which is what a daily or weekly
    // trigger repeats) and its repetition, and one action that runs PowerShell on the script the routine wrote. The
    // script as written parses as Windows PowerShell (parsed only: nothing of it runs here).
    [Test]
    public async Task TheTaskOfARoutineIsTaskSchedulerXmlWithItsStartItsRepetitionAndItsOneAction()
    {
        string daily = await Created("""{"action":"create","at":"10:00","repeat":"daily","steps":["say: Riega el jardín."]}""");
        string weekly = await Created("""
            {"action":"create","name":"pausa","at":"9:00","repeat":"days","days":["fri","mon","thu"],"steps":["say: Estira las piernas."]}
            """);
        string once = await Created("""{"action":"create","name":"ropa","at":"22:15","steps":["say: Saca la ropa."]}""");
        XElement[] tasks = [.. new[] { daily, weekly, once }.Select(task => XDocument.Parse(_scheduler.Xml[task]).Root!)];
        string parse = "$e=$null;[void][Management.Automation.Language.Parser]::ParseFile('" + Script(daily).Replace("'", "''")
            + "',[ref]$null,[ref]$e);'errors=' + $e.Count";
        ProcessStartInfo parser = Hidden(PowerShell, $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \"{parse}\"");

        (int? exit, string parsed, string errors) = await Ended(parser, static () => { });

        Assert.Multiple(() =>
        {
            foreach ((string task, XElement xml) in new[] { daily, weekly, once }.Zip(tasks))
            {
                XElement trigger = xml.Element(TaskNs + "Triggers")!.Elements().Single();
                XElement exec = xml.Element(TaskNs + "Actions")!.Elements().Single();
                XElement principal = xml.Element(TaskNs + "Principals")!.Elements().Single();
                XElement settings = xml.Element(TaskNs + "Settings")!;
                Assert.That(xml.Name, Is.EqualTo(TaskNs + "Task"));
                Assert.That(xml.DescendantsAndSelf().Select(static element => element.Name.Namespace), Is.All.EqualTo(TaskNs));
                Assert.That(trigger.Elements().First().Name, Is.EqualTo(TaskNs + "StartBoundary"));
                Assert.That(trigger.Element(TaskNs + "Repetition"), Is.Null, "said once at its time, not every so often");
                Assert.That(exec.Name, Is.EqualTo(TaskNs + "Exec"));
                Assert.That(File.Exists(Environment.ExpandEnvironmentVariables(exec.Element(TaskNs + "Command")!.Value)), Is.True);
                Assert.That(exec.Element(TaskNs + "Arguments")!.Value, Is.EqualTo(
                    "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File \"" + Script(task) + "\""));
                Assert.That(File.Exists(Script(task)), Is.True);
                // In the person's own session: the open App's mutex (Local\) is seen only from there.
                Assert.That(principal.Element(TaskNs + "LogonType")!.Value, Is.EqualTo("InteractiveToken"));
                Assert.That(principal.Element(TaskNs + "UserId")!.Value, Is.EqualTo(_scheduler.CurrentUserSid()));
                Assert.That(xml.Element(TaskNs + "Actions")!.Attribute("Context")!.Value, Is.EqualTo(principal.Attribute("id")!.Value));
                // The task outlives the script's wait for the App, and a run still going is never doubled.
                Assert.That(XmlConvert.ToTimeSpan(settings.Element(TaskNs + "ExecutionTimeLimit")!.Value),
                    Is.GreaterThan(ScheduledRingScript.HandOffWait));
                Assert.That(settings.Element(TaskNs + "MultipleInstancesPolicy")!.Value, Is.EqualTo("IgnoreNew"));
            }

            AssertStart(tasks[0], "CalendarTrigger", new DateTimeOffset(2026, 11, 11, 10, 0, 0, Now.Offset));
            Assert.That(tasks[0].Descendants(TaskNs + "ScheduleByDay").Single().Elements().Select(static e => e.Name.LocalName + "=" + e.Value),
                Is.EqualTo(new[] { "DaysInterval=1" }));
            AssertStart(tasks[1], "CalendarTrigger", new DateTimeOffset(2026, 11, 12, 9, 0, 0, Now.Offset));
            XElement byWeek = tasks[1].Descendants(TaskNs + "ScheduleByWeek").Single();
            Assert.That(byWeek.Element(TaskNs + "WeeksInterval")!.Value, Is.EqualTo("1"));
            Assert.That(byWeek.Element(TaskNs + "DaysOfWeek")!.Elements().Select(static day => day.Name.LocalName + day.Value),
                Is.EqualTo(new[] { "Monday", "Thursday", "Friday" }));
            AssertStart(tasks[2], "TimeTrigger", new DateTimeOffset(2026, 11, 10, 22, 15, 0, Now.Offset));
            Assert.That(tasks[2].Element(TaskNs + "Triggers")!.Elements().Single().Elements().Count(), Is.EqualTo(1));
            Assert.That(exit, Is.Zero, errors);
            Assert.That(parsed.Trim(), Is.EqualTo("errors=0"), errors);
        });
    }

    // RUT8: what the task runs, run. The command and the arguments are the ones of the task's XML, on the script the
    // routine wrote, against an «open App» that holds the folder's mutex and takes the hand-over as AlarmRinger.TakeDue
    // does (AlarmRingHandoff.Take, and for a text to say, End at once). The text arrives once and whole, the script ends
    // by itself and never reaches the notification; the next day's run hands it over once again.
    [Test]
    public async Task TheActionOfTheTaskRunWithBaxyOpenHandsTheWholeTextToTheAppOnceAndEnds()
    {
        string task = await Created(EveryDayAtTen(Words));
        string shown = WithoutShowing(task);

        ActionRun first = await RunTheAction(task, appOpen: true);
        ActionRun second = await RunTheAction(task, appOpen: true);

        Assert.Multiple(() =>
        {
            foreach (ActionRun run in new[] { first, second })
            {
                Assert.That(run.Exit, Is.Zero, "the script ends by itself: " + run.Errors);
                Assert.That(run.Taken, Has.Count.EqualTo(1), "handed over once");
                Assert.That(run.Taken.Select(static ring => ring.Title), Is.All.EqualTo(Words));
                Assert.That(run.Taken.Select(static ring => (ring.TaskName, ring.Kind, ring.Clock)),
                    Is.All.EqualTo((task, AlarmRingHandoff.SayKind, "10:00")));
                Assert.That(run.Receipt?["rungBy"]?.GetValue<string>(), Is.EqualTo("app"));
                Assert.That(run.Left, Is.EquivalentTo(new[] { task + ".ps1", task + ".fired" }), "no hand-over left behind");
            }

            // Yesterday's receipt is still there when today's run starts: it is said again, and the receipt is today's.
            Assert.That(second.Taken.Select(static ring => ring.RangUtc), Is.All.GreaterThan(first.Taken.Select(static ring => ring.RangUtc).FirstOrDefault()));
            Assert.That(second.Receipt?["rangUtc"]?.GetValue<string>(), Is.Not.EqualTo(first.Receipt?["rangUtc"]?.GetValue<string>()));
            Assert.That(File.Exists(shown), Is.False, "with BAXY open the notification is never reached");
        });
    }

    // RUT8: with BAXY closed (nobody holds the mutex) the same action goes straight to the notification, once, and it is
    // the ordinary one with the whole text. Nothing is shown on this PC: the one call that shows it is swapped for a line
    // that writes what it was given (WithoutShowing); every other line runs as written, and nothing sounds.
    [Test]
    public async Task TheActionOfTheTaskRunWithBaxyClosedReachesTheOrdinaryNotificationOnceWithTheWholeText()
    {
        string task = await Created(EveryDayAtTen(Words));
        string shown = WithoutShowing(task);

        ActionRun run = await RunTheAction(task, appOpen: false);

        string[] notifications = File.Exists(shown) ? await File.ReadAllLinesAsync(shown) : [];
        Assert.Multiple(() =>
        {
            Assert.That(run.Exit, Is.Zero, "the script ends by itself: " + run.Errors);
            Assert.That(notifications, Has.Length.EqualTo(1), "shown once");
            XElement toast = XElement.Parse(notifications.FirstOrDefault() ?? "<none/>");
            Assert.That(toast.Name.LocalName, Is.EqualTo("toast"));
            Assert.That(toast.Attributes(), Is.Empty, "no alarm or reminder scenario: it does not stay on the screen");
            Assert.That(toast.Descendants().Select(static element => element.Name.LocalName),
                Is.EqualTo(new[] { "visual", "binding", "text", "text" }), "no buttons and no sound of its own");
            Assert.That(toast.Descendants().Where(static element => !element.HasElements).Select(static element => element.Value),
                Is.EqualTo(new[] { "BAXY", Words }));
            Assert.That(run.Receipt?["rangUtc"]?.GetValue<string>(), Is.Not.Null);
            Assert.That(run.Receipt?["rungBy"], Is.Null);
            Assert.That(run.Receipt?["sound"]?.GetValue<string>(), Is.AnyOf("none", "toast"));
            Assert.That(run.Left, Is.EquivalentTo(new[] { task + ".ps1", task + ".fired" }), "nothing was handed over");
        });
    }

    // RUT9 (REV9 H1): the list and a run as the model reads them (OperationVisibleFacts) keep each routine whole: what
    // it says, its days, its steps' arguments. Past four levels they were cut and the mind told a weekday routine as
    // said once with nothing to say; any other operation keeps its four levels.
    [Test]
    public async Task TheListAndARunAsTheModelReadsThemKeepTheWordsTheDaysAndTheStepArguments()
    {
        await Run("""{"action":"create","at":"08:00","repeat":"days","days":["mon","tue","wed","thu","fri"],"steps":["say: buen día, a trabajar"]}""");
        await Run("""{"action":"create","phrase":"siguiente","steps":["media.control {\"action\":\"next\"}"]}""");
        OperationOutcome listed = await Run("""{"action":"list"}""");
        OperationOutcome ran = await Run("""{"action":"run","name":"siguiente"}""");

        JsonNode list = JsonNode.Parse(OperationVisibleFacts.FromOutcome("baxy.routines", listed))!;
        JsonNode run = JsonNode.Parse(OperationVisibleFacts.FromOutcome("baxy.routines", ran))!;
        JsonNode other = JsonNode.Parse(OperationVisibleFacts.FromOutcome("note.list", listed))!;
        Assert.Multiple(() =>
        {
            JsonNode weekday = list["observed"]!["routines"]![0]!;
            Assert.That(weekday["trigger"]!["days"]!.ToJsonString(), Is.EqualTo("""["mon","tue","wed","thu","fri"]"""));
            Assert.That(weekday["steps"]![0]!["say"]?.GetValue<string>(), Is.EqualTo("buen día, a trabajar"));
            Assert.That(list["observed"]!["truncated"], Is.Null);
            Assert.That(run["observed"]!["run"]!["steps"]![0]!["arguments"]!["action"]?.GetValue<string>(), Is.EqualTo("next"));
            Assert.That(other["observed"]!["truncated"]?.GetValue<bool>(), Is.True, "the four levels stay for the rest");
        });
    }

    // RUT9 (REV9 H3): with the store not written after a task was set or taken away, the tasks are left as the list is:
    // a new routine's task does not stay to speak for one the list does not have, a change keeps the words the list
    // has, a switch on that was not kept leaves no task and a delete that was not kept keeps it speaking.
    [Test]
    public async Task AStoreThatCannotBeWrittenLeavesTheTasksAsTheListIs()
    {
        await Run("""{"action":"create","name":"café","at":"16:00","repeat":"daily","steps":["say: Hora del café."]}""");
        await Run("""{"action":"create","name":"noche","at":"22:00","repeat":"daily","steps":["say: A dormir."]}""");
        await Run("""{"action":"disable","name":"noche"}""");
        string coffee = _scheduler.Tasks.Keys.Single();
        // The store's temporary file is a folder: writing it fails, as a file held by another program makes File.Replace fail.
        string blocked = Path.Combine(_root, LocalRoutineStore.FolderName, "routines.v1.json.tmp");
        Directory.CreateDirectory(blocked);

        OperationOutcome created = await Run("""{"action":"create","at":"10:00","repeat":"daily","steps":["say: hola"]}""");
        OperationOutcome changed = await Run("""{"action":"change","name":"café","steps":["say: Un cafecito."]}""");
        OperationOutcome enabled = await Run("""{"action":"enable","name":"noche"}""");
        OperationOutcome deleted = await Run("""{"action":"delete","name":"café"}""");
        Directory.Delete(blocked);

        Assert.Multiple(() =>
        {
            Assert.That(new[] { created, changed, enabled, deleted }.Select(static outcome => outcome.ErrorCode),
                Is.All.EqualTo("routines_write_failed"));
            Assert.That(_scheduler.Tasks.Keys, Is.EqualTo(new[] { coffee }), "only the task of the routine the list has on");
            Assert.That(ScheduledRingScript.ReadTitle(Script(coffee)), Is.EqualTo("Hora del café."));
            Assert.That(Store().Read().Select(static routine => routine["name"]!.GetValue<string>()),
                Is.EqualTo(new[] { "café", "noche" }));
        });
    }

    // RUT9 (REV9 H9): a routine named after its clock is found by that clock as the list says it («9:55») and as the mind
    // folds it («9 55»), with or without the hour's leading zero.
    [TestCase("9:55")]
    [TestCase("9 55")]
    [TestCase("09:55")]
    public async Task ARoutineAtATimeIsFoundByItsClockAsItIsSaid(string said)
    {
        await Run("""{"action":"create","at":"09:55","repeat":"daily","steps":["say: buen día"]}""");

        OperationOutcome off = await Run(new JsonObject { ["action"] = "disable", ["name"] = said }.ToJsonString());

        Assert.That(off.Succeeded, Is.True, off.ErrorCode);
    }

    // RUT9 (REV9 H10): a routine said once leaves the list after its time, and its task goes too once it said it (its
    // receipt is there); one whose time passed with the PC off and that has not said it yet keeps its task to say it late.
    [Test]
    public async Task ARoutineSaidOnceTakesItsTaskAwayOnceItSaidIt()
    {
        string said = Id(await Run("""{"action":"create","name":"ropa","at":"22:15","steps":["say: Saca la ropa."]}"""));
        string late = Id(await Run("""{"action":"create","name":"luz","at":"22:20","steps":["say: Apaga la luz."]}"""));
        var tasks = new RoutineSayTasks(_root, _scheduler);
        File.WriteAllText(Path.Combine(_root, ScheduledRingTasks.FolderName, tasks.TaskName(said) + ScheduledRingTasks.ReceiptExtension), "{}");

        _clock.Now = Now.AddHours(1);
        OperationOutcome listed = await Run("""{"action":"list"}""");

        Assert.Multiple(() =>
        {
            Assert.That(Result(listed)["count"]!.GetValue<int>(), Is.EqualTo(0));
            Assert.That(_scheduler.Tasks.Keys, Is.EqualTo(new[] { tasks.TaskName(late) }));
            Assert.That(File.Exists(Script(tasks.TaskName(said))), Is.False);
        });
    }

    // RUT9 (REV9 H5): a routines file that cannot be read is never moved or deleted by a call (the panel lists by itself:
    // the list would empty with nobody told); every call says it is damaged and the way out, «Olvidar todo», and the
    // tasks stay as they were.
    [Test]
    public async Task ADamagedRoutinesFileIsSaidWithItsWayOutAndLeftAsItIs()
    {
        await Run("""{"action":"create","name":"café","at":"16:00","repeat":"daily","steps":["say: Hora del café."]}""");
        string file = Path.Combine(_root, LocalRoutineStore.FolderName, "routines.v1.json");
        File.WriteAllText(file, "{\"routines\":[{\"id\":\"r-000001\",\"order\":\"apaga");
        byte[] before = File.ReadAllBytes(file);

        OperationOutcome[] calls =
        [
            await Run("""{"action":"list"}"""),
            await Run("""{"action":"create","phrase":"cine","order":"baja la luz"}"""),
            await Run("""{"action":"delete","name":"café"}"""),
        ];

        Assert.Multiple(() =>
        {
            Assert.That(calls.Select(static outcome => outcome.ErrorCode), Is.All.EqualTo("routines_unreadable"));
            Assert.That(calls.Select(static outcome => Result(outcome)["damaged"]?.GetValue<bool>()), Is.All.True);
            Assert.That(Result(calls[0])["next"]!.GetValue<string>(), Does.Contain("«Olvidar todo»"));
            Assert.That(File.ReadAllBytes(file), Is.EqualTo(before));
            Assert.That(Directory.GetFiles(Path.GetDirectoryName(file)!).Select(Path.GetFileName),
                Is.EquivalentTo(new[] { "routines.v1.json" }));
            Assert.That(_scheduler.Tasks, Has.Count.EqualTo(1));
        });
    }

    // RUT9 (second blind review): a clock without its leading zero finds only a routine at a time, and only when no
    // routine has that name as it was said: a phrase routine named «8:00» is never the routine «08:00».
    [Test]
    public async Task AClockWithoutItsZeroIsNeverAnotherRoutinesName()
    {
        await Run("""{"action":"create","at":"08:00","repeat":"daily","steps":["say: Buen día."]}""");
        await Run("""{"action":"create","name":"8:00","phrase":"ocho","order":"baja la luz"}""");

        OperationOutcome phrase = await Run("""{"action":"disable","name":"8:00"}""");
        OperationOutcome clock = await Run("""{"action":"disable","name":"08:00"}""");

        Assert.Multiple(() =>
        {
            Assert.That(Result(phrase)["routine"]!["trigger"]!["phrase"]?.GetValue<string>(), Is.EqualTo("ocho"));
            Assert.That(Result(clock)["routine"]!["trigger"]!["at"]?.GetValue<string>(), Is.EqualTo("08:00"));
            Assert.That(_scheduler.Tasks, Is.Empty);
        });
    }

    // REM2 (REV13 B-3): a routine named by its clock (the person gave it no name) follows its new clock: «08:00» moved to
    // 22:00 kept «08:00», a new one at 8 was «08:00 (2)», and «borra la rutina 08:00» deleted the one at 22:00. A name of
    // the person's own stays as it is.
    [Test]
    public async Task ARoutineNamedByItsClockFollowsItsNewClock()
    {
        await Run("""{"action":"create","at":"08:00","repeat":"daily","steps":["say: A trabajar."]}""");
        await Run("""{"action":"create","at":"09:00","repeat":"daily","steps":["say: Café."]}""");
        await Run("""{"action":"create","at":"09:00","repeat":"daily","steps":["say: Pausa."]}""");
        await Run("""{"action":"create","name":"ánimo","at":"07:00","repeat":"daily","steps":["say: Ánimo."]}""");

        OperationOutcome moved = await Run("""{"action":"change","name":"08:00","at":"22:00","repeat":"daily"}""");
        OperationOutcome second = await Run("""{"action":"change","name":"09:00 (2)","at":"23:00","repeat":"daily"}""");
        OperationOutcome taken = await Run("""{"action":"change","name":"09:00","at":"22:00","repeat":"daily"}""");
        OperationOutcome named = await Run("""{"action":"change","name":"ánimo","at":"06:00","repeat":"daily"}""");
        OperationOutcome eight = await Run("""{"action":"create","at":"08:00","repeat":"daily","steps":["say: Hola."]}""");

        Assert.Multiple(() =>
        {
            Assert.That(Result(moved)["routine"]!["name"]!.GetValue<string>(), Is.EqualTo("22:00"));
            Assert.That(Result(second)["routine"]!["name"]!.GetValue<string>(), Is.EqualTo("23:00"));
            Assert.That(Result(taken)["routine"]!["name"]!.GetValue<string>(), Is.EqualTo("22:00 (2)"));
            Assert.That(Result(named)["routine"]!["name"]!.GetValue<string>(), Is.EqualTo("ánimo"));
            Assert.That(Result(eight)["routine"]!["name"]!.GetValue<string>(), Is.EqualTo("08:00"));
        });
    }

    private static string Id(OperationOutcome outcome) => Result(outcome)["routine"]!["id"]!.GetValue<string>();

    private string Script(string task) => Path.Combine(_root, ScheduledRingTasks.FolderName, task + ".ps1");

    private static string EveryDayAtTen(string words) => new JsonObject
    {
        ["action"] = "create",
        ["at"] = "10:00",
        ["repeat"] = "daily",
        ["steps"] = new JsonArray("say: " + words),
    }.ToJsonString();

    // Runs the call and returns the task it set.
    private async Task<string> Created(string json)
    {
        string[] before = [.. _scheduler.Tasks.Keys];
        OperationOutcome outcome = await Run(json);
        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        return _scheduler.Tasks.Keys.Except(before).Single();
    }

    private static void AssertStart(XElement task, string kind, DateTimeOffset asked)
    {
        XElement trigger = task.Element(TaskNs + "Triggers")!.Elements().Single();
        string start = trigger.Element(TaskNs + "StartBoundary")!.Value;
        Assert.That(trigger.Name, Is.EqualTo(TaskNs + kind));
        Assert.That(start, Does.Match(@"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"));
        Assert.That(XmlConvert.ToDateTimeOffset(start), Is.EqualTo(asked));
        Assert.That(XmlConvert.ToDateTimeOffset(start).Offset, Is.EqualTo(TimeZoneInfo.Local.GetUtcOffset(asked)));
    }

    // This PC never shows a routine's notification: the script's one Show is swapped for a line that appends the
    // notification's XML, as Windows loaded it, to the file returned. A script without exactly that call, or with
    // anything that sounds, is not run at all.
    private string WithoutShowing(string task)
    {
        string shown = Path.Combine(_root, "shown.txt");
        string script = File.ReadAllText(Script(task));
        string guarded = script.Replace(ShowCall, "[IO.File]::AppendAllText([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
            + Convert.ToBase64String(Encoding.UTF8.GetBytes(shown)) + "')),$note.Content.GetXml()+[char]10)", StringComparison.Ordinal);
        Assert.That(script.Split(ShowCall), Has.Length.EqualTo(2), "the script shows its notification with one call");
        Assert.That(guarded, Does.Not.Contain("Show(").And.Not.Contain("PlaySync").And.Not.Contain("Beep"),
            "nothing may be shown or sound on this PC");
        File.WriteAllText(Script(task), guarded, new UTF8Encoding(false));
        return shown;
    }

    // The task's action as the Task Scheduler runs it: the command (its environment variables expanded) and the
    // arguments of the task's XML, with no window. The open App is the hand-over's real other side, without the voice.
    private async Task<ActionRun> RunTheAction(string task, bool appOpen)
    {
        XElement exec = XDocument.Parse(_scheduler.Xml[task]).Descendants(TaskNs + "Exec").Single();
        string alarms = AlarmRingHandoff.Folder(_root);
        using Mutex? held = appOpen ? new Mutex(false, AlarmRingHandoff.MutexName(alarms)) : null;
        var taken = new List<AlarmRingHandoff.Ring>();

        (int? exit, _, string errors) = await Ended(
            Hidden(Environment.ExpandEnvironmentVariables(exec.Element(TaskNs + "Command")!.Value),
                exec.Element(TaskNs + "Arguments")!.Value),
            () =>
            {
                foreach (string due in appOpen ? Directory.GetFiles(alarms, "BAXY-*" + AlarmRingHandoff.DueExtension) : [])
                {
                    if (AlarmRingHandoff.Take(due) is not { } ring) continue;
                    taken.Add(ring);
                    if (ring.Kind == AlarmRingHandoff.SayKind) AlarmRingHandoff.End(alarms, ring.TaskName);
                }
            });

        string receipt = Path.Combine(alarms, task + ScheduledRingTasks.ReceiptExtension);
        return new ActionRun(exit, taken, File.Exists(receipt) ? JsonNode.Parse(await File.ReadAllTextAsync(receipt)) : null,
            [.. Directory.GetFiles(alarms).Select(static file => Path.GetFileName(file))], errors);
    }

    private static ProcessStartInfo Hidden(string command, string arguments) => new(command, arguments)
    {
        UseShellExecute = false,
        CreateNoWindow = true,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
    };

    // Runs it to its end, doing <paramref name="meanwhile"/> as it runs; one that outlives the limit is ended by its own
    // handle (never by name) and has no exit code.
    private static async Task<(int? Exit, string Output, string Errors)> Ended(ProcessStartInfo start, Action meanwhile)
    {
        using Process process = Process.Start(start)!;
        Task<string> output = process.StandardOutput.ReadToEndAsync();
        Task<string> errors = process.StandardError.ReadToEndAsync();
        Stopwatch running = Stopwatch.StartNew();
        while (!process.HasExited && running.Elapsed < Limit)
        {
            meanwhile();
            await Task.Delay(50);
        }

        bool ended = process.HasExited;
        if (!ended)
        {
            process.Kill(entireProcessTree: true);
        }

        await process.WaitForExitAsync();
        return (ended ? process.ExitCode : null, await output, await errors);
    }

    private LocalRoutineStore Store() => new(Path.Combine(_root, LocalRoutineStore.FolderName));

    private async Task<OperationOutcome> Run(string json)
    {
        var handler = new RoutinesHandler(_root, _clock, new RoutineSayTasks(_root, _scheduler));
        using JsonDocument arguments = JsonDocument.Parse(json);
        return await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()),
            CancellationToken.None);
    }

    private static JsonObject Result(OperationOutcome outcome) =>
        JsonNode.Parse(outcome.Result!.Value.GetRawText())!.AsObject();

    // The PC's sound outputs as audio.device.list reads them; every other call is a test's mistake.
    private sealed class Devices(params string[] outputs) : IExternalCapabilityProvider
    {
        internal List<string> Asked { get; } = [];

        internal bool Fails { get; init; }

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken)
        {
            Asked.Add(operation);
            if (operation != "audio.device.list")
            {
                throw new AssertionException("only the devices are read: " + operation);
            }

            if (Fails)
            {
                return ValueTask.FromResult(ExternalJson.Failure(operation, "audio_device_failed"));
            }

            var listed = new JsonObject
            {
                ["version"] = 1,
                ["outputs"] = new JsonArray(outputs.Select((name, index) =>
                    (JsonNode?)new JsonObject { ["name"] = name, ["default"] = index == 0 }).ToArray()),
                ["inputs"] = new JsonArray(),
            };
            using JsonDocument document = JsonDocument.Parse(listed.ToJsonString());
            return ValueTask.FromResult(ExternalJson.Success(operation, document.RootElement.Clone(), effectObserved: false));
        }

        public ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
    }

    private sealed class Clock(DateTimeOffset now) : TimeProvider
    {
        internal DateTimeOffset Now { get; set; } = now;

        public override TimeZoneInfo LocalTimeZone => Zone;

        public override DateTimeOffset GetUtcNow() => Now.ToUniversalTime();
    }

    // The Task Scheduler as RoutineSayTasks asks it: a registered task's next run is its trigger's start.
    private sealed class FakeScheduler : ITaskSchedulerHost
    {
        internal Dictionary<string, ScheduledTaskSnapshot> Tasks { get; } = new(StringComparer.OrdinalIgnoreCase);

        internal Dictionary<string, string> Xml { get; } = new(StringComparer.OrdinalIgnoreCase);

        internal int Opened { get; private set; }

        internal Exception? OpenFailure { get; set; }

        internal bool NoNextRun { get; set; }

        internal Exception? FindFailure { get; set; }

        public ITaskSchedulerSession Open()
        {
            if (OpenFailure is not null) throw OpenFailure;
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

            public ScheduledTaskSnapshot? Find(string name) =>
                owner.FindFailure is { } failure ? throw failure : owner.Tasks.GetValueOrDefault(name);

            public void Register(string name, string xml)
            {
                string start = Regex.Match(xml, "<StartBoundary>([^<]+)</StartBoundary>").Groups[1].Value;
                DateTime? next = owner.NoNextRun
                    ? null
                    : DateTimeOffset.Parse(start, System.Globalization.CultureInfo.InvariantCulture).LocalDateTime;
                owner.Tasks[name] = new ScheduledTaskSnapshot(name, 3, next, null, 0);
                owner.Xml[name] = xml;
            }

            public void Delete(string name)
            {
                owner.Tasks.Remove(name);
                owner.Xml.Remove(name);
            }

            public void Dispose()
            {
            }
        }
    }
}
