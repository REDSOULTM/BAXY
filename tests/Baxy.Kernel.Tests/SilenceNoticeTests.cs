using System.Text.Json.Nodes;
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
    public void ThePhraseIsTheMindsTrimmedAndAbsentWhenItSentNone()
    {
        Assert.That(SilenceNotice.PhraseOf(Ready(" Dame un momento. ")), Is.EqualTo("Dame un momento."));
        Assert.That(SilenceNotice.PhraseOf(Ready(null)), Is.Null);
        Assert.That(SilenceNotice.PhraseOf(Ready("   ")), Is.Null);
        Assert.That(SilenceNotice.PhraseOf(new JsonObject { ["type"] = "catalog.ready", ["notice"] = 3 }), Is.Null);
        Assert.That(SilenceNotice.PhraseOf(null), Is.Null);
    }

    [Test]
    public void ASilentTurnSaysTheNoticeOnceAfterTwoSeconds()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open("Dame un momento.", time.GetTimestamp(), () => true, said.Add);

        Assert.That(time.Timers, Has.Count.EqualTo(1));
        Assert.That(time.Timers[0].DueTime, Is.EqualTo(TimeSpan.FromSeconds(2.0)));
        Assert.That(said, Is.Empty);
        time.Timers[0].Fire();
        time.Timers[0].Fire();
        notice.Publish(() => said.Add("answer"));
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento.", "answer" }));
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

        notice.Open("Dame un momento.", arrived, () => true, said.Add);

        Assert.That(time.Timers, Has.Count.EqualTo(1));
        Assert.That(time.Timers[0].DueTime, Is.EqualTo(TimeSpan.FromSeconds(0.5)));
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
            notice.Open("Dame un momento.", arrived, () => true, said.Add);
        }
        finally
        {
            SynchronizationContext.SetSynchronizationContext(previous);
        }

        Assert.That(time.Timers, Is.Empty);
        Assert.That(turnContext.Posted, Is.Empty);
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento." }));
        notice.Publish(() => said.Add("answer"));
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento.", "answer" }));

        // Already past and a call this turn raised waits for the person: still nothing, now or later.
        said.Clear();
        notice.Open("Dame un momento.", arrived, () => false, said.Add);
        Assert.That(time.Timers, Is.Empty);
        Assert.That(said, Is.Empty);
    }

    [Test]
    public void NoNoticeFollowsTheTurnsOwnLine()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open("Dame un momento.", time.GetTimestamp(), () => true, said.Add);
        notice.Publish(() => said.Add("answer"));
        time.Timers[0].Fire();

        Assert.That(said, Is.EqualTo(new[] { "answer" }));
        Assert.That(time.Timers[0].Disposed, Is.True);
    }

    [Test]
    public void NoNoticeWhileACallThisTurnRaisedWaitsForThePerson()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open("Dame un momento.", time.GetTimestamp(), () => false, said.Add);
        time.Timers[0].Fire();

        Assert.That(said, Is.Empty);
    }

    [Test]
    public void NoNoticeAfterTheTurnEndedNorInALaterTurnNobodyOpened()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);
        var said = new List<string>();

        notice.Open("Dame un momento.", time.GetTimestamp(), () => true, said.Add);
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

        notice.Open("Dame un momento.", time.GetTimestamp(), () => true, said.Add);
        notice.Close();
        notice.Open("Dame un momento.", time.GetTimestamp(), () => true, said.Add);
        time.Timers[0].Fire();
        Assert.That(said, Is.Empty);

        time.Timers[1].Fire();
        Assert.That(said, Is.EqualTo(new[] { "Dame un momento." }));
    }

    [Test]
    public void WithoutAPhraseFromTheMindThereIsNoNotice()
    {
        var time = new ManualTime();
        var notice = new SilenceNotice(time);

        notice.Open(null, time.GetTimestamp(), () => true, _ => Assert.Fail("no phrase, no notice"));

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
            notice.Open("Dame un momento.", time.GetTimestamp(), () => true, said.Add);
        }
        finally
        {
            SynchronizationContext.SetSynchronizationContext(previous);
        }

        time.Timers[0].Fire();
        Assert.That(said, Is.Empty);
        Assert.That(turnContext.Posted, Has.Count.EqualTo(1));

        // The answer published on the turn's context before the posted notice ran: the notice is not said after it.
        notice.Publish(() => said.Add("answer"));
        turnContext.RunAll();
        Assert.That(said, Is.EqualTo(new[] { "answer" }));
    }

    private static JsonObject Ready(string? phrase)
    {
        var reply = new JsonObject { ["type"] = "catalog.ready", ["count"] = 1 };
        if (phrase is not null)
        {
            reply["notice"] = phrase;
        }

        return reply;
    }

    private sealed class ManualTime : TimeProvider
    {
        private long _now;

        internal List<ManualTimer> Timers { get; } = [];

        public override long TimestampFrequency => TimeSpan.TicksPerSecond;

        public override long GetTimestamp() => _now;

        internal void Advance(TimeSpan by) => _now += by.Ticks;

        public override ITimer CreateTimer(TimerCallback callback, object? state, TimeSpan dueTime, TimeSpan period)
        {
            var timer = new ManualTimer(callback, state, dueTime);
            Timers.Add(timer);
            return timer;
        }
    }

    private sealed class ManualTimer(TimerCallback callback, object? state, TimeSpan dueTime) : ITimer
    {
        internal TimeSpan DueTime { get; } = dueTime;

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
