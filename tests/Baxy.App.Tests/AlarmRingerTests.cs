using System.IO;
using System.Text;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// ALR1: with BAXY open, a reminder chimes and BAXY says it once (once more 10 minutes later, then it ends); an alarm
/// loops its tone and its words until it is answered or 10 minutes pass; «Baxy» heard stops the tone while the person
/// speaks. Nothing sounds here: the output is recorded.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class AlarmRingerTests
{
    private const string Alarm = "BAXY-Alarm-0123456789abcdef0123456789abcdef";
    private const string Reminder = "BAXY-Reminder-fedcba9876543210fedcba9876543210";
    private static readonly DateTimeOffset T0 = new(2026, 11, 8, 18, 0, 0, TimeSpan.Zero);

    [Test]
    public void AReminderChimesIsSaidOnceAndOnceMoreTenMinutesLaterThenEnds()
    {
        using Folder folder = new();
        Output output = new();
        using AlarmRinger ringer = folder.Ringer(output);
        var changes = new List<string>();
        ringer.Changed += ring => changes.Add(ring.Status);
        folder.Due(Reminder, "comprar pan", "15:00", T0);

        for (TimeSpan t = TimeSpan.Zero; t <= TimeSpan.FromMinutes(13); t += TimeSpan.FromSeconds(1))
        {
            ringer.Tick(T0 + t);
        }

        Assert.Multiple(() =>
        {
            Assert.That(output.Said, Is.EqualTo(new[] { "Recordatorio: comprar pan", "Recordatorio: comprar pan" }));
            Assert.That(output.Log.Count(entry => entry == "tone reminder once"), Is.EqualTo(2));
            Assert.That(output.Log.IndexOf("say Recordatorio: comprar pan"), Is.EqualTo(2));
            Assert.That(changes, Is.EqualTo(new[] { "ringing", "unanswered" }));
            Assert.That(ringer.Now, Is.Empty);
            Assert.That(AlarmRingHandoff.IsRinging(folder.Path, Reminder), Is.False);
        });
    }

    [Test]
    public void AnAlarmLoopsItsToneAndItsWordsUntilTenMinutesPass()
    {
        using Folder folder = new();
        Output output = new();
        using AlarmRinger ringer = folder.Ringer(output);
        var changes = new List<string>();
        ringer.Changed += ring => changes.Add(ring.Status);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);

        for (TimeSpan t = TimeSpan.Zero; t <= TimeSpan.FromMinutes(11); t += TimeSpan.FromSeconds(1))
        {
            ringer.Tick(T0 + t);
        }

        Assert.Multiple(() =>
        {
            Assert.That(output.Log[0], Is.EqualTo("tone alarm loop"));
            Assert.That(output.Said.Distinct(), Is.EqualTo(new[] { "Alarma de las 7:00: sal a trabajar" }));
            // 10 s of tone and 2 s of words each turn, for 10 minutes: about fifty times, and then never again.
            Assert.That(output.Said, Has.Count.InRange(45, 51));
            Assert.That(changes, Is.EqualTo(new[] { "ringing", "timeout" }));
            Assert.That(output.ToneOn, Is.False);
        });
    }

    [TestCase("stop", "stopped")]
    [TestCase("snooze", "snoozed")]
    public void AnAnswerEndsTheRingAndItsSound(string answer, string status)
    {
        using Folder folder = new();
        Output output = new();
        using AlarmRinger ringer = folder.Ringer(output);
        var changes = new List<string>();
        ringer.Changed += ring => changes.Add(ring.Status);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);
        ringer.Tick(T0);

        AlarmRingHandoff.Answer(folder.Path, Alarm, answer);
        ringer.Tick(T0 + TimeSpan.FromSeconds(1));
        ringer.Tick(T0 + TimeSpan.FromSeconds(30));

        Assert.Multiple(() =>
        {
            Assert.That(changes, Is.EqualTo(new[] { "ringing", status }));
            Assert.That(output.ToneOn, Is.False);
            Assert.That(output.Log, Is.EqualTo(new[] { "tone alarm loop", "stop" }));
            Assert.That(AlarmRingHandoff.IsRinging(folder.Path, Alarm), Is.False);
            Assert.That(AlarmRingHandoff.AnswerOf(folder.Path, Alarm), Is.Null);
        });
    }

    [Test]
    public void BaxyHeardStopsTheToneWhileThePersonSpeaksAndItComesBackUnanswered()
    {
        using Folder folder = new();
        Output output = new();
        bool turn = false;
        using AlarmRinger ringer = folder.Ringer(output, () => turn);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);
        ringer.Tick(T0);

        bool stopped = ringer.Heard(T0 + TimeSpan.FromSeconds(3));
        bool offWhenHeard = !output.ToneOn;
        bool stoppedAgain = ringer.Heard(T0 + TimeSpan.FromSeconds(4));
        ringer.Tick(T0 + TimeSpan.FromSeconds(5));
        turn = true; // their turn runs past the wake's hold
        ringer.Tick(T0 + TimeSpan.FromSeconds(20));
        bool offInTurn = !output.ToneOn;
        turn = false;
        ringer.Tick(T0 + TimeSpan.FromSeconds(21));

        Assert.Multiple(() =>
        {
            Assert.That(stopped, Is.True);
            Assert.That(stoppedAgain, Is.False);
            Assert.That(offWhenHeard, Is.True);
            Assert.That(offInTurn, Is.True);
            Assert.That(output.Said, Is.Empty);
            Assert.That(output.ToneOn, Is.True);
            Assert.That(output.Log, Is.EqualTo(new[] { "tone alarm loop", "stop", "tone alarm loop" }));
        });
    }

    [Test]
    public void TwoRingsSoundOneAfterTheOther()
    {
        using Folder folder = new();
        Output output = new();
        using AlarmRinger ringer = folder.Ringer(output);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);
        ringer.Tick(T0);
        folder.Due(Reminder, "comprar pan", "07:00", T0 + TimeSpan.FromSeconds(1));
        ringer.Tick(T0 + TimeSpan.FromSeconds(1));
        int ringing = ringer.Now.Count;

        AlarmRingHandoff.Answer(folder.Path, Alarm, "stop");
        for (TimeSpan t = TimeSpan.FromSeconds(2); t <= TimeSpan.FromSeconds(8); t += TimeSpan.FromSeconds(1))
        {
            ringer.Tick(T0 + t);
        }

        Assert.Multiple(() =>
        {
            Assert.That(ringing, Is.EqualTo(2));
            Assert.That(output.Log.Take(3), Is.EqualTo(new[] { "tone alarm loop", "stop", "tone reminder once" }));
            Assert.That(output.Said, Is.EqualTo(new[] { "Recordatorio: comprar pan" }));
        });
    }

    [Test]
    public void AReminderWaitingToBeSaidAgainLetsAnAlarmRingAtOnce()
    {
        Output output = new();
        using Folder folder = new();
        using AlarmRinger ringer = folder.Ringer(output);
        folder.Due(Reminder, "comprar pan", "07:00", T0);
        for (TimeSpan t = TimeSpan.Zero; t <= TimeSpan.FromSeconds(10); t += TimeSpan.FromSeconds(1))
        {
            ringer.Tick(T0 + t);
        }

        folder.Due(Alarm, "sal a trabajar", "07:01", T0 + TimeSpan.FromMinutes(1));
        ringer.Tick(T0 + TimeSpan.FromMinutes(1));

        Assert.Multiple(() =>
        {
            Assert.That(output.Log[^1], Is.EqualTo("tone alarm loop"));
            Assert.That(ringer.Now.Select(ring => ring.Kind), Is.EquivalentTo(new[] { "alarm", "reminder" }));
        });
    }

    [Test]
    public void AnAlarmArrivingOverAReminderGoesFirstAndTheReminderIsSaidAfter()
    {
        Output output = new();
        using Folder folder = new();
        using AlarmRinger ringer = folder.Ringer(output);
        folder.Due(Reminder, "comprar pan", "07:00", T0);
        ringer.Tick(T0);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);
        ringer.Tick(T0 + TimeSpan.FromSeconds(1));
        AlarmRingHandoff.Answer(folder.Path, Alarm, "stop");
        for (TimeSpan t = TimeSpan.FromSeconds(2); t <= TimeSpan.FromSeconds(8); t += TimeSpan.FromSeconds(1))
        {
            ringer.Tick(T0 + t);
        }

        Assert.Multiple(() =>
        {
            Assert.That(output.Log.Take(4), Is.EqualTo(new[] { "tone reminder once", "stop", "tone alarm loop", "stop" }));
            Assert.That(output.Said, Is.EqualTo(new[] { "Recordatorio: comprar pan" }));
        });
    }

    [Test]
    public void AnAnswerLeftFromAnEarlierRingNeverEndsTheNextOne()
    {
        Output output = new();
        using Folder folder = new();
        using AlarmRinger ringer = folder.Ringer(output);
        AlarmRingHandoff.Answer(folder.Path, Alarm, "stop");
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);

        ringer.Tick(T0);
        ringer.Tick(T0 + TimeSpan.FromSeconds(1));

        Assert.Multiple(() =>
        {
            Assert.That(ringer.Now, Has.Count.EqualTo(1));
            Assert.That(output.ToneOn, Is.True);
        });
    }

    [Test]
    public void ATurnThatRunsOnHoldsTheAlarmAMinuteAtMost()
    {
        Output output = new();
        using Folder folder = new();
        using AlarmRinger ringer = folder.Ringer(output, () => true);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);

        ringer.Tick(T0);
        bool heldAtFirst = !output.ToneOn;
        ringer.Tick(T0 + AlarmRinger.MaxHold + TimeSpan.FromSeconds(1));

        Assert.Multiple(() =>
        {
            Assert.That(heldAtFirst, Is.True);
            Assert.That(output.ToneOn, Is.True);
        });
    }

    [Test]
    public void ARingThatCannotBeReadStillRingsOnceTaken()
    {
        Output output = new();
        using Folder folder = new();
        using AlarmRinger ringer = folder.Ringer(output);
        File.WriteAllText(System.IO.Path.Combine(folder.Path, Reminder + AlarmRingHandoff.DueExtension), "{no json");

        ringer.Tick(T0);

        Assert.Multiple(() =>
        {
            Assert.That(ringer.Now.Single().Title, Is.Null);
            Assert.That(output.Log, Is.EqualTo(new[] { "tone reminder once" }));
        });
    }

    [TestCase("alarm", "sal a trabajar", "07:00", false, "Alarma de las 7:00: sal a trabajar")]
    [TestCase("alarm", null, "13:05", false, "Alarma de las 13:05.")]
    [TestCase("alarm", "pastilla", "01:00", false, "Alarma de la 1:00: pastilla")]
    [TestCase("reminder", "comprar pan", "15:00", false, "Recordatorio: comprar pan")]
    [TestCase("reminder", null, "15:00", false, "Recordatorio de las 15:00.")]
    [TestCase("alarm", "leave for work", "07:00", true, "Alarm, 7:00: leave for work")]
    [TestCase("reminder", "buy bread", "15:00", true, "Reminder: buy bread")]
    public void TheWordsAreTheKindTheTimeAndThePersonsOwn(
        string kind, string? title, string clock, bool english, string words) =>
        Assert.That(AlarmRinger.Words(kind, title, clock, english), Is.EqualTo(words));

    [Test]
    public void StartingUpgradesOldScriptsClearsWhatAnEarlierAppLeftAndHoldsTheFolder()
    {
        using Folder folder = new();
        Directory.CreateDirectory(folder.Path);
        string script = Path.Combine(folder.Path, Reminder + ".ps1");
        File.WriteAllText(script, "$ErrorActionPreference='Stop'\n$receipt=[Text.Encoding]::UTF8.GetString("
            + "[Convert]::FromBase64String('" + Convert.ToBase64String(Encoding.UTF8.GetBytes(script)) + "'))\n");
        File.WriteAllText(Path.Combine(folder.Path, Alarm + AlarmRingHandoff.RingingExtension),
            """{"rangUtc":"2026-11-08T07:00:00.0000000+00:00","clock":"07:00"}""");
        Output output = new();
        bool held;
        using (AlarmRinger ringer = folder.Ringer(output))
        {
            held = AlarmRingHandoff.AppHolds(folder.Path);
        }

        Assert.Multiple(() =>
        {
            Assert.That(held, Is.True);
            Assert.That(AlarmRingHandoff.AppHolds(folder.Path), Is.False);
            Assert.That(File.ReadAllText(script), Does.StartWith(ScheduledRingScript.Marker));
            Assert.That(AlarmRingHandoff.IsRinging(folder.Path, Alarm), Is.False);
        });
    }

    // PRV-2: a one-time alarm that rang stayed in Windows' Task Scheduler for good. The App asks for the ones that
    // will not ring again to be removed when it starts (those that rang with it closed) and each time a ring ends, once
    // it no longer rings; not when it closes, with the process on its way out.
    [Test]
    public void StartingAndEachRingThatEndsAskForTheSpentRingsToGoAndClosingDoesNot()
    {
        using Folder folder = new();
        Output output = new();
        var asked = new List<bool>();
        AlarmRinger ringer = folder.Ringer(output, spent: () => asked.Add(AlarmRingHandoff.IsRinging(folder.Path, Alarm)));
        int atStart = asked.Count;
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);
        ringer.Tick(T0);
        int whileItRings = asked.Count;
        AlarmRingHandoff.Answer(folder.Path, Alarm, "stop");
        ringer.Tick(T0 + TimeSpan.FromSeconds(1));
        int afterTheStop = asked.Count;
        folder.Due(Reminder, "comprar pan", "15:00", T0 + TimeSpan.FromSeconds(2));
        ringer.Tick(T0 + TimeSpan.FromSeconds(2));
        ringer.Dispose();

        Assert.Multiple(() =>
        {
            Assert.That(atStart, Is.EqualTo(1));
            Assert.That(whileItRings, Is.EqualTo(1));
            Assert.That(afterTheStop, Is.EqualTo(2));
            Assert.That(asked, Is.EqualTo(new[] { false, false }));
        });
    }

    [Test]
    public void TheCardSaysWhatRingsAndTheTurnRequestCarriesIt()
    {
        var ring = new RingNow(Alarm, "89abcdef", "alarm", "sal a trabajar", "07:00", T0,
            "Alarma de las 7:00: sal a trabajar", "ringing");
        var ringing = new JsonArray { new JsonObject { ["id"] = "89abcdef", ["kind"] = "alarm", ["clock"] = "07:00" } };

        JsonObject card = FieldProductChannel.RingItem(ring);
        JsonObject request = MindSidecarClient.DecideRequest("gracias", null, TimeSpan.Zero, ringing: ringing);
        JsonObject quiet = MindSidecarClient.DecideRequest("hola", null, TimeSpan.Zero);

        Assert.Multiple(() =>
        {
            Assert.That((string?)card["who"], Is.EqualTo("ring"));
            Assert.That((string?)card["ring"]!["id"], Is.EqualTo("89abcdef"));
            Assert.That((string?)card["ring"]!["words"], Is.EqualTo("Alarma de las 7:00: sal a trabajar"));
            Assert.That((string?)card["ring"]!["status"], Is.EqualTo("ringing"));
            Assert.That((string?)request["ringing"]![0]!["id"], Is.EqualTo("89abcdef"));
            Assert.That(quiet.ContainsKey("ringing"), Is.False);
        });
    }

    // INT16B, third blind review: a daily alarm's task rings every day under the same name, and its card was named by the
    // task alone. Today's ring took the place of yesterday's «Parada» card, up in the conversation, where its Parar was not
    // seen (the chat keeps to its end), and yesterday's card was lost.
    [Test]
    public void ADailyAlarmThatRingsAgainIsANewCardAtTheEndAndYesterdaysKeepsHowItEnded()
    {
        var yesterday = new RingNow(Alarm, "89abcdef", "alarm", null, "07:00", T0.AddDays(-1), "Alarma de las 7:00", "stopped");
        var today = yesterday with { RangUtc = T0, Status = "ringing" };
        var transcript = new FieldTranscript();
        _ = transcript.Ring(FieldProductChannel.RingItem(yesterday));
        _ = transcript.You("gracias");

        _ = transcript.Ring(FieldProductChannel.RingItem(today));
        _ = transcript.Ring(FieldProductChannel.RingItem(today with { Status = "snoozed" }));

        Assert.That(transcript.Items.Select(static item => (string?)item["ring"]?["status"] ?? (string?)item["who"]),
            Is.EqualTo(new[] { "stopped", "you", "snoozed" }), "one card per time it rang, each with how it ended");
    }

    // INT16, second blind review: a kept conversation opened again rings no more what rang when it was saved, and what
    // still rings is in it, live, whatever conversation it rang in.
    [Test]
    public void AConversationOpenedAgainShowsWhatStillRingsLiveAndWhatRangThenAsEnded()
    {
        var yesterday = new RingNow(Alarm, "89abcdef", "alarm", null, "18:00", T0.AddDays(-1), "Alarma de las 18:00", "stopped");
        var rang = new RingNow("BAXY-Alarm-" + new string('e', 32), "eeeeeeee", "alarm", null, "17:00", T0.AddHours(-1),
            "Alarma de las 17:00", "ringing");
        var rings = new RingNow(Reminder, "76543210", "reminder", "la llamada", "17:30", T0.AddMinutes(-30), "Recordatorio", "ringing");
        var today = yesterday with { RangUtc = T0, Status = "ringing" };
        var kept = new JsonArray(FieldProductChannel.RingItem(yesterday), FieldProductChannel.RingItem(rang),
            FieldProductChannel.RingItem(rings));
        var transcript = new FieldTranscript();

        FieldProductChannel.Reopen(transcript, kept, [rings, today]);

        Assert.That(transcript.Items.Select(static item => (string?)item["ring"]!["status"]),
            Is.EqualTo(new[] { "stopped", "ended", "ringing", "ringing" }), "yesterday's as it ended; today's live at the end");
        Assert.That((string?)transcript.Items[^1]["ring"]!["clock"], Is.EqualTo("18:00"));
    }

    // APP1 (ALR-1, review of the App 2026-11-09): whoever draws the ring's card (the view's channel) once threw an
    // exception that was none of the three the loop caught (INT16: an ArgumentOutOfRangeException from the card's id), the
    // tick ended there, before the tone, and the loop that rings ended with it, in silence. A card that cannot be drawn
    // never stops the ring: the alarm sounds, and the failure is kept.
    [Test]
    public void ACardThatCannotBeDrawnNeverStopsTheRing()
    {
        using Folder folder = new();
        Output output = new();
        using AlarmRinger ringer = folder.Ringer(output);
        ringer.Changed += static _ => throw new ArgumentOutOfRangeException("card");
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);

        Assert.DoesNotThrow(() => ringer.Tick(T0));
        Assert.DoesNotThrow(() => ringer.Tick(T0 + TimeSpan.FromSeconds(1)));

        Assert.Multiple(() =>
        {
            Assert.That(output.Log, Is.EqualTo(new[] { "tone alarm loop" }));
            Assert.That(ringer.Now.Select(static ring => ring.Id), Is.EqualTo(new[] { "89abcdef" }));
            Assert.That(folder.Kept, Is.EqualTo(new[] { nameof(ArgumentOutOfRangeException) }));
        });
    }

    // APP1 (ALR-1): the loop that rings, with a double that throws what the loop never caught. The tick's failure is kept,
    // the loop goes on, and the alarm sounds on the next tick.
    [Test]
    public async Task TheLoopOutlivesATickThatThrowsAndTheAlarmSoundsOnTheNext()
    {
        using Folder folder = new();
        Output output = new() { ToneThrows = 1 };
        using AlarmRinger ringer = folder.Ringer(output);
        folder.Due(Alarm, "sal a trabajar", "07:00", DateTimeOffset.UtcNow);
        using var closing = new CancellationTokenSource();

        Task loop = ringer.RunAsync(TimeSpan.FromMilliseconds(10), static () => DateTimeOffset.UtcNow, closing.Token);
        for (int waited = 0; waited < 500 && !output.ToneOn; waited++)
        {
            await Task.Delay(10);
        }

        bool alive = !loop.IsCompleted;
        await closing.CancelAsync();
        await loop;

        Assert.Multiple(() =>
        {
            Assert.That(output.ToneOn, Is.True, "the alarm sounds after the tick that threw");
            Assert.That(alive, Is.True, "the loop goes on");
            Assert.That(loop.IsCompletedSuccessfully, Is.True, "it ends with the App, with nothing left to observe");
            Assert.That(folder.Kept, Is.EqualTo(new[] { nameof(NotSupportedException) }));
            Assert.That(output.Notified, Is.Empty);
            Assert.That(AlarmRingHandoff.AppHolds(folder.Path), Is.True);
        });
    }

    // APP1 (ALR-1): ticks that keep throwing are an App that cannot ring. What it took rings as Windows' notification (the
    // one the ring script shows with BAXY closed), the card says so, and the folder is released: from then on the ring
    // scripts ring Windows' notification themselves instead of waiting for an App that would not sound them.
    [Test]
    public void TicksThatKeepThrowingGiveTheRingsBackToWindowsAndTheCardSaysSo()
    {
        using Folder folder = new();
        Output output = new() { ToneThrows = int.MaxValue };
        using AlarmRinger ringer = folder.Ringer(output);
        var changes = new List<string>();
        ringer.Changed += ring => changes.Add(ring.Status);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);

        ringer.TickOrGiveBack(T0);
        ringer.TickOrGiveBack(T0 + TimeSpan.FromMilliseconds(500));
        bool heldAfterTwo = AlarmRingHandoff.AppHolds(folder.Path);
        ringer.TickOrGiveBack(T0 + TimeSpan.FromSeconds(1));
        folder.Due(Reminder, "comprar pan", "15:00", T0 + TimeSpan.FromSeconds(2));
        ringer.TickOrGiveBack(T0 + TimeSpan.FromSeconds(2));

        Assert.Multiple(() =>
        {
            Assert.That(heldAfterTwo, Is.True, "two failed ticks are not yet an App that cannot ring");
            Assert.That(output.Notified, Is.EqualTo(new[] { "alarm sal a trabajar 07:00" }));
            Assert.That(changes, Is.EqualTo(new[] { "ringing", "windows" }));
            Assert.That(ringer.Now, Is.Empty);
            Assert.That(AlarmRingHandoff.IsRinging(folder.Path, Alarm), Is.False);
            Assert.That(AlarmRingHandoff.AppHolds(folder.Path), Is.False, "the ring scripts ring Windows themselves now");
            Assert.That(File.Exists(Path.Combine(folder.Path, Reminder + AlarmRingHandoff.DueExtension)), Is.True,
                "a later ring is not taken: its script takes it back and rings Windows' notification");
            Assert.That(folder.Kept, Has.Count.EqualTo(AlarmRinger.FailedTicks));
        });
    }

    // APP1 (ALR-1): a failure before any ring is taken (here, the language asked for the words) takes none: the ring stays
    // the script's, which rings Windows' notification after its wait.
    [Test]
    public void AFailureBeforeARingIsTakenLeavesItToItsScript()
    {
        using Folder folder = new();
        Output output = new();
        using AlarmRinger ringer = folder.Ringer(output, english: static () => throw new NotSupportedException());
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);

        for (int tick = 0; tick < AlarmRinger.FailedTicks; tick++)
        {
            ringer.TickOrGiveBack(T0 + TimeSpan.FromMilliseconds(500 * tick));
        }

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Path.Combine(folder.Path, Alarm + AlarmRingHandoff.DueExtension)), Is.True);
            Assert.That(AlarmRingHandoff.IsRinging(folder.Path, Alarm), Is.False);
            Assert.That(AlarmRingHandoff.AppHolds(folder.Path), Is.False);
            Assert.That(output.Log, Is.Empty);
        });
    }

    // APP1 (ALR-2): a tone that could not play was not noticed, and the alarm «rang» in silence with its card on screen.
    // Windows' notification rings it instead; when Windows does not take it either, the card says nothing could ring it.
    [TestCase(true, "windows")]
    [TestCase(false, "failed")]
    public void ATonethatCannotPlayIsRungByWindowsNotificationAndTheCardSaysWhich(bool windowsTakesIt, string status)
    {
        using Folder folder = new();
        Output output = new() { TonePlays = false, WindowsTakesIt = windowsTakesIt };
        using AlarmRinger ringer = folder.Ringer(output);
        var changes = new List<string>();
        ringer.Changed += ring => changes.Add(ring.Status);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);

        ringer.Tick(T0);
        ringer.Tick(T0 + TimeSpan.FromSeconds(1));

        Assert.Multiple(() =>
        {
            Assert.That(output.Notified, Is.EqualTo(new[] { "alarm sal a trabajar 07:00" }));
            Assert.That(changes, Is.EqualTo(new[] { "ringing", status }));
            Assert.That(ringer.Now, Is.Empty);
            Assert.That(AlarmRingHandoff.IsRinging(folder.Path, Alarm), Is.False);
            Assert.That(AlarmRingHandoff.AppHolds(folder.Path), Is.True, "the next ring is tried again by the App");
        });
    }

    // APP1 (ALR-1): the voice that cannot say the words (the mind restarts) never stops the tone, which is the alarm.
    [Test]
    public void AVoiceThatCannotSayTheWordsNeverStopsTheTone()
    {
        using Folder folder = new();
        Output output = new() { SayThrows = true };
        using AlarmRinger ringer = folder.Ringer(output);
        folder.Due(Alarm, "sal a trabajar", "07:00", T0);

        for (TimeSpan t = TimeSpan.Zero; t <= TimeSpan.FromSeconds(40); t += TimeSpan.FromSeconds(1))
        {
            ringer.Tick(T0 + t);
        }

        Assert.Multiple(() =>
        {
            Assert.That(output.Log.Count(static entry => entry == "tone alarm loop"), Is.GreaterThanOrEqualTo(3));
            Assert.That(ringer.Now, Has.Count.EqualTo(1));
            Assert.That(folder.Kept.Distinct(), Is.EqualTo(new[] { nameof(InvalidCastException) }));
            Assert.That(output.Notified, Is.Empty);
        });
    }

    private sealed class Output
    {
        internal List<string> Log { get; } = [];

        internal List<string> Said { get; } = [];

        /// <summary>Windows' notifications asked for a ring the App could not sound: kind, title and clock.</summary>
        internal List<string> Notified { get; } = [];

        internal bool ToneOn { get; private set; }

        /// <summary>How many times the tone throws before it plays (a double that throws what the loop never caught).</summary>
        internal int ToneThrows { get; set; }

        /// <summary>False: nothing can play (RingTone.Play's false).</summary>
        internal bool TonePlays { get; init; } = true;

        internal bool SayThrows { get; init; }

        internal bool WindowsTakesIt { get; init; } = true;

        internal RingOutput Sounds => new(
            (kind, loop) =>
            {
                if (ToneThrows > 0)
                {
                    ToneThrows--;
                    throw new NotSupportedException("the tone's double throws");
                }

                if (!TonePlays)
                {
                    return false;
                }

                Log.Add($"tone {kind} {(loop ? "loop" : "once")}");
                ToneOn = true;
                return true;
            },
            () =>
            {
                Log.Add("stop");
                ToneOn = false;
            },
            words =>
            {
                if (SayThrows)
                {
                    throw new InvalidCastException("the voice's double throws");
                }

                Log.Add("say " + words);
                Said.Add(words);
            },
            () => false,
            ring =>
            {
                Notified.Add($"{ring.Kind} {ring.Title} {ring.Clock}");
                return WindowsTakesIt;
            });
    }

    private sealed class Folder : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-alr1-app-" + Guid.NewGuid().ToString("N"), "scheduled-notifications");

        /// <summary>The failures the ring went on after, by their type.</summary>
        internal List<string> Kept { get; } = [];

        internal AlarmRinger Ringer(Output output, Func<bool>? holding = null, Func<bool>? english = null,
            Action? spent = null)
        {
            var ringer = new AlarmRinger(Path, output.Sounds, holding ?? (() => false), english ?? (() => false), spent,
                failure => Kept.Add(failure.GetType().Name));
            ringer.Start();
            return ringer;
        }

        // What the ring script hands over at its time.
        internal void Due(string task, string? title, string clock, DateTimeOffset rang)
        {
            var due = new JsonObject { ["rangUtc"] = rang.ToString("O"), ["clock"] = clock };
            if (title is not null)
            {
                due["title"] = title;
            }

            File.WriteAllText(System.IO.Path.Combine(Path, task + AlarmRingHandoff.DueExtension), due.ToJsonString());
        }

        public void Dispose()
        {
            try
            {
                Directory.Delete(System.IO.Path.GetDirectoryName(Path)!, recursive: true);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }
}
