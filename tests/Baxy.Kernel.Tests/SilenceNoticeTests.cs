using Baxy.App;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// The App's notice of a silent turn (src/Baxy.App/SilenceNotice.cs, linked here: the App has no test project). The
/// clock and the timer are the test's own, so each case moves the time and fires the timer when it says.
/// </summary>
[TestFixture]
public sealed class SilenceNoticeTests
{
    [Test]
    public void ASilentTurnSaysTheNoticeAtItsDelayAndAgainWhileItStaysSilent()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open(Says("Dame un momento."), time.GetTimestamp(), said.Add);

        Assert.That(time.Timers, Has.Count.EqualTo(1));
        Assert.That(time.Timers[0].DueTime, Is.EqualTo(SilenceNotice.After));
        Assert.That(time.Timers[0].Period, Is.EqualTo(SilenceNotice.Again));
        Assert.That(said, Is.Empty);
        // Al máximo, flujos: a call of 30 to 160 s said it once at 2.5 s and then nothing until it ended.
        time.Timers[0].Fire();
        time.Timers[0].Fire();
        notice.Publish(() => said.Add("answer"));
        // Al máximo 9.2b: silent until the answer sounds, not until it is published.
        notice.Sounded();
        time.Timers[0].Fire();
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento.", "Dame un momento.", "answer" }));
    }

    [Test]
    public void AnAnswerTheVoiceNeverSoundsGetsOneMoreNoticeNotOneEveryTenSeconds()
    {
        // Al máximo 9.2b with the repetition of flujos: a published line keeps the notice until it sounds, but a line
        // whose synthesis failed never sounds, and the notice would come back every 10 s until the next turn.
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open(Says("Dame un momento."), time.GetTimestamp(), said.Add);
        time.Timers[0].Fire();
        notice.Publish(() => said.Add("answer"));
        notice.Close();
        time.Timers[0].Fire();
        time.Timers[0].Fire();

        Assert.That(said, Is.EqualTo(new[] { "Dame un momento.", "answer", "Dame un momento." }));
        Assert.That(time.Timers[0].Disposed, Is.True);
    }

    [Test]
    public void TheTimeThePersonAlreadyWaitedShortensTheDelay()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();
        long arrived = time.GetTimestamp();
        // The person's words waited 1.5 s for a heartbeat to end before their turn started.
        time.Advance(TimeSpan.FromSeconds(1.5));

        notice.Open(Says("Dame un momento."), arrived, said.Add);

        Assert.That(time.Timers, Has.Count.EqualTo(1));
        Assert.That(time.Timers[0].DueTime, Is.EqualTo(SilenceNotice.After - TimeSpan.FromSeconds(1.5)));
        Assert.That(said, Is.Empty);
        time.Timers[0].Fire();
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento." }));
    }

    [Test]
    public void WhenThePersonAlreadyWaitedLongerTheNoticeIsSaidAtOnceOnTheTurnsThreadAndOnce()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();
        var turnContext = new QueuedContext();
        long arrived = time.GetTimestamp();
        time.Advance(TimeSpan.FromSeconds(3.0));
        SynchronizationContext? previous = SynchronizationContext.Current;
        SynchronizationContext.SetSynchronizationContext(turnContext);
        try
        {
            notice.Open(Says("Dame un momento."), arrived, said.Add);
        }
        finally
        {
            SynchronizationContext.SetSynchronizationContext(previous);
        }

        // Said now; the timer only says it again while the turn stays silent.
        Assert.That(time.Timers, Has.Count.EqualTo(1));
        Assert.That(time.Timers[0].DueTime, Is.EqualTo(SilenceNotice.Again));
        Assert.That(turnContext.Posted, Is.Empty);
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento." }));
        notice.Publish(() => said.Add("answer"));
        notice.Sounded();
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento.", "answer" }));
        time.Timers[0].Fire();
        turnContext.RunAll();
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento.", "answer" }));
    }

    [Test]
    public void NoNoticeFollowsTheTurnsOwnLineOnceItSounds()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open(Says("Dame un momento."), time.GetTimestamp(), said.Add);
        notice.Publish(() => said.Add("answer"));
        notice.Sounded();
        time.Timers[0].Fire();

        Assert.That(said, Is.EqualTo(new[] { "answer" }));
        Assert.That(time.Timers[0].Disposed, Is.True);
    }

    [Test]
    public void NoNoticeAfterTheTurnEndedNorInALaterTurnNobodyOpened()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open(Says("Dame un momento."), time.GetTimestamp(), said.Add);
        notice.Close();
        time.Timers[0].Fire();
        // A heartbeat opens no notice: its own line is only published.
        notice.Publish(() => said.Add("beat"));

        Assert.That(said, Is.EqualTo(new[] { "beat" }));
    }

    [Test]
    public void AnEarlierTurnsTimerSaysNothingInTheNextTurn()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open(Says("Dame un momento."), time.GetTimestamp(), said.Add);
        notice.Close();
        notice.Open(Says("Dame un momento."), time.GetTimestamp(), said.Add);
        time.Timers[0].Fire();
        Assert.That(said, Is.Empty);

        time.Timers[1].Fire();
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento." }));
    }

    [Test]
    public void WhenNobodyWouldHearItThereIsNoNotice()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);

        notice.Open(null, time.GetTimestamp(), _ => Assert.Fail("nobody asks, no notice"));

        Assert.That(time.Timers, Is.Empty);
    }

    [Test]
    public void TheNoticeIsSaidOnTheContextTheTurnRunsOn()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();
        var turnContext = new QueuedContext();
        SynchronizationContext? previous = SynchronizationContext.Current;
        SynchronizationContext.SetSynchronizationContext(turnContext);
        try
        {
            notice.Open(Says("Dame un momento."), time.GetTimestamp(), said.Add);
        }
        finally
        {
            SynchronizationContext.SetSynchronizationContext(previous);
        }

        time.Timers[0].Fire();
        Assert.That(said, Is.Empty);
        Assert.That(turnContext.Posted, Has.Count.EqualTo(1));

        // The answer published on the turn's context and heard before the posted notice ran: no notice after it.
        notice.Publish(() => said.Add("answer"));
        notice.Sounded();
        turnContext.RunAll();
        Assert.That(said, Is.EqualTo(new[] { "answer" }));
    }

    [Test]
    public void AQuestionTheMindAnswersWithoutAPhraseSaysNothingAndTheNextExpiryAsksAgain()
    {
        // The mind writes a phrase only while the turn waits for a call the App runs that had no notice yet.
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();
        var phrases = new Queue<string?>([null, "  Busco el archivo en Documentos.  "]);
        int asked = 0;

        notice.Open(
            _ =>
            {
                asked++;
                return Task.FromResult(phrases.Dequeue());
            },
            time.GetTimestamp(),
            said.Add);
        time.Timers[0].Fire();
        Assert.That(said, Is.Empty);
        time.Timers[0].Fire();

        Assert.That(asked, Is.EqualTo(2));
        Assert.That(said, Is.EqualTo(new[] { "Busco el archivo en Documentos." }));
    }

    [Test]
    public void APhraseThatArrivesOnceTheTurnClosedOrAnotherOpenedIsNotSaid()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();
        var first = new TaskCompletionSource<string?>();
        var second = new TaskCompletionSource<string?>();
        CancellationToken firstToken = default;

        notice.Open(
            token =>
            {
                firstToken = token;
                return first.Task;
            },
            time.GetTimestamp(),
            said.Add);
        time.Timers[0].Fire();
        notice.Close();
        Assert.That(firstToken.IsCancellationRequested, Is.True);
        first.SetResult("Abro el Bloc de notas.");

        notice.Open(_ => second.Task, time.GetTimestamp(), said.Add);
        time.Timers[1].Fire();
        notice.Open(Says("Otro turno."), time.GetTimestamp(), said.Add);
        second.SetResult("Busco en la web.");

        Assert.That(said, Is.Empty);
    }

    [Test]
    public void AnExpiryWhileTheQuestionHasNotAnsweredAsksNoOther()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();
        var answer = new TaskCompletionSource<string?>();
        int asked = 0;

        notice.Open(
            _ =>
            {
                asked++;
                return answer.Task;
            },
            time.GetTimestamp(),
            said.Add);
        time.Timers[0].Fire();
        time.Timers[0].Fire();
        Assert.That(asked, Is.EqualTo(1));
        answer.SetResult("Estoy descargando el instalador.");

        Assert.That(said, Is.EqualTo(new[] { "Estoy descargando el instalador." }));
    }

    [Test]
    public void EachExpiryOfALongTurnSaysThePhraseTheMindWroteForIt()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();
        var phrases = new Queue<string?>(["Busco el archivo.", "Sigo buscando en el disco D."]);

        notice.Open(_ => Task.FromResult(phrases.Dequeue()), time.GetTimestamp(), said.Add);
        time.Timers[0].Fire();
        time.Timers[0].Fire();

        Assert.That(said, Is.EqualTo(new[] { "Busco el archivo.", "Sigo buscando en el disco D." }));
    }

    [Test]
    public void AQuestionThatFailsSaysNothingAndNeverReachesTheTurn()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();
        int asked = 0;

        notice.Open(
            _ =>
            {
                asked++;
                return asked == 1
                    ? Task.FromException<string?>(new IOException("the mind's pipe broke"))
                    : Task.FromResult<string?>("Sigo con la descarga.");
            },
            time.GetTimestamp(),
            said.Add);
        Assert.DoesNotThrow(() => time.Timers[0].Fire());
        time.Timers[0].Fire();

        Assert.That(said, Is.EqualTo(new[] { "Sigo con la descarga." }));
    }

    // The mind answers each question at once with this phrase.
    private static Func<CancellationToken, Task<string?>> Says(string? phrase) => _ => Task.FromResult(phrase);

    private sealed class ManualTime : TimeProvider
    {
        private long _now;

        internal List<ManualTimer> Timers { get; } = [];

        public override long TimestampFrequency => TimeSpan.TicksPerSecond;

        public override long GetTimestamp() => _now;

        internal void Advance(TimeSpan by) => _now += by.Ticks;

        public override ITimer CreateTimer(TimerCallback callback, object? state, TimeSpan dueTime, TimeSpan period)
        {
            var timer = new ManualTimer(callback, state, dueTime, period);
            Timers.Add(timer);
            return timer;
        }
    }

    private sealed class ManualTimer(TimerCallback callback, object? state, TimeSpan dueTime, TimeSpan period) : ITimer
    {
        internal TimeSpan DueTime { get; } = dueTime;

        internal TimeSpan Period { get; } = period;

        internal bool Disposed { get; private set; }

        // As a real timer: a callback already on its way still runs after Dispose.
        internal void Fire() => callback(state);

        public bool Change(TimeSpan dueTime, TimeSpan period) => !Disposed;

        public void Dispose() => Disposed = true;

        public ValueTask DisposeAsync()
        {
            Disposed = true;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class QueuedContext : SynchronizationContext
    {
        internal List<(SendOrPostCallback Callback, object? State)> Posted { get; } = [];

        public override void Post(SendOrPostCallback d, object? state) => Posted.Add((d, state));

        internal void RunAll()
        {
            foreach ((SendOrPostCallback callback, object? state) in Posted)
            {
                callback(state);
            }
        }
    }
}
