using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// MS (SP2 notebook tandas: every media operation ran out its budget after the first video opened in the browser): a
/// media session that never answers is left out within the limit, the others are read, the operation goes on, and its
/// failure says «media_session_unresponsive».
/// </summary>
[TestFixture]
public sealed class MediaSessionCallsTests
{
    private const string Opera = "OperaSoftware.OperaGXWebBrowser.1732473326";
    private const string Client = "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify";
    private static readonly TimeSpan Margin = TimeSpan.FromSeconds(2);

    [Test]
    public async Task ASessionThatNeverAnswersIsLeftOutAndTheOthersAreRead()
    {
        Session[] sessions = [Session.Answering("a"), Session.Hung(), Session.Answering("c")];
        StrongBox<bool> watch = MediaSessionCalls.Watch();
        var clock = Stopwatch.StartNew();

        IReadOnlyList<string> read = await MediaSessionCalls.ReadEachAsync(sessions, session => session.Answer);

        Assert.Multiple(() =>
        {
            Assert.That(read, Is.EqualTo(new[] { "a", "c" }));
            Assert.That(clock.Elapsed, Is.LessThan(MediaSessionCalls.CallLimit + Margin));
            Assert.That(watch.Value, Is.True);
        });
    }

    // A polling loop never pays the limit twice: a session whose read is still pending is left out at once.
    [Test]
    public async Task ASessionStillPendingIsLeftOutAtOnce()
    {
        Session[] sessions = [Session.Hung(), Session.Answering("b")];
        _ = await MediaSessionCalls.ReadEachAsync(sessions, session => session.Answer);
        StrongBox<bool> watch = MediaSessionCalls.Watch();
        var clock = Stopwatch.StartNew();

        IReadOnlyList<string> read = await MediaSessionCalls.ReadEachAsync(sessions, session => session.Answer);

        Assert.Multiple(() =>
        {
            Assert.That(read, Is.EqualTo(new[] { "b" }));
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(1)));
            Assert.That(watch.Value, Is.True);
        });
    }

    // Contracase: when every session answers, every one is read in its order and nothing is said.
    [Test]
    public async Task WhenEverySessionAnswersAllAreReadAndNothingIsSaid()
    {
        StrongBox<bool> watch = MediaSessionCalls.Watch();

        IReadOnlyList<string> read = await MediaSessionCalls.ReadEachAsync(
            [Session.Answering("a"), Session.Answering("b")], session => session.Answer);
        ExternalCapabilityReceipt failure = ExternalJson.Failure("media.control", "smtc_control_observation_failed");

        Assert.Multiple(() =>
        {
            Assert.That(read, Is.EqualTo(new[] { "a", "b" }));
            Assert.That(watch.Value, Is.False);
            Assert.That(MediaSessionCalls.Diagnosed(failure, watch), Is.SameAs(failure));
        });
    }

    [Test]
    public void AnUnansweredCallThrowsWithinTheLimit()
    {
        StrongBox<bool> watch = MediaSessionCalls.Watch();

        Assert.ThrowsAsync<TimeoutException>(async () =>
            await MediaSessionCalls.WithinLimitAsync(new TaskCompletionSource<bool>().Task));
        Assert.That(watch.Value, Is.True);
    }

    // A failure keeps what it carried and adds the diagnostic; a verified receipt is never touched.
    [Test]
    public void OnlyAFailureSaysASessionWentUnanswered()
    {
        var watch = new StrongBox<bool>(true);
        ExternalCapabilityReceipt failure = ExternalJson.Failure("media.play.query", "spotify_uia_adapter_failed");
        failure = failure with { Result = Json("""{"version":1,"stage":"searched"}""") };
        ExternalCapabilityReceipt success = ExternalJson.Success("media.control", Json("""{"version":1}"""));

        ExternalCapabilityReceipt diagnosed = MediaSessionCalls.Diagnosed(failure, watch);

        Assert.Multiple(() =>
        {
            Assert.That(diagnosed.ErrorCode, Is.EqualTo("spotify_uia_adapter_failed"));
            Assert.That(diagnosed.Result?.GetProperty("stage").GetString(), Is.EqualTo("searched"));
            Assert.That(diagnosed.Result?.GetProperty("diagnostic").GetString(),
                Is.EqualTo(MediaSessionCalls.Unresponsive));
            Assert.That(MediaSessionCalls.Diagnosed(success, watch), Is.SameAs(success));
        });
    }

    // The playback goes on past a hung session: the reads before and after it come back within the limit with the
    // other sessions, and the failure of the playback says a session went unanswered.
    [TestCase(false)]
    [TestCase(true)]
    public async Task APlaybackGoesOnPastAHungSession(bool plays)
    {
        Session[] system = [Session.Hung(), Session.Answering(Client)];
        var access = new WindowsMediaSessionAdapter.MediaSessionAccess(
            async () => (await MediaSessionCalls.ReadEachAsync(system, session => session.Answer))
                .Select(source => (source, "song", true)).ToArray(),
            (_, _) => ValueTask.CompletedTask,
            (_, _) => ValueTask.CompletedTask);
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null, sessions: access);
        var browser = new Player(plays
            ? ExternalJson.Success("media.play.youtube", Json($$"""{"sourceAppUserModelId":"{{Opera}}"}"""))
            : ExternalJson.FailureAfterEffect("media.play.youtube", "youtube_playback_unconfirmed"));
        using var provider = new WindowsExternalCapabilityProvider([media, browser]);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"los bunkers"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(browser.Invoked, Is.True);
            Assert.That(receipt.Verified, Is.EqualTo(plays));
            Assert.That(clock.Elapsed, Is.LessThan(MediaSessionCalls.CallLimit + Margin));
            Assert.That(receipt.Result?.TryGetProperty("diagnostic", out JsonElement diagnostic) == true
                    ? diagnostic.GetString() : null,
                plays ? Is.Null : Is.EqualTo(MediaSessionCalls.Unresponsive));
        });
    }

    private static JsonElement Json(string text)
    {
        using JsonDocument document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }

    private sealed class Session(Task<string> answer)
    {
        internal Task<string> Answer { get; } = answer;

        internal static Session Answering(string value) => new(Task.FromResult(value));

        internal static Session Hung() => new(new TaskCompletionSource<string>().Task);
    }

    private sealed class Player(ExternalCapabilityReceipt receipt) : IExternalOperationAdapter
    {
        internal bool Invoked { get; private set; }

        public bool CanHandle(string operation) => operation == receipt.Operation;

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken)
        {
            Invoked = true;
            return ValueTask.FromResult(receipt);
        }
    }
}
