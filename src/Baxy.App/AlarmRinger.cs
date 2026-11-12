using System.Globalization;
using System.IO;
using Baxy.Providers.Windows.External;

namespace Baxy.App;

/// <summary>What a ring sounds through: its tone (looped for an alarm; false when nothing could play), stopped; BAXY's
/// voice saying its words; whether that voice is still speaking; and Windows' own notification of a ring the App holds and
/// cannot sound (false when Windows did not take it).</summary>
internal sealed record RingOutput(
    Func<string, bool, bool> PlayTone, Action StopTone, Action<string> Say, Func<bool> Speaking, Func<RingNow, bool> Notify);

/// <summary>One alarm or reminder the App rings, as the view's card and the model's turn note show it.</summary>
/// <param name="Status">ringing, stopped, snoozed, timeout (an alarm nobody answered in <see cref="ScheduledRingScript.AlarmCap"/>),
/// unanswered (a reminder said twice), closed (the App closed while it rang), windows (the App could not sound it and
/// Windows' notification rings it) or failed (neither could); a kept conversation shows «ended» for one saved while it
/// rang that no longer rings (FieldTranscript.Replace).</param>
internal sealed record RingNow(
    string TaskName, string Id, string Kind, string? Title, string Clock, DateTimeOffset RangUtc, string Words,
    string Status);

/// <summary>
/// ALR1 (owner, 2026-11-08): with BAXY open, an alarm or a reminder rings as a phone's and as Alexa's do. The ring
/// script hands it over (<see cref="AlarmRingHandoff"/>) and the App:
/// <list type="bullet">
/// <item>a reminder (owner: «los recordatorios no tienen que ser tan molestos»): a short tone and BAXY says its words
/// once, as Alexa «will chime and announce the reminder» (Amazon, Reminders API); unanswered, it is said once more
/// <see cref="ReminderAgain"/> later (the snooze length Android's clock and Alexa's «Snooze reminder for 10 minutes» use)
/// and then it ends, never in a loop;</item>
/// <item>an alarm («los molestos son las alarmas»): its tone in a loop and its words between tones until it is
/// answered, for at most <see cref="ScheduledRingScript.AlarmCap"/> (Android's «Silence after», 10 minutes);</item>
/// <item>«Baxy» heard while it rings (the tone plays on the default output, the one the echo canceller's loopback
/// hears) stops the tone while the person speaks and their turn runs (<see cref="Heard"/>), and it comes back if
/// nobody answered it.</item>
/// </list>
/// It is answered only through schedule.alarms stop or snooze (the model's call or the card's buttons), which leave an
/// answer file that ends the ring here. Everything runs on the App's interface thread; <see cref="RunAsync"/> drives it.
/// <para>APP1 (ALR-1 and ALR-2, review of the App 2026-11-09): an alarm that does not sound is the worst an alarm can do.
/// The loop caught three kinds of exception and any other ended it in silence (INT16: the card's own code threw an
/// ArgumentOutOfRangeException), and a tone that could not play was not noticed. Now whoever draws the card and the voice
/// that says the words are apart from the ring (their failure is kept and the tone goes on); a tick that throws is kept
/// and the next one goes on; and what the App cannot sound (its tone did not play, or <see cref="FailedTicks"/> ticks in
/// a row threw) goes back to Windows: the same notification the ring script shows with BAXY closed, the card says so, and
/// after the failed ticks the folder's mutex is released, so the ring scripts ring Windows' notification themselves.</para>
/// <para>RUT4 (owner, 2026-11-10: «todos los días a las 10 dime buen día… una vez y listo»): a routine's text
/// (<see cref="AlarmRingHandoff.SayKind"/>, RoutineSayTasks) is no ring. Taken, its hand-over ends at once (it is never
/// «ringing»: no card, nothing to stop or snooze, not in the turn's note) and BAXY says the text once, when the person
/// is not speaking to it and its voice is free (<see cref="MaxHold"/> at most), and tells it (<see cref="Said"/>) for
/// the conversation's line. No tone, and never again.</para>
/// </summary>
internal sealed class AlarmRinger : IDisposable
{
    /// <summary>How long an alarm's tone loops before its words are said again.</summary>
    internal static readonly TimeSpan ToneFor = TimeSpan.FromSeconds(10);

    /// <summary>A reminder's short tone, before its words.</summary>
    internal static readonly TimeSpan ChimeFor = TimeSpan.FromSeconds(2);

    /// <summary>When an unanswered reminder is said once more.</summary>
    internal static readonly TimeSpan ReminderAgain = TimeSpan.FromMinutes(10);

    /// <summary>How long a reminder said twice still waits for its answer before it ends.</summary>
    internal static readonly TimeSpan ReminderLast = TimeSpan.FromMinutes(2);

    /// <summary>How long «Baxy» heard keeps the tone off, before the person's turn starts and while it runs.</summary>
    internal static readonly TimeSpan HeardHold = TimeSpan.FromSeconds(8);

    /// <summary>The longest a ring waits for the person speaking to BAXY (or a turn that runs on): an alarm sounds again
    /// after it, whatever runs (a phone's alarm rings during a call too).</summary>
    internal static readonly TimeSpan MaxHold = TimeSpan.FromSeconds(60);

    /// <summary>Ticks in a row that threw before the App stops ringing and Windows rings instead (1,5 s of the loop).</summary>
    internal const int FailedTicks = 3;

    private static readonly TimeSpan SayAtLeast = TimeSpan.FromSeconds(2);
    private static readonly TimeSpan SayAtMost = TimeSpan.FromSeconds(20);

    private readonly string _alarmRoot;
    private readonly RingOutput _output;
    private readonly Func<bool> _holding;
    private readonly Func<bool> _english;
    private readonly Action? _spent;
    private readonly Action<Exception> _failed;
    private readonly List<Ringing> _rings = [];
    private readonly List<RingNow> _says = [];
    private Mutex? _held;
    private Ringing? _sounding;
    private bool _toneOn;
    private DateTimeOffset _heardUntil;
    private DateTimeOffset? _holdSince;
    private int _failedTicks;

    /// <param name="spent">PRV-2: asked when rings may have been left that will not ring again (a one-time one stayed
    /// in Windows' Task Scheduler for good): when this App starts, for the ones that rang with it closed, and each time
    /// a ring ends here. Not when the App closes: the next start asks.</param>
    /// <param name="failed">Keeps a failure the ring went on after (UnhandledFailures); nothing by default.</param>
    internal AlarmRinger(
        string alarmRoot, RingOutput output, Func<bool> holding, Func<bool> english, Action? spent = null,
        Action<Exception>? failed = null)
    {
        _spent = spent;
        _alarmRoot = alarmRoot ?? throw new ArgumentNullException(nameof(alarmRoot));
        _output = output ?? throw new ArgumentNullException(nameof(output));
        _holding = holding ?? throw new ArgumentNullException(nameof(holding));
        _english = english ?? throw new ArgumentNullException(nameof(english));
        _failed = failed ?? (static _ => { });
    }

    /// <summary>A ring started, changed or ended (the view's card follows it).</summary>
    internal event Action<RingNow>? Changed;

    /// <summary>RUT4: BAXY said a routine's text, once (the conversation keeps a line of it).</summary>
    internal event Action<RingNow>? Said;

    /// <summary>What rings or waits for its answer now, the oldest first: what the model's turn note says.</summary>
    internal IReadOnlyList<RingNow> Now => [.. _rings.Select(static ring => ring.View)];

    /// <summary>
    /// From now on this App rings this folder's alarms and reminders: the ring scripts written before the hand-over
    /// are upgraded, a ring a previous App left behind is cleared, and the folder's mutex is held.
    /// </summary>
    internal void Start()
    {
        Directory.CreateDirectory(_alarmRoot);
        ScheduledRingScript.Upgrade(_alarmRoot);
        foreach (AlarmRingHandoff.Ring left in AlarmRingHandoff.Ringing(_alarmRoot))
        {
            AlarmRingHandoff.End(_alarmRoot, left.TaskName);
        }

        AlarmRingHandoff.ClearAnswers(_alarmRoot);

        _held = new Mutex(false, AlarmRingHandoff.MutexName(_alarmRoot));
        _spent?.Invoke();
    }

    /// <summary>«Baxy» was heard: the tone stops while the person speaks (and their turn runs, <c>holding</c>). True when
    /// a tone was stopped: the App plays one sound at a time, so the wake's own chime went with it.</summary>
    internal bool Heard(DateTimeOffset now)
    {
        _heardUntil = now + HeardHold;
        _holdSince = now;
        if (!_toneOn)
        {
            return false;
        }

        _output.StopTone();
        _toneOn = false;
        return true;
    }

    /// <summary>
    /// The loop that rings: one <see cref="Tick"/> each <paramref name="period"/> until <paramref name="cancellation"/>.
    /// A tick that throws, whatever it throws, is kept and the next one goes on; after <see cref="FailedTicks"/> in a row
    /// the App rings no more and Windows does (<see cref="GiveBack"/>). It ends only with the App.
    /// </summary>
    internal async Task RunAsync(TimeSpan period, Func<DateTimeOffset> clock, CancellationToken cancellation)
    {
        ArgumentNullException.ThrowIfNull(clock);
        using var timer = new PeriodicTimer(period);
        try
        {
            while (await timer.WaitForNextTickAsync(cancellation))
            {
                TickOrGiveBack(clock());
            }
        }
        catch (OperationCanceledException)
        {
            // The App closes.
        }
    }

    /// <summary>One turn of the loop: a tick, whose failure is kept and never leaves here.</summary>
    internal void TickOrGiveBack(DateTimeOffset now)
    {
        try
        {
            Tick(now);
            _failedTicks = 0;
        }
        // Whatever a tick throws, the loop that rings the alarms goes on (ALR-1).
        catch (Exception failure)
        {
            Kept(failure);
            if (++_failedTicks >= FailedTicks)
            {
                GiveBack();
            }
        }
    }

    /// <summary>
    /// Takes what the ring scripts handed over, ends what was answered or ran its time, and sounds one ring: an alarm
    /// before a reminder, the oldest first; a reminder said once is silent while it waits to be said again.
    /// </summary>
    internal void Tick(DateTimeOffset now)
    {
        if (_held is null)
        {
            return;
        }

        TakeDue();
        SayDue(now);
        foreach (Ringing ring in _rings.ToArray())
        {
            if (AlarmRingHandoff.AnswerOf(_alarmRoot, ring.TaskName) is { } answer)
            {
                End(ring, answer == "snooze" ? "snoozed" : "stopped");
            }
            else if (ring.View.Kind == "alarm" && now - ring.View.RangUtc >= ScheduledRingScript.AlarmCap)
            {
                End(ring, "timeout");
            }
            else if (ring.Step == Step.Wait && now - ring.Since >= ReminderAgain)
            {
                ring.Next(Step.Tone, now);
            }
            else if (ring.Step == Step.Last && now - ring.Since >= ReminderLast)
            {
                End(ring, "unanswered");
            }
        }

        Ringing? sounding = _rings.Where(static ring => ring.Step is not (Step.Wait or Step.Last))
            .OrderBy(static ring => ring.View.Kind == "alarm" ? 0 : 1).ThenBy(static ring => ring.View.RangUtc)
            .FirstOrDefault();
        if (!ReferenceEquals(sounding, _sounding))
        {
            // Another one goes first (an alarm over a reminder): what this one was saying is said again when it sounds.
            if (_toneOn)
            {
                _output.StopTone();
                _toneOn = false;
            }

            if (_sounding is { Step: Step.Tone or Step.Say or Step.Said } cut)
            {
                cut.Next(Step.Tone, now);
            }

            _sounding = sounding;
            sounding?.Next(Step.Tone, now);
        }

        if (sounding is null)
        {
            return;
        }

        if (Holding(now))
        {
            // The person speaks to BAXY: nothing sounds now, and an announcement cut short starts again after.
            if (_toneOn)
            {
                _output.StopTone();
                _toneOn = false;
            }

            if (sounding.Step is Step.Tone or Step.Say or Step.Said)
            {
                sounding.Next(Step.Tone, now);
            }

            return;
        }

        Drive(sounding, now);
    }

    // RUT4: the oldest routine's text waiting is said, once: not over the person speaking to BAXY nor over BAXY's own
    // voice, which it waits for MaxHold at most since its time.
    private void SayDue(DateTimeOffset now)
    {
        if (_says.Count == 0)
        {
            return;
        }

        RingNow say = _says[0];
        if (now - say.RangUtc < MaxHold && (Holding(now) || _output.Speaking()))
        {
            return;
        }

        _says.RemoveAt(0);
        Say(say.Words);
        try
        {
            Said?.Invoke(say);
        }
        // Whoever writes the conversation's line is apart from the ring loop, as the card is.
        catch (Exception failure)
        {
            Kept(failure);
        }

        _spent?.Invoke();
    }

    // The person speaks to BAXY («Baxy» heard, or their turn runs), for at most MaxHold at a time.
    private bool Holding(DateTimeOffset now)
    {
        if (now >= _heardUntil && !_holding())
        {
            _holdSince = null;
            return false;
        }

        _holdSince ??= now;
        return now - _holdSince.Value < MaxHold;
    }

    private void Drive(Ringing ring, DateTimeOffset now)
    {
        bool alarm = ring.View.Kind == "alarm";
        switch (ring.Step)
        {
            case Step.Tone when !_toneOn:
                if (!_output.PlayTone(ring.View.Kind, alarm))
                {
                    // ALR-2: no tone played. It is not left ringing in silence: Windows' notification rings it.
                    ToWindows(ring);
                    break;
                }

                _toneOn = true;
                ring.Next(Step.Tone, now);
                break;
            case Step.Tone when now - ring.Since >= (alarm ? ToneFor : ChimeFor):
                _output.StopTone();
                _toneOn = false;
                ring.Next(Step.Say, now);
                goto case Step.Say;
            case Step.Say:
                Say(ring.View.Words);
                ring.Next(Step.Said, now);
                break;
            case Step.Said when now - ring.Since >= SayAtMost
                || (now - ring.Since >= SayAtLeast && !_output.Speaking()):
                ring.Said++;
                if (alarm)
                {
                    ring.Next(Step.Tone, now);
                }
                else if (ring.Said < 2)
                {
                    ring.Next(Step.Wait, now);
                }
                else
                {
                    ring.Next(Step.Last, now);
                }

                break;
        }
    }

    private void TakeDue()
    {
        string[] due;
        try
        {
            due = Directory.GetFiles(_alarmRoot, "BAXY-*" + AlarmRingHandoff.DueExtension);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return;
        }

        // Asked before any ring is taken: once one is taken, nothing that may throw stands between it and the list.
        bool english = _english();
        foreach (string path in due)
        {
            if (AlarmRingHandoff.Take(path) is not { } taken)
            {
                continue;
            }

            if (taken.Kind == AlarmRingHandoff.SayKind)
            {
                // RUT4: a routine's text is not a ring: its hand-over ends here, and it waits only to be said.
                AlarmRingHandoff.End(_alarmRoot, taken.TaskName);
                if (taken.Title is { } text)
                {
                    _says.Add(new RingNow(taken.TaskName, taken.Id, taken.Kind, text, taken.Clock, taken.RangUtc, text, "said"));
                }

                continue;
            }

            var ring = new Ringing(new RingNow(taken.TaskName, taken.Id, taken.Kind, taken.Title, taken.Clock,
                taken.RangUtc, Words(taken.Kind, taken.Title, taken.Clock, english), "ringing"));
            _rings.Add(ring);
            Tell(ring.View);
        }
    }

    // The voice that cannot say the words now (the mind restarts) never stops the tone, which is the alarm.
    private void Say(string words)
    {
        try
        {
            _output.Say(words);
        }
        // Whatever the voice throws, the ring goes on.
        catch (Exception failure)
        {
            Kept(failure);
        }
    }

    // Whoever draws the card is apart from the ring: its failure is kept and the ring goes on (ALR-1).
    private void Tell(RingNow ring)
    {
        try
        {
            Changed?.Invoke(ring);
        }
        // Whatever the card's code throws, the ring goes on.
        catch (Exception failure)
        {
            Kept(failure);
        }
    }

    private void Kept(Exception failure)
    {
        try
        {
            _failed(failure);
        }
        // Keeping a failure never adds one of its own.
        catch (Exception)
        {
        }
    }

    // The App cannot sound this ring: Windows' own notification rings it (the one the ring script shows with BAXY
    // closed), and the card says which of the two happened.
    private void ToWindows(Ringing ring)
    {
        bool shown = Notified(ring.View);
        End(ring, shown ? "windows" : "failed");
    }

    private bool Notified(RingNow ring)
    {
        try
        {
            return _output.Notify(ring);
        }
        // A notification that could not be shown is said as such, not thrown.
        catch (Exception failure)
        {
            Kept(failure);
            return false;
        }
    }

    /// <summary>
    /// The App cannot ring (its ticks keep throwing): every ring it took goes to Windows' notification, the ones it holds
    /// and any it took and lost on the way (a «.ringing» of this folder with no ring behind it), and the folder's mutex is
    /// released, so from now on the ring scripts ring Windows' notification themselves, as with BAXY closed.
    /// </summary>
    private void GiveBack()
    {
        if (_held is null)
        {
            return;
        }

        foreach (Ringing ring in _rings.ToArray())
        {
            try
            {
                ToWindows(ring);
            }
            // One ring that cannot be given back never keeps the others.
            catch (Exception failure)
            {
                Kept(failure);
                _rings.Remove(ring);
            }
        }

        foreach (AlarmRingHandoff.Ring lost in AlarmRingHandoff.Ringing(_alarmRoot))
        {
            var view = new RingNow(lost.TaskName, lost.Id, lost.Kind, lost.Title, lost.Clock, lost.RangUtc,
                Words(lost.Kind, lost.Title, lost.Clock, false), "ringing");
            bool shown = Notified(view);
            AlarmRingHandoff.End(_alarmRoot, lost.TaskName);
            Tell(view with { Status = shown ? "windows" : "failed" });
        }

        _sounding = null;
        _held.Dispose();
        _held = null;
    }

    private void End(Ringing ring, string status)
    {
        if (ReferenceEquals(ring, _sounding))
        {
            if (_toneOn)
            {
                _output.StopTone();
                _toneOn = false;
            }

            _sounding = null;
        }

        _rings.Remove(ring);
        AlarmRingHandoff.End(_alarmRoot, ring.TaskName);
        Tell(ring.View with { Status = status });
        if (status != "closed")
        {
            _spent?.Invoke();
        }
    }

    /// <summary>
    /// What BAXY says when it rings, in the person's language: the kind, its time and the person's own words («Alarma de
    /// las 7:00: sal a trabajar», «Recordatorio: comprar pan»), as a phone's alarm shows its label and Alexa announces
    /// the reminder's text. The words are the ones the person set; nothing is made up around them.
    /// </summary>
    internal static string Words(string kind, string? title, string clock, bool english)
    {
        string time = DateTime.TryParseExact(clock, "HH:mm", CultureInfo.InvariantCulture, DateTimeStyles.None,
            out DateTime at) ? at.ToString("H:mm", CultureInfo.InvariantCulture) : clock;
        bool one = at.Hour is 1;
        string head = kind == "alarm"
            ? english ? $"Alarm, {time}" : $"Alarma de {(one ? "la" : "las")} {time}"
            : english
                ? title is null ? $"Reminder, {time}" : "Reminder"
                : title is null ? $"Recordatorio de {(one ? "la" : "las")} {time}" : "Recordatorio";
        return title is null ? head + "." : head + ": " + title;
    }

    public void Dispose()
    {
        foreach (Ringing ring in _rings.ToArray())
        {
            End(ring, "closed");
        }

        _held?.Dispose();
        _held = null;
    }

    private enum Step
    {
        Tone,
        Say,
        Said,
        Wait,
        Last,
    }

    private sealed class Ringing(RingNow view)
    {
        internal RingNow View { get; } = view;

        internal string TaskName => View.TaskName;

        internal Step Step { get; private set; }

        internal DateTimeOffset Since { get; private set; }

        internal int Said { get; set; }

        internal void Next(Step step, DateTimeOffset now)
        {
            Step = step;
            Since = now;
        }
    }
}
