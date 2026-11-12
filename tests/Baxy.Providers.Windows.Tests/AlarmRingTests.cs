using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Xml.Linq;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// ALR1: an alarm or a reminder rings as a phone's does. The ring script hands the ring to the open App (or rings
/// Windows' alarm or reminder notification), and schedule.alarms stops or snoozes the one ringing now, by its id.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class AlarmRingTests
{
    private const string Alarm = "BAXY-Alarm-0123456789abcdef0123456789abcdef";
    private const string Reminder = "BAXY-Reminder-fedcba9876543210fedcba9876543210";
    private const string SecondAlarm = "BAXY-Alarm-00112233445566778899aabbccddeeff";

    [Test]
    public async Task StopEndsTheRingTheOpenAppRingsAndSaysWhichOne()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Alarm, "sal a trabajar", "07:00");

        ExternalCapabilityReceipt receipt = await Adapter(temporary).InvokeAsync(
            "schedule.alarms", Json("""{"action":"stop","id":"89abcdef"}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(result.GetProperty("stopped").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("ringing").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("kind").GetString(), Is.EqualTo("alarm"));
            Assert.That(result.GetProperty("title").GetString(), Is.EqualTo("sal a trabajar"));
            Assert.That(result.GetProperty("clock").GetString(), Is.EqualTo("07:00"));
            Assert.That(app.Answers, Is.EqualTo(new[] { Alarm + ":stop" }));
            Assert.That(AlarmRingHandoff.IsRinging(temporary.Alarms, Alarm), Is.False);
        });
    }

    [Test]
    public async Task SnoozeSetsAOneTimeRingOfTheSameKindAndTitleThenEndsThisOne()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Reminder, "comprar pan", "15:00");
        var backend = ScriptedNotificationBackend.Registering();
        DateTimeOffset before = DateTimeOffset.UtcNow;

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms", Json("""{"action":"snooze","id":"76543210","inMinutes":5}"""),
                CancellationToken.None);

        ScheduledNotificationRequest set = backend.Requests.Single(request => request.Mode == "schedule");
        DateTimeOffset due = DateTimeOffset.Parse(set.DueUtc!, CultureInfo.InvariantCulture);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result!.Value.GetProperty("snoozed").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("inMinutes").GetInt32(), Is.EqualTo(5));
            Assert.That(receipt.Result!.Value.GetProperty("dueLocal").GetString(), Is.Not.Empty);
            Assert.That(set.Kind, Is.EqualTo("reminder"));
            Assert.That(due - before, Is.InRange(TimeSpan.FromMinutes(4.9), TimeSpan.FromMinutes(5.2)));
            Assert.That(ScheduledRingScript.ReadTitle(set.RingScriptPath!), Is.EqualTo("comprar pan"));
            Assert.That(app.Answers, Is.EqualTo(new[] { Reminder + ":snooze" }));
        });
    }

    [Test]
    public async Task ASnoozeWithNoMinutesIsTenAsAndroidsClock()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Alarm, null, "07:00");
        var backend = ScriptedNotificationBackend.Registering();
        DateTimeOffset before = DateTimeOffset.UtcNow;

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms", Json("""{"action":"snooze"}"""), CancellationToken.None);

        DateTimeOffset due = DateTimeOffset.Parse(backend.Requests[^1].DueUtc!, CultureInfo.InvariantCulture);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(due - before, Is.InRange(TimeSpan.FromMinutes(9.9), TimeSpan.FromMinutes(10.2)));
            Assert.That(ScheduledRingScript.ReadTitle(backend.Requests[^1].RingScriptPath!), Is.Null);
        });
    }

    // ALR5 (B4): «recuérdamelo a las cuatro» while it rings. Snooze took only minutes, so the model snoozed ten and
    // said the time asked, or wrote a cancel with that time. at is when it rings again: a local clock time, the next
    // time the clock shows it (written with its date, the same minute); the receipt says the time it was set for.
    [TestCase(false)]
    [TestCase(true)]
    public async Task ASnoozeAtATimeRingsAgainAtThatTimeAndSaysIt(bool dated)
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Reminder, "comprar pan", "15:00");
        var backend = ScriptedNotificationBackend.Registering();
        DateTime asked = DateTime.Now.AddHours(2);
        asked = asked.AddTicks(-(asked.Ticks % TimeSpan.TicksPerMinute));
        string at = asked.ToString(dated ? "yyyy-MM-ddTHH:mm" : "HH:mm", CultureInfo.InvariantCulture);

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms", Json($$"""{"action":"snooze","id":"76543210","at":"{{at}}"}"""),
                CancellationToken.None);

        ScheduledNotificationRequest? set = backend.Requests.SingleOrDefault(request => request.Mode == "schedule");
        JsonElement result = receipt.Result ?? default;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(set, Is.Not.Null);
            Assert.That(set is null ? default : DateTimeOffset.Parse(set.DueUtc!, CultureInfo.InvariantCulture)
                .LocalDateTime, Is.EqualTo(asked));
            Assert.That(set?.Kind, Is.EqualTo("reminder"));
            Assert.That(result.ValueKind == JsonValueKind.Object && result.TryGetProperty("dueLocal", out JsonElement due)
                ? due.GetString() : null, Is.EqualTo(asked.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture)));
            Assert.That(result.ValueKind == JsonValueKind.Object && result.TryGetProperty("inMinutes", out _), Is.False);
            Assert.That(app.Answers, Is.EqualTo(new[] { Reminder + ":snooze" }));
        });
    }

    // A clock time that has passed today is tomorrow's, and the receipt says it moved (as create's).
    [Test]
    public async Task ASnoozeAtAClockTimeThatPassedTodayIsTomorrowsAndSaysSo()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Alarm, null, "07:00");
        var backend = ScriptedNotificationBackend.Registering();
        DateTime asked = DateTime.Now.AddMinutes(-2);
        if (asked.Date != DateTime.Now.Date) Assert.Ignore("the first minutes of the day have no clock time passed today");
        asked = asked.AddTicks(-(asked.Ticks % TimeSpan.TicksPerMinute)).AddDays(1);

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms", Json($$"""{"action":"snooze","at":"{{Clock(asked)}}"}"""),
                CancellationToken.None);

        ScheduledNotificationRequest? set = backend.Requests.SingleOrDefault(request => request.Mode == "schedule");
        JsonElement result = receipt.Result ?? default;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(set is null ? default : DateTimeOffset.Parse(set.DueUtc!, CultureInfo.InvariantCulture)
                .LocalDateTime, Is.EqualTo(asked));
            Assert.That(result.ValueKind == JsonValueKind.Object && result.TryGetProperty("movedToNextDay", out JsonElement
                moved) && moved.GetBoolean(), Is.True);
            Assert.That(result.ValueKind == JsonValueKind.Object && result.TryGetProperty("scheduledFor", out JsonElement
                day) ? day.GetString() : null, Is.EqualTo("tomorrow"));
        });
    }

    // ALR5's blind review: «pospón la alarma de las 7» written with its id and its own clock as at moved it to the next
    // day. The clock of the one ringing names it, with an id too: it is snoozed the default ten minutes.
    [TestCase(true)]
    [TestCase(false)]
    public async Task ASnoozeAtTheClockOfTheOneRingingNamesItAndIsTenMinutes(bool withId)
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Reminder, "comprar pan", "15:00");
        var backend = ScriptedNotificationBackend.Registering();
        DateTimeOffset before = DateTimeOffset.UtcNow;

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms",
                Json(withId ? """{"action":"snooze","id":"76543210","at":"15:00"}""" : """{"action":"snooze","at":"15:00"}"""),
                CancellationToken.None);

        DateTimeOffset due = DateTimeOffset.Parse(backend.Requests[^1].DueUtc!, CultureInfo.InvariantCulture);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(due - before, Is.InRange(TimeSpan.FromMinutes(9.9), TimeSpan.FromMinutes(10.2)));
            Assert.That(receipt.Result!.Value.GetProperty("inMinutes").GetInt32(), Is.EqualTo(10));
        });
    }

    // The minutes win over at, as in create.
    [Test]
    public async Task ASnoozeWithMinutesAndATimeGoesByTheMinutes()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Reminder, "comprar pan", "15:00");
        var backend = ScriptedNotificationBackend.Registering();
        DateTimeOffset before = DateTimeOffset.UtcNow;

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms",
                Json($$"""{"action":"snooze","inMinutes":20,"at":"{{Clock(DateTime.Now.AddHours(3))}}"}"""),
                CancellationToken.None);

        DateTimeOffset due = DateTimeOffset.Parse(backend.Requests[^1].DueUtc!, CultureInfo.InvariantCulture);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(due - before, Is.InRange(TimeSpan.FromMinutes(19.9), TimeSpan.FromMinutes(20.2)));
            Assert.That(receipt.Result!.Value.GetProperty("inMinutes").GetInt32(), Is.EqualTo(20));
        });
    }

    // A date and time that is not the next time the clock shows that time (for «tomorrow at nine» the model wrote
    // today's date, already past, or the day after tomorrow's, and said «tomorrow») sets nothing, the ring rings on, and
    // the refusal ends with the same call at that clock time alone, as create's (DuePassed). One that is no time says so.
    [TestCase("2020-01-01T08:00", true)]
    [TestCase("+2", true)]
    [TestCase("más tarde", false)]
    public async Task ASnoozeAtADateThatIsNotTheNextTimeOfThatClockOrIsNoTimeSetsNothingAndItRingsOn(string at, bool date)
    {
        string day = at.StartsWith('+')
            ? DateTime.Now.AddDays(2).ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) : "2020-01-01";
        if (date) at = day + "T08:00";
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Reminder, "comprar pan", "15:00");
        var backend = ScriptedNotificationBackend.Registering();

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms", Json($$"""{"action":"snooze","id":"76543210","at":"{{at}}"}"""),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_snooze_invalid"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(backend.Requests.Where(request => request.Mode == "schedule"), Is.Empty);
            Assert.That(app.Answers, Is.Empty);
            Assert.That(AlarmRingHandoff.IsRinging(temporary.Alarms, Reminder), Is.True);
            Assert.That(receipt.Result is { } result && result.TryGetProperty("next", out JsonElement next)
                ? next.GetString() : null, date
                    ? Does.StartWith("nothing was snoozed: a snooze reaches the next 24 hours and " + day
                        + " 08:00 is not in them (it is ").And.EndsWith(
                        ", call " + Baxy.Kernel.Operations.WireNames.Call("schedule.alarms", new()
                        {
                            ["action"] = "snooze", ["id"] = "76543210", ["at"] = "08:00",
                        }))
                    : (NUnit.Framework.Constraints.IResolveConstraint)Is.EqualTo("nothing was snoozed: at is not a local clock time (HH:mm, the next time the clock "
                        + "shows it); say when with at or with inMinutes"));
            Assert.That(receipt.Result is { } rings && rings.TryGetProperty("ringingNow", out JsonElement now)
                ? now.GetArrayLength() : 0, Is.EqualTo(1));
        });
    }

    // With no id a snooze answers every one ringing; at is when they ring again, not which one (stop's at still is).
    [Test]
    public async Task ASnoozeAtATimeWithNoIdSnoozesEveryOneRingingToThatTime()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Alarm, "sal a trabajar", "07:00");
        app.Rings(Reminder, "comprar pan", "07:05");
        var backend = ScriptedNotificationBackend.Registering();
        DateTime asked = DateTime.Now.AddHours(2);
        asked = asked.AddTicks(-(asked.Ticks % TimeSpan.TicksPerMinute));

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms", Json($$"""{"action":"snooze","at":"{{Clock(asked)}}"}"""),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(backend.Requests.Where(request => request.Mode == "schedule").Select(request =>
                DateTimeOffset.Parse(request.DueUtc!, CultureInfo.InvariantCulture).LocalDateTime),
                Is.EqualTo(new[] { asked, asked }));
            Assert.That(app.Answers, Is.EquivalentTo(new[] { Alarm + ":snooze", Reminder + ":snooze" }));
        });
    }

    // ALR5: the App did not end the ring in time (AnswerWait). The new ring is set and read back before this one is
    // answered, so the receipt says it: snoozed:true beside its inMinutes and dueLocal, and ringing:true for the one
    // still heard. It said snoozed:false, and the model told the person nothing had been snoozed while it rang again
    // in five minutes. A stop not seen to end stays stopped:false.
    [TestCase("snooze", true)]
    [TestCase("stop", false)]
    public async Task AnAnswerTheAppDidNotEndInTimeSaysWhatWasSetAndThatItStillRings(string action, bool said)
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms, ends: false);
        app.Rings(Reminder, "comprar pan", "15:00");
        var backend = ScriptedNotificationBackend.Registering();
        TimeSpan wait = WindowsScheduledNotificationAdapter.AnswerWait;
        WindowsScheduledNotificationAdapter.AnswerWait = TimeSpan.FromMilliseconds(300);
        ExternalCapabilityReceipt receipt;
        try
        {
            receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend).InvokeAsync(
                "schedule.alarms", Json($$"""{"action":"{{action}}","id":"76543210","inMinutes":5}"""),
                CancellationToken.None);
        }
        finally
        {
            WindowsScheduledNotificationAdapter.AnswerWait = wait;
        }

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_ring_answer_unconfirmed"));
            Assert.That(result.GetProperty(action == "stop" ? "stopped" : "snoozed").GetBoolean(), Is.EqualTo(said));
            Assert.That(result.GetProperty("ringing").GetBoolean(), Is.True);
            Assert.That(backend.Requests.Count(request => request.Mode == "schedule"), Is.EqualTo(said ? 1 : 0));
            Assert.That(result.TryGetProperty("dueLocal", out _), Is.EqualTo(said));
            Assert.That(receipt.EffectObserved, Is.EqualTo(said));
        });
    }

    [Test]
    public async Task StopWithNothingRingingStopsNothingAndSaysSo()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);

        ExternalCapabilityReceipt receipt = await Adapter(temporary).InvokeAsync(
            "schedule.alarms", Json("""{"action":"stop"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("ringingFound").GetBoolean(), Is.False);
            Assert.That(app.Answers, Is.Empty);
        });
    }

    [TestCase("""{"action":"stop","id":"00000000"}""", "notification_ring_not_found")]
    [TestCase("""{"action":"snooze","id":"00000000"}""", "notification_ring_not_found")]
    [TestCase("""{"action":"stop","kind":"reminder"}""", "notification_ring_not_found")]
    [TestCase("""{"action":"snooze","inMinutes":0}""", "notification_snooze_invalid")]
    [TestCase("""{"action":"stop","at":"08:00"}""", "notification_ring_not_found")]
    [TestCase("""{"action":"stop","at":"las siete"}""", "notification_clock_selector_invalid")]
    public async Task AnAnswerThatNamesNoRingingOneAnswersNothingAndSaysWhatRings(string arguments, string code)
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Alarm, "sal a trabajar", "07:00");
        var backend = ScriptedNotificationBackend.Registering();

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms", Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(backend.Requests, Is.Empty);
            Assert.That(app.Answers, Is.Empty);
            Assert.That(AlarmRingHandoff.IsRinging(temporary.Alarms, Alarm), Is.True);
        });
        if (code == "notification_ring_not_found")
        {
            Assert.That(receipt.Result!.Value.GetProperty("ringingNow")[0].GetProperty("id").GetString(),
                Is.EqualTo("89abcdef"));
        }
    }

    // ALR3 (F9 of VIVO1): with several ringing, a stop that names none stops every one, and its receipt says each.
    [Test]
    public async Task TwoRingingAndNoIdStopsBothInOneCallAndSaysEach()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Alarm, "sal a trabajar", "07:00");
        app.Rings(Reminder, "comprar pan", "07:00");

        ExternalCapabilityReceipt receipt = await Adapter(temporary).InvokeAsync(
            "schedule.alarms", Json("""{"action":"stop"}"""), CancellationToken.None);

        JsonElement[] rings = receipt.Result is { } result && result.TryGetProperty("rings", out JsonElement each)
            ? [.. each.EnumerateArray()]
            : [];
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(rings.Select(ring => ring.GetProperty("id").GetString()),
                Is.EquivalentTo(new[] { "89abcdef", "76543210" }));
            Assert.That(rings.All(ring => ring.GetProperty("stopped").GetBoolean()
                && !ring.GetProperty("ringing").GetBoolean()), Is.True);
            Assert.That(app.Answers, Is.EquivalentTo(new[] { Alarm + ":stop", Reminder + ":stop" }));
            Assert.That(AlarmRingHandoff.Ringing(temporary.Alarms), Is.Empty);
        });
    }

    [Test]
    public async Task NoIdSnoozesEveryOneRingingOfTheKindGivenAndLeavesTheOtherRinging()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Alarm, "sal a trabajar", "07:00");
        app.Rings(SecondAlarm, null, "07:05");
        app.Rings(Reminder, "comprar pan", "07:00");
        var backend = ScriptedNotificationBackend.Registering();

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms", Json("""{"action":"snooze","kind":"alarm","inMinutes":5}"""),
                CancellationToken.None);

        JsonElement[] rings = receipt.Result is { } result && result.TryGetProperty("rings", out JsonElement each)
            ? [.. each.EnumerateArray()]
            : [];
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(rings.Select(ring => ring.GetProperty("id").GetString()),
                Is.EquivalentTo(new[] { "89abcdef", "ccddeeff" }));
            Assert.That(rings.All(ring => ring.GetProperty("snoozed").GetBoolean()
                && ring.GetProperty("inMinutes").GetInt32() == 5), Is.True);
            Assert.That(backend.Requests.Where(request => request.Mode == "schedule").Select(request => request.Kind),
                Is.EqualTo(new[] { "alarm", "alarm" }));
            Assert.That(app.Answers, Is.EquivalentTo(new[] { Alarm + ":snooze", SecondAlarm + ":snooze" }));
            Assert.That(AlarmRingHandoff.IsRinging(temporary.Alarms, Reminder), Is.True);
        });
    }

    // ALR2 measured the model naming «la de las siete y cinco» by at, which stop ignored: at names the ones ringing at
    // that local clock, as cancel's does; an id names one whatever else rings.
    [TestCase("""{"action":"stop","at":"7:05"}""", SecondAlarm)]
    [TestCase("""{"action":"stop","at":"07:05","kind":"alarm"}""", SecondAlarm)]
    [TestCase("""{"action":"stop","id":"76543210"}""", Reminder)]
    public async Task AtOrAnIdAnswersOnlyTheOneItNamesWhileOthersRing(string arguments, string named)
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Alarm, "sal a trabajar", "07:00");
        app.Rings(SecondAlarm, "regar", "07:05");
        app.Rings(Reminder, "comprar pan", "07:00");

        ExternalCapabilityReceipt receipt = await Adapter(temporary).InvokeAsync(
            "schedule.alarms", Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result!.Value.GetProperty("id").GetString(),
                Is.EqualTo(AlarmRingHandoff.Id(named)));
            Assert.That(receipt.Result!.Value.GetProperty("stopped").GetBoolean(), Is.True);
            Assert.That(app.Answers, Is.EqualTo(new[] { named + ":stop" }));
            Assert.That(AlarmRingHandoff.Ringing(temporary.Alarms).Select(ring => ring.TaskName),
                Is.EquivalentTo(new[] { Alarm, SecondAlarm, Reminder }.Where(task => task != named)));
        });
    }

    [Test]
    public async Task ARingNoAppHoldsRingsNowhereAndIsCleared()
    {
        using TemporaryDirectory temporary = new();
        using (OpenApp app = new(temporary.Alarms))
        {
            app.Rings(Alarm, "sal a trabajar", "07:00");
        }

        ExternalCapabilityReceipt receipt = await Adapter(temporary).InvokeAsync(
            "schedule.alarms", Json("""{"action":"stop"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("ringingFound").GetBoolean(), Is.False);
            Assert.That(AlarmRingHandoff.IsRinging(temporary.Alarms, Alarm), Is.False);
        });
    }

    // INT16, blind review: a hand-over whose name is not a ring task's (BAXY-Alarm- or BAXY-Reminder- and 32 hex, as
    // ScheduledRingScript names them) is no ring of BAXY's: taken, a short name broke the App's ring card (TaskName[^32..])
    // and with it the loop that rings.
    [TestCase("BAXY-Alarm-abcdefgh")]
    [TestCase("BAXY-Reminder-0123456789ABCDEF0123456789ABCDEF")]
    [TestCase("BAXY-Alarm-x0123456789abcdef0123456789abcdef")]
    public void AHandOverThatIsNoRingTasksIsNotTaken(string name)
    {
        using TemporaryDirectory temporary = new();
        Directory.CreateDirectory(temporary.Alarms);
        string due = Path.Combine(temporary.Alarms, name + ".due");
        File.WriteAllText(due, "{}");

        Assert.Multiple(() =>
        {
            Assert.That(AlarmRingHandoff.Take(due), Is.Null);
            Assert.That(File.Exists(due), Is.True, "left as it was");
        });
    }

    [Test]
    public async Task TheListSaysWhatRingsNow()
    {
        using TemporaryDirectory temporary = new();
        using OpenApp app = new(temporary.Alarms);
        app.Rings(Reminder, "comprar pan", "15:00");
        const string none = """{"ok":true,"schedulerRunning":true,"tasks":[]}""";

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(
                temporary.Path, ScriptedNotificationBackend.Lines(none))
            .InvokeAsync("schedule.alarms", Json("""{"action":"list"}"""), CancellationToken.None);

        JsonElement ringing = receipt.Result!.Value.GetProperty("ringingNow");
        Assert.Multiple(() =>
        {
            Assert.That(ringing.GetArrayLength(), Is.EqualTo(1));
            Assert.That(ringing[0].GetProperty("id").GetString(), Is.EqualTo("76543210"));
            Assert.That(ringing[0].GetProperty("kind").GetString(), Is.EqualTo("reminder"));
            Assert.That(ringing[0].GetProperty("title").GetString(), Is.EqualTo("comprar pan"));
        });
    }

    [TestCase(null, true)]
    [TestCase("daily", true)]
    [TestCase("hourly", false)]
    public async Task ACreatedRingScriptHandsOverToTheOpenAppAndKnowsItsTime(string? recurrence, bool knowsTime)
    {
        using TemporaryDirectory temporary = new();
        var backend = ScriptedNotificationBackend.Registering();
        DateTimeOffset due = DateTimeOffset.Now.AddHours(2);
        string clock = due.ToString("HH:mm", CultureInfo.InvariantCulture);
        string repeat = recurrence is null ? "" : $",\"recurrence\":\"{recurrence}\"";

        ExternalCapabilityReceipt receipt = await new WindowsScheduledNotificationAdapter(temporary.Path, backend)
            .InvokeAsync("schedule.alarms",
                Json($$"""{"action":"create","kind":"alarm","at":"{{clock}}","title":"sal a trabajar"{{repeat}}}"""),
                CancellationToken.None);

        string script = await File.ReadAllTextAsync(backend.Requests[^1].RingScriptPath!);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(script, Does.StartWith(ScheduledRingScript.Marker + "\n"));
            Assert.That(script, Does.Contain(AlarmRingHandoff.MutexName(temporary.Alarms)));
            Assert.That(script.Contains($"$clock='{clock}'", StringComparison.Ordinal), Is.EqualTo(knowsTime));
            Assert.That(ScheduledRingScript.ReadTitle(backend.Requests[^1].RingScriptPath!), Is.EqualTo("sal a trabajar"));
        });
    }

    [TestCase("alarm", "ms-winsoundevent:Notification.Looping.Alarm", "true")]
    [TestCase("reminder", "ms-winsoundevent:Notification.Reminder", null)]
    public void WindowsNotificationIsAnAlarmOrAReminderWithTheTextAndTheSystemsSnoozeAndDismiss(
        string kind, string sound, string? loop)
    {
        XElement toast = XElement.Parse(ScheduledRingScript.ToastXml(kind, "sal <ya> & trabaja", "07:00"));

        Assert.Multiple(() =>
        {
            Assert.That(toast.Attribute("scenario")?.Value, Is.EqualTo(kind));
            Assert.That(toast.Descendants("text").Select(text => text.Value),
                Is.EqualTo(new[] { "BAXY", "sal <ya> & trabaja", "07:00" }));
            Assert.That(toast.Descendants("action").Select(action =>
                    action.Attribute("activationType")?.Value + ":" + action.Attribute("arguments")?.Value),
                Is.EqualTo(new[] { "system:snooze", "system:dismiss" }));
            Assert.That(toast.Element("audio")?.Attribute("src")?.Value, Is.EqualTo(sound));
            Assert.That(toast.Element("audio")?.Attribute("loop")?.Value, Is.EqualTo(loop));
        });
    }

    // The alarms and reminders the owner already set keep their task; their scripts, written before the hand-over, are
    // rewritten with the same title and receipt, once.
    [Test]
    public void AnOldRingScriptIsUpgradedWithItsTitleAndAnythingElseIsLeft()
    {
        using TemporaryDirectory temporary = new();
        Directory.CreateDirectory(temporary.Alarms);
        string old = Path.Combine(temporary.Alarms, Reminder + ".ps1");
        File.WriteAllText(old, OldRingScript(Path.ChangeExtension(old, ".fired"), "comprar pan"));
        string untitled = Path.Combine(temporary.Alarms, Alarm + ".ps1");
        File.WriteAllText(untitled, OldRingScript(Path.ChangeExtension(untitled, ".fired"), null));
        string foreign = Path.Combine(temporary.Alarms, "BAXY-Alarm-" + new string('9', 32) + ".ps1");
        File.WriteAllText(foreign, "# ring");

        int first = ScheduledRingScript.Upgrade(temporary.Alarms);
        int second = ScheduledRingScript.Upgrade(temporary.Alarms);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.EqualTo(2));
            Assert.That(second, Is.Zero);
            Assert.That(File.ReadAllText(old), Does.StartWith(ScheduledRingScript.Marker));
            Assert.That(File.ReadAllText(old), Does.Contain("TryOpenExisting"));
            Assert.That(ScheduledRingScript.ReadTitle(old), Is.EqualTo("comprar pan"));
            Assert.That(ScheduledRingScript.ReadTitle(untitled), Is.Null);
            Assert.That(File.ReadAllText(foreign), Is.EqualTo("# ring"));
        });
    }

    // The real script's hand-over, run by Windows PowerShell as the Task Scheduler runs it. What it does after the
    // hand-over (Windows' notification and its sound) is replaced by a mark: no test sounds or shows anything.
    [TestCase(true, true, "app")]
    [TestCase(true, false, "notification")]
    [TestCase(false, false, "notification")]
    public async Task TheRingScriptHandsTheRingToTheOpenAppOrRingsItself(bool appOpen, bool appTakes, string rings)
    {
        using TemporaryDirectory temporary = new();
        Directory.CreateDirectory(temporary.Alarms);
        string path = Path.Combine(temporary.Alarms, Alarm + ".ps1");
        ScheduledRingScript.HandOffWait = TimeSpan.FromSeconds(2);
        try
        {
            ScheduledRingScript.Write(path, "sal a trabajar", "07:00");
        }
        finally
        {
            ScheduledRingScript.HandOffWait = TimeSpan.FromSeconds(15);
        }

        string script = await File.ReadAllTextAsync(path);
        int notification = script.IndexOf("$toast=$false", StringComparison.Ordinal);
        Assert.That(notification, Is.GreaterThan(0));
        await File.WriteAllTextAsync(path, script[..notification]
            + "[IO.File]::WriteAllText($receipt,'{\"rungBy\":\"notification\"}')\n", new UTF8Encoding(false));
        // A .late left by an earlier ring whose delete failed never turns a ring nobody took into a silent one.
        if (appOpen)
        {
            await File.WriteAllTextAsync(Path.ChangeExtension(path, ".late"), "{}");
        }
        using OpenApp? app = appOpen ? new OpenApp(temporary.Alarms, takes: appTakes) : null;

        using Process process = Process.Start(new ProcessStartInfo(
            Path.Combine(Environment.SystemDirectory, @"WindowsPowerShell\v1.0\powershell.exe"),
            $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"{path}\"")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
        })!;
        await process.WaitForExitAsync(new CancellationTokenSource(TimeSpan.FromSeconds(30)).Token);

        using JsonDocument receipt = JsonDocument.Parse(await File.ReadAllTextAsync(Path.ChangeExtension(path, ".fired")));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.RootElement.GetProperty("rungBy").GetString(), Is.EqualTo(rings));
            Assert.That(app?.Taken ?? [], Is.EqualTo(appTakes ? new[] { "sal a trabajar@07:00" } : Array.Empty<string>()));
            Assert.That(Directory.GetFiles(temporary.Alarms, "*.due"), Is.Empty);
            Assert.That(Directory.GetFiles(temporary.Alarms, "*.late"), Is.Empty);
        });
    }

    // The whole script, as written, parses as Windows PowerShell, and its notification loads in WinRT's XmlDocument (the
    // one ToastNotification takes); nothing is run or shown.
    [TestCase(Alarm, "sal a trabajar", "07:00")]
    [TestCase(Alarm, null, null)]
    [TestCase(Reminder, "comprar <pan> & 'leche'", "15:00")]
    public async Task TheWholeRingScriptIsWindowsPowerShellAndItsNotificationLoads(string task, string? title, string? clock)
    {
        using TemporaryDirectory temporary = new();
        Directory.CreateDirectory(temporary.Alarms);
        string path = Path.Combine(temporary.Alarms, task + ".ps1");
        ScheduledRingScript.Write(path, title, clock);
        string toast = Path.Combine(temporary.Path, "toast.xml");
        await File.WriteAllTextAsync(toast, ScheduledRingScript.ToastXml(
            task.StartsWith("BAXY-Alarm-", StringComparison.Ordinal) ? "alarm" : "reminder", title, clock));
        string check = "$e=$null;[void][Management.Automation.Language.Parser]::ParseFile('" + path + "',[ref]$null,[ref]$e);"
            + "[void][Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime];"
            + "$x=New-Object Windows.Data.Xml.Dom.XmlDocument;$x.LoadXml([IO.File]::ReadAllText('" + toast + "'));"
            + "'errors=' + $e.Count + ';scenario=' + $x.DocumentElement.GetAttribute('scenario')";

        using Process process = Process.Start(new ProcessStartInfo(
            Path.Combine(Environment.SystemDirectory, @"WindowsPowerShell\v1.0\powershell.exe"),
            $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \"{check}\"")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        string output = await process.StandardOutput.ReadToEndAsync();
        string error = await process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();

        Assert.That(output.Trim(), Is.EqualTo("errors=0;scenario="
            + (task.StartsWith("BAXY-Alarm-", StringComparison.Ordinal) ? "alarm" : "reminder")), error);
    }

    // The ring script as BAXY wrote it before ALR1 (WindowsScheduledNotificationAdapter.WriteRingScript at 45625a3d2).
    private static string OldRingScript(string receiptPath, string? title)
    {
        static string B64(string value) => Convert.ToBase64String(Encoding.UTF8.GetBytes(value));
        return "$ErrorActionPreference='Stop'\n"
            + (title is null ? "" : "$title=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + B64(title) + "'))\n")
            + "$receipt=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + B64(receiptPath) + "'))\n"
            + "$toast=$false\n"
            + "$sound='none'\n";
    }

    private static WindowsScheduledNotificationAdapter Adapter(TemporaryDirectory temporary) =>
        new(temporary.Path, ScriptedNotificationBackend.Registering());

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static string Clock(DateTime local) => local.ToString("HH:mm", CultureInfo.InvariantCulture);

    /// <summary>
    /// The open App as the hand-over sees it: it holds the folder's mutex, takes what the ring script hands over (or
    /// not), and ends a ring when it is answered.
    /// </summary>
    private sealed class OpenApp : IDisposable
    {
        private readonly string _alarms;
        private readonly Mutex _held;
        private readonly CancellationTokenSource _stop = new();
        private readonly Task _loop;

        internal OpenApp(string alarms, bool takes = true, bool ends = true)
        {
            _alarms = alarms;
            Directory.CreateDirectory(alarms);
            _held = new Mutex(false, AlarmRingHandoff.MutexName(alarms));
            _loop = Task.Run(async () =>
            {
                while (!_stop.IsCancellationRequested)
                {
                    foreach (string due in takes ? Directory.GetFiles(_alarms, "*" + AlarmRingHandoff.DueExtension) : [])
                    {
                        if (AlarmRingHandoff.Take(due) is { } ring) Taken.Add($"{ring.Title}@{ring.Clock}");
                    }

                    // ends false: an App that does not end the ring it is told to (busy, or closing).
                    foreach (string answer in ends ? Directory.GetFiles(_alarms, "*" + AlarmRingHandoff.AnswerExtension) : [])
                    {
                        string task = Path.GetFileNameWithoutExtension(answer);
                        Answers.Add(task + ":" + AlarmRingHandoff.AnswerOf(_alarms, task));
                        AlarmRingHandoff.End(_alarms, task);
                    }

                    try
                    {
                        await Task.Delay(50, _stop.Token);
                    }
                    catch (OperationCanceledException)
                    {
                        break;
                    }
                }
            });
        }

        internal List<string> Answers { get; } = [];

        internal List<string> Taken { get; } = [];

        // A ring the App took: as the hand-over leaves it.
        internal void Rings(string task, string? title, string clock)
        {
            string due = Path.Combine(_alarms, task + ".hold");
            string text = JsonSerializer.Serialize(new Dictionary<string, string?>
            {
                ["rangUtc"] = DateTimeOffset.UtcNow.ToString("O"),
                ["title"] = title,
                ["clock"] = clock,
            });
            File.WriteAllText(due, text);
            Assert.That(AlarmRingHandoff.Take(due), Is.Not.Null);
        }

        public void Dispose()
        {
            _stop.Cancel();
            _loop.Wait();
            _held.Dispose();
            _stop.Dispose();
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-alr1-tests-" + Guid.NewGuid().ToString("N"));

        internal string Alarms => System.IO.Path.Combine(Path, "scheduled-notifications");

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }
}
