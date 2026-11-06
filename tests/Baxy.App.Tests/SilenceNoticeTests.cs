using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The notice of a silent turn (src/Baxy.App/SilenceNotice.cs). Al máximo 9.2b: it closed when the turn published its
/// line, and an answer published at 2.4 s that sounded at 3.9 s left more than 3 s without a signal; it now counts until
/// that answer is heard.
/// </summary>
[TestFixture]
public sealed class SilenceNoticeTests
{
    private const string Phrase = "Dame un segundo.";

    // The mind answers each question at once with the phrase.
    private static readonly Func<CancellationToken, Task<string?>> Ask = _ => Task.FromResult<string?>(Phrase);

    [SetUp]
    public void NoContext() => SynchronizationContext.SetSynchronizationContext(null);

    // Uso-124: a model reading for up to 89 s with no call running: nothing could be written or said, and the person heard
    // nothing for over a minute. A sound without words while it advances, never more often than ReadingSign.
    [Test]
    public void AModelStillReadingSoundsEveryWhileItAdvances()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        int sounded = 0;
        notice.Open(Ask, clock.GetTimestamp(), _ => { }, () => sounded++);

        clock.Advance(TimeSpan.FromSeconds(19));
        notice.Advanced();
        Assert.That(sounded, Is.EqualTo(0), "nothing yet: an NVIDIA GPU has read it all by now");
        clock.Advance(TimeSpan.FromSeconds(2));
        notice.Advanced();
        Assert.That(sounded, Is.EqualTo(1));
        notice.Advanced();
        Assert.That(sounded, Is.EqualTo(1), "advances come far more often than the sound");
        clock.Advance(SilenceNotice.ReadingSign);
        notice.Advanced();
        Assert.That(sounded, Is.EqualTo(2));
    }

    // Uso-124: on the RX 7600 a notice takes 3 s and a web call under 1 s: the call has ended when its phrase comes, and
    // the answer is a long read away. On a fast GPU the phrase is dropped: the answer is about to come.
    [TestCase(true, 1)]
    [TestCase(false, 0)]
    public async Task APhraseAfterItsCallEndedIsSaidOnlyWhenNoticesAreSlow(bool slow, int said)
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var phrases = new List<string>();
        var answer = new TaskCompletionSource<string?>();
        notice.Open(_ => answer.Task, clock.GetTimestamp(), phrases.Add, null, () => slow);
        notice.Running(true);
        Task ahead = notice.AheadAsync();
        notice.Running(false, completed: true);

        answer.SetResult(Phrase);
        await ahead;

        Assert.That(phrases, Has.Count.EqualTo(said));
    }

    // Revisión PCR1, A1 (Feria 2026-10-27 again): a call refused, failed or waiting for the person's yes did not do what
    // its phrase says («Borrando el archivo…» before «¿Lo borro?»): with slow notices too, its phrase is dropped. So is
    // one that comes after a later call ended so, though an earlier one completed.
    [TestCase(false)]
    [TestCase(true)]
    public async Task WithSlowNoticesAPhraseAfterACallThatDidNotCompleteIsDropped(bool anEarlierCallCompleted)
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var phrases = new List<string>();
        var answer = new TaskCompletionSource<string?>();
        notice.Open(_ => answer.Task, clock.GetTimestamp(), phrases.Add, null, () => true);
        notice.Running(true);
        Task ahead = notice.AheadAsync();
        if (anEarlierCallCompleted)
        {
            notice.Running(false, completed: true);
            notice.Running(true);
        }

        notice.Running(false);

        answer.SetResult(Phrase);
        await ahead;

        Assert.That(phrases, Is.Empty);
    }

    [Test]
    public async Task WithSlowNoticesAPhraseDoesNotOutliveATurnThatEndedSilent()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var phrases = new List<string>();
        var answer = new TaskCompletionSource<string?>();
        notice.Open(_ => answer.Task, clock.GetTimestamp(), phrases.Add, null, () => true);
        notice.Running(true);
        Task ahead = notice.AheadAsync();
        notice.Running(false, completed: true);
        notice.Close();

        answer.SetResult(Phrase);
        await ahead;

        Assert.That(phrases, Is.Empty, "the turn ended with nothing published: nothing is said after it");
    }

    [Test]
    public void AModelThatDoesNotAdvanceSoundsNothing()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        int sounded = 0;
        notice.Open(Ask, clock.GetTimestamp(), _ => { }, () => sounded++);

        clock.Advance(TimeSpan.FromMinutes(5));

        Assert.That(sounded, Is.EqualTo(0));
    }

    [Test]
    public void WhileACallRunsItsNoticeSpeaksNotTheSound()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        int sounded = 0;
        notice.Open(_ => Task.FromResult<string?>(null), clock.GetTimestamp(), _ => { }, () => sounded++);
        notice.Running(true);

        clock.Advance(TimeSpan.FromSeconds(30));
        notice.Advanced();

        Assert.That(sounded, Is.EqualTo(0));
    }

    [Test]
    public async Task ANoticeJustSaidPutsTheSoundOff()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var said = new List<string>();
        int sounded = 0;
        notice.Open(Ask, clock.GetTimestamp(), said.Add, () => sounded++);
        notice.Running(true);
        clock.Advance(TimeSpan.FromSeconds(15));
        await notice.AheadAsync();
        Assert.That(said, Is.Not.Empty);
        notice.Running(false);

        clock.Advance(TimeSpan.FromSeconds(10));
        notice.Advanced();
        Assert.That(sounded, Is.EqualTo(0), "the notice was heard 10 s ago");
        clock.Advance(TimeSpan.FromSeconds(11));
        notice.Advanced();
        Assert.That(sounded, Is.EqualTo(1));
    }

    [Test]
    public void AfterTheLineIsPublishedOrTheTurnEndedThereIsNoSound()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        int sounded = 0;
        notice.Open(Ask, clock.GetTimestamp(), _ => { }, () => sounded++);
        notice.Publish(() => { });
        clock.Advance(TimeSpan.FromSeconds(30));
        notice.Advanced();
        Assert.That(sounded, Is.EqualTo(0), "its line is on its way");

        notice.Open(Ask, clock.GetTimestamp(), _ => { }, () => sounded++);
        notice.Close();
        clock.Advance(TimeSpan.FromSeconds(30));
        notice.Advanced();
        Assert.That(sounded, Is.EqualTo(0), "the turn ended");
    }

    [Test]
    public void WhenNoNoticeWouldBeHeardThereIsNoSoundEither()
    {
        // The owner's switch (FieldSettings.WaitNotice) or BAXY's silenced voice: NativeTurnLoop opens it with no ask.
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        int sounded = 0;
        notice.Open(null, clock.GetTimestamp(), _ => { }, () => sounded++);

        clock.Advance(TimeSpan.FromSeconds(30));
        notice.Advanced();

        Assert.That(sounded, Is.EqualTo(0));
    }

    // Uso-125: a call that needs the model's own server (the description of a capture) says its notice first: while the
    // server reads the image the notice could only wait behind it and run out of its time (F31: heard at 67 s).
    [Test]
    public async Task AheadAsksAtOnceAndTheCallWaitsForTheAnswer()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var said = new List<string>();
        var answer = new TaskCompletionSource<string?>();
        int asked = 0;
        notice.Open(_ => { asked++; return answer.Task; }, clock.GetTimestamp(), said.Add);
        notice.Running(true);

        Task ahead = notice.AheadAsync();

        Assert.That(asked, Is.EqualTo(1), "asked at once, before the 2.5 s");
        Assert.That(ahead.IsCompleted, Is.False, "the call waits for the phrase");
        answer.SetResult(Phrase);
        await ahead;
        Assert.That(said, Is.EqualTo(new[] { Phrase }));
        clock.Advance(SilenceNotice.After);
        Assert.That(asked, Is.EqualTo(1), "the next is a whole Again away");
        clock.Advance(SilenceNotice.Again - SilenceNotice.After);
        Assert.That(asked, Is.EqualTo(2));
    }

    [Test]
    public async Task AheadWaitsForTheQuestionTheCallsStartAskedInsteadOfAskingTwice()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var said = new List<string>();
        var answer = new TaskCompletionSource<string?>();
        int asked = 0;
        notice.Open(_ => { asked++; return answer.Task; }, clock.GetTimestamp(), said.Add);
        clock.Advance(SilenceNotice.After); // due while the model decided: asked when the call starts
        notice.Running(true);
        Assert.That(asked, Is.EqualTo(1));

        Task ahead = notice.AheadAsync();

        Assert.That(asked, Is.EqualTo(1));
        Assert.That(ahead.IsCompleted, Is.False);
        answer.SetResult(Phrase);
        await ahead;
        Assert.That(said, Is.EqualTo(new[] { Phrase }));
    }

    [Test]
    public void OnlyADescriptionOnAConfiguredVisionSaysItsNoticeFirst()
    {
        string? before = Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8077/v1/chat/completions");
            Assert.That(NativeTurnLoop.SpeaksFirst("vision.describe"), Is.True);
            Assert.That(NativeTurnLoop.SpeaksFirst("capture.screenshot"), Is.False);
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", null);
            Assert.That(NativeTurnLoop.SpeaksFirst("vision.describe"), Is.False, "fails at once with no vision");
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", before);
        }
    }

    [Test]
    public void AheadAsksNothingWhenNoCallRunsOrNobodyWouldHear()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        int asked = 0;
        notice.Open(null, clock.GetTimestamp(), static _ => { });
        notice.Running(true);
        Assert.That(notice.AheadAsync().IsCompleted, Is.True);
        notice.Running(false);

        notice.Open(_ => { asked++; return Task.FromResult<string?>(Phrase); }, clock.GetTimestamp(), static _ => { });
        Assert.That(notice.AheadAsync().IsCompleted, Is.True);
        Assert.That(asked, Is.EqualTo(0));
    }

    [Test]
    public void AnAnswerPublishedButNotYetHeardGetsNoNoticeNow()
    {
        // Al máximo 9.2b said one here; feria 2026-10-27: no call runs once the line is published, and its line is
        // heard next.
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var said = new List<string>();
        notice.Open(Ask, clock.GetTimestamp(), said.Add);
        notice.Running(true); // a call of the turn runs in the App
        clock.Advance(TimeSpan.FromSeconds(1));
        notice.Running(false);

        clock.Advance(TimeSpan.FromSeconds(1.4));
        notice.Publish(static () => { });
        notice.Close(); // the turn ended with its line on screen; the voice still synthesizes it
        clock.Advance(TimeSpan.FromSeconds(0.1));

        Assert.That(said, Is.Empty);
    }

    [Test]
    public void AnAnswerHeardBeforeTheNoticeIsDueClosesIt()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var said = new List<string>();
        notice.Open(Ask, clock.GetTimestamp(), said.Add);
        notice.Running(true); // a call of the turn runs in the App

        clock.Advance(TimeSpan.FromSeconds(1.5));
        notice.Publish(static () => { });
        notice.Close();
        clock.Advance(TimeSpan.FromSeconds(0.5));
        notice.Sounded();
        clock.Advance(TimeSpan.FromSeconds(5));

        Assert.That(said, Is.Empty);
    }

    [Test]
    public void ASoundBeforeTheTurnPublishedDoesNotCloseIt()
    {
        // A heartbeat's words sounding while the person's turn works are not that turn's answer.
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var said = new List<string>();
        notice.Open(Ask, clock.GetTimestamp(), said.Add);
        notice.Running(true); // a call of the turn runs in the App

        clock.Advance(TimeSpan.FromSeconds(1));
        notice.Sounded();
        clock.Advance(TimeSpan.FromSeconds(1.5));

        Assert.That(said, Is.EqualTo(new[] { Phrase }));
    }

    [Test]
    public void ATurnThatEndsWithoutPublishingSaysNoNotice()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var said = new List<string>();
        notice.Open(Ask, clock.GetTimestamp(), said.Add);
        notice.Running(true); // a call of the turn runs in the App

        clock.Advance(TimeSpan.FromSeconds(1));
        notice.Close();
        clock.Advance(TimeSpan.FromSeconds(5));

        Assert.That(said, Is.Empty);
    }

    [Test]
    public void TheNoticeIsSaidOnceAndNeverAfterTheNextTurnOpens()
    {
        var clock = new ManualClock();
        var notice = new SilenceNotice(clock);
        var said = new List<string>();
        notice.Open(Ask, clock.GetTimestamp(), said.Add);
        notice.Running(true); // a call of the turn runs in the App
        clock.Advance(TimeSpan.FromSeconds(2));
        notice.Publish(static () => { });
        notice.Close();

        notice.Open(null, clock.GetTimestamp(), said.Add); // the next turn, with no notice to hear
        clock.Advance(TimeSpan.FromSeconds(5));
        notice.Running(true); // a call of the turn runs in the App

        Assert.That(said, Is.Empty);
    }

    /// <summary>A clock whose timers fire when it is advanced past their time.</summary>
    private sealed class ManualClock : TimeProvider
    {
        private readonly List<Timer> _timers = new();
        private long _ticks;

        public override long TimestampFrequency => TimeSpan.TicksPerSecond;

        public override long GetTimestamp() => _ticks;

        public override ITimer CreateTimer(TimerCallback callback, object? state, TimeSpan dueTime, TimeSpan period)
        {
            var timer = new Timer(this, callback, state, _ticks + dueTime.Ticks);
            _timers.Add(timer);
            return timer;
        }

        internal void Advance(TimeSpan by)
        {
            _ticks += by.Ticks;
            foreach (Timer timer in _timers.ToArray())
            {
                if (!timer.Disposed && timer.Due <= _ticks)
                {
                    timer.Disposed = true;
                    timer.Callback(timer.State);
                }
            }
        }

        private sealed class Timer(ManualClock clock, TimerCallback callback, object? state, long due) : ITimer
        {
            internal TimerCallback Callback { get; } = callback;

            internal object? State { get; } = state;

            internal long Due { get; private set; } = due;

            internal bool Disposed { get; set; }

            public bool Change(TimeSpan dueTime, TimeSpan period)
            {
                Due = clock.GetTimestamp() + dueTime.Ticks;
                Disposed = false;
                return true;
            }

            public void Dispose()
            {
                Disposed = true;
                clock._timers.Remove(this);
            }

            public ValueTask DisposeAsync()
            {
                Dispose();
                return ValueTask.CompletedTask;
            }
        }
    }
}
