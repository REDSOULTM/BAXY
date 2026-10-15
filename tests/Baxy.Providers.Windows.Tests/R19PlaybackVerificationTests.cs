using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 19 «verificación de reproducción»: what plays is what was asked, a failure keeps its stage and detail, and a
/// playback that changes the way of playing pauses only the session BAXY itself left playing.
/// </summary>
[TestFixture]
public sealed class R19PlaybackVerificationTests
{
    private const string Opera = "OperaSoftware.OperaGXWebBrowser.1732473326";
    private const string Client = "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify";

    // t2-c01 T1: the press only resumed the track the client had loaded (Nujabes); the turn is a failure with its own
    // code, effect observed, and what was pressed and what played travel with it, never a success.
    [Test]
    public async Task AResumedLoadedTrackAfterTheSearchIsNotConfirmedNeverASuccess()
    {
        var runner = new Runner(NotConfirmedOutput);
        var adapter = new SpotifyDesktopAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(SpotifyDesktopAdapter.QueryResultNotConfirmed));
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("observedNowPlaying").GetString(),
                Is.EqualTo("aruarian dance de nujabes"));
            Assert.That(receipt.Result?.GetProperty("beforeNowPlaying").GetString(),
                Is.EqualTo("aruarian dance de nujabes"));
            Assert.That(receipt.Result?.GetProperty("selectedControl").GetString(), Is.EqualTo("Reproducir"));
            // The request's words never travel to the script: nothing is decided by a list of words. Ronda 24,
            // revisión 2: the only other argument is the fixed data of function words (the same for every
            // request, never derived from it), which the script sets aside when it compares the query. SP2: and its
            // deadline, the run's budget less the margin, never derived from the request either.
            Assert.That(runner.Arguments[^1], Is.EqualTo("query"));
            Assert.That(runner.Arguments, Has.Length.EqualTo(11));
            Assert.That(runner.Arguments[5], Is.EqualTo("-QueryWordsBase64"));
            Assert.That(runner.Arguments[6], Is.EqualTo(SpotifyDesktopAdapter.QueryWordsBase64.Value));
            Assert.That(runner.Arguments[7], Is.EqualTo("-DeadlineMs"));
            Assert.That(runner.Arguments[8],
                Is.EqualTo(SpotifyDesktopAdapter.ScriptDeadlineMs(SpotifyDesktopAdapter.ScriptBudget)));
        });
    }

    // t1-c07 #1: the script's catch-all failure keeps where it stopped and why.
    [Test]
    public async Task TheCatchAllFailureCarriesItsStageAndDetail()
    {
        var runner = new Runner(
            "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_uia_failed\",\"stage\":\"started\",\"detail\":\"spotify_foreground_not_verified\"}");
        var adapter = new SpotifyDesktopAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"lo-fi para estudiar"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_uia_failed"));
            Assert.That(receipt.Result?.GetProperty("stage").GetString(), Is.EqualTo("started"));
            Assert.That(receipt.Result?.GetProperty("detail").GetString(), Is.EqualTo("spotify_foreground_not_verified"));
        });
    }

    [Test]
    public async Task AFailureWithNothingToTellKeepsNoResult()
    {
        var runner = new Runner("{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_play_control_not_found\"}");
        var adapter = new SpotifyDesktopAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);

        Assert.That(receipt.Result, Is.Null);
    }

    // t2-c01 T2 «no mejor en youtube…»: the client BAXY had started kept playing under the video.
    [Test]
    public void ChangingTheWayOfPlayingPausesTheSessionBaxyLeftPlaying() =>
        Assert.That(WindowsMediaSessionAdapter.AssistantSessionToPause(
            [(Client, "Llueve", true), (Opera, "", false)], (Client, "Llueve", "media.play.query"), "media.play.youtube"),
            Is.EqualTo((Client, "Llueve")));

    [Test]
    public void ThePersonsOwnSessionIsNeverPaused()
    {
        Assert.Multiple(() =>
        {
            // Nothing BAXY played is remembered: the person's client playing is theirs.
            Assert.That(WindowsMediaSessionAdapter.AssistantSessionToPause(
                [(Client, "Su cancion", true)], null, "media.play.youtube"), Is.Null);
            // BAXY played in the browser; the client playing now is the person's.
            Assert.That(WindowsMediaSessionAdapter.AssistantSessionToPause(
                [(Client, "Su cancion", true), (Opera, "Video de BAXY", true)],
                (Opera, "Video de BAXY", "media.play.youtube"), "media.play.query"), Is.EqualTo((Opera, "Video de BAXY")));
            Assert.That(WindowsMediaSessionAdapter.AssistantSessionToPause(
                [(Client, "Su cancion", true), (Opera, "Video de BAXY", false)],
                (Opera, "Video de BAXY", "media.play.youtube"), "media.play.query"), Is.Null);
            // Revisión 2: the same app now plays another title (the person's own stream after BAXY's video ended).
            Assert.That(WindowsMediaSessionAdapter.AssistantSessionToPause(
                [(Opera, "Su propio stream", true)],
                (Opera, "Video de BAXY", "media.play.youtube"), "media.play.query"), Is.Null);
            // Nothing told BAXY's title from the person's: nothing is paused.
            Assert.That(WindowsMediaSessionAdapter.AssistantSessionToPause(
                [(Opera, "", true)], (Opera, "", "media.play.youtube"), "media.play.query"), Is.Null);
            // The same way of playing replaces nothing here.
            Assert.That(WindowsMediaSessionAdapter.AssistantSessionToPause(
                [(Client, "Llueve", true)], (Client, "Llueve", "media.play.query"), "media.play.exact"), Is.Null);
        });
    }

    [Test]
    public void TheSessionAVerifiedPlaybackStartedIsTheOneThatStartedPlaying()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsMediaSessionAdapter.NewlyPlayingSource(
                [(Client, "Old song", false), (Opera, "Their video", true)],
                [(Client, "Llueve sobre la ciudad", true), (Opera, "Their video", true)]), Is.EqualTo(Client));
            Assert.That(WindowsMediaSessionAdapter.NewlyPlayingSource(
                [(Opera, "Their video", true)], [(Opera, "Their video", true)]), Is.Null);
            Assert.That(WindowsMediaSessionAdapter.NewlyPlayingSource(
                [], [(Client, "A", true), (Opera, "B", true)]), Is.Null, "two sources started: none is claimed");
        });
    }

    // t2-c01 T1 then T2: the press that only resumed Nujabes failed with its effect observed, and that music was left
    // playing by BAXY's hand. «no, mejor en youtube» pauses it before the video plays.
    [Test]
    public async Task AFailedPressThatLeftMusicPlayingIsPausedWhenThePlaybackMovesToTheBrowser()
    {
        var sessions = new FakeSessions((Client, "aruarian dance", false));
        var spotify = new SpotifyDesktopAdapter(new Runner(NotConfirmedOutput, () => sessions.Play(Client)));
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null, sessions: sessions.Access);
        var youtube = new Browser(sessions);
        using var provider = new WindowsExternalCapabilityProvider([spotify, media, youtube]);

        ExternalCapabilityReceipt first = await provider.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);
        ExternalCapabilityReceipt second = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"los bunkers"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.False);
            Assert.That(first.EffectObserved, Is.True);
            Assert.That(second.Verified, Is.True);
            Assert.That(sessions.Paused, Is.EqualTo(new[] { Client }));
            Assert.That(youtube.ClientPlayingWhenItStarted, Is.False, "paused before the video started");
            // Revisión 2: the receipt carries the pause, which stands because the video played.
            Assert.That(second.AssistantPlaybackPauses,
                Is.EqualTo(new[] { new AssistantPlaybackPause(Client, "aruarian dance", Resumed: false) }));
            Assert.That(sessions.IsPlaying(Client), Is.False);
        });
    }

    // Contracase: the person's own Spotify was already playing before the failed press; it is theirs, never paused.
    [Test]
    public async Task AFailedPressNeverClaimsTheMusicThePersonWasAlreadyPlaying()
    {
        var sessions = new FakeSessions((Client, "su propia cancion", true));
        var spotify = new SpotifyDesktopAdapter(new Runner(NotConfirmedOutput));
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null, sessions: sessions.Access);
        using var provider = new WindowsExternalCapabilityProvider([spotify, media, new Browser(sessions)]);

        _ = await provider.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);
        _ = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"los bunkers"}"""), CancellationToken.None);

        Assert.That(sessions.Paused, Is.Empty);
    }

    // Contracase: a failure before any effect (nothing pressed) claims nothing, even if a session starts meanwhile.
    [Test]
    public async Task AFailureWithoutEffectClaimsNoSession()
    {
        var sessions = new FakeSessions((Client, "aruarian dance", false));
        var spotify = new SpotifyDesktopAdapter(new Runner(
            "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_result_not_found\"}",
            () => sessions.Play(Client)));
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null, sessions: sessions.Access);
        using var provider = new WindowsExternalCapabilityProvider([spotify, media, new Browser(sessions)]);

        _ = await provider.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);
        _ = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"los bunkers"}"""), CancellationToken.None);

        Assert.That(sessions.Paused, Is.Empty);
    }

    // Revisión 2, sonda 1: T1 a verified search in the client, T2 «mejor en youtube» fails before any effect (no
    // search result). The client was paused for the video; with no video it plays again, and the receipt says so.
    [TestCase("youtube_search_unavailable")]
    [TestCase("input_permission_denied")]
    [TestCase("browser_not_available")]
    public async Task APlaybackThatFailsBeforeItsEffectResumesWhatItPaused(string error)
    {
        var sessions = new FakeSessions((Client, "aruarian dance", false));
        var client = new Player("media.play.query", sessions, () =>
        {
            sessions.Set(Client, "Llueve sobre la ciudad", true);
            return ExternalJson.Success("media.play.query", Json($$"""{"sourceAppUserModelId":"{{Client}}"}"""));
        });
        var youtube = new Player("media.play.youtube", sessions,
            () => ExternalJson.FailureBeforeEffect("media.play.youtube", error));
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null, sessions: sessions.Access);
        using var provider = new WindowsExternalCapabilityProvider([client, media, youtube]);

        ExternalCapabilityReceipt first = await provider.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"llueve sobre la ciudad"}"""), CancellationToken.None);
        ExternalCapabilityReceipt second = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"llueve sobre la ciudad"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.True);
            Assert.That(second.Verified, Is.False);
            Assert.That(second.EffectObserved, Is.False);
            Assert.That(second.ErrorCode, Is.EqualTo(error));
            Assert.That(sessions.IsPlaying(Client), Is.True, "the client plays again");
            Assert.That(sessions.Resumed, Is.EqualTo(new[] { Client }));
            Assert.That(second.AssistantPlaybackPauses,
                Is.EqualTo(new[] { new AssistantPlaybackPause(Client, "Llueve sobre la ciudad", Resumed: true) }));
        });
    }

    // Revisión 2: when the paused client cannot be made to play again, the pause is the turn's effect and the
    // receipt says so; it is never «nothing happened».
    [Test]
    public async Task APauseThatCouldNotBeUndoneIsAnObservedEffect()
    {
        var sessions = new FakeSessions((Client, "aruarian dance", false)) { ResumeWorks = false };
        var client = new Player("media.play.query", sessions, () =>
        {
            sessions.Set(Client, "Llueve sobre la ciudad", true);
            return ExternalJson.Success("media.play.query", Json($$"""{"sourceAppUserModelId":"{{Client}}"}"""));
        });
        var youtube = new Player("media.play.youtube", sessions,
            () => ExternalJson.FailureBeforeEffect("media.play.youtube", "youtube_search_unavailable"));
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null,
            delay: (_, _) => ValueTask.CompletedTask, sessions: sessions.Access);
        using var provider = new WindowsExternalCapabilityProvider([client, media, youtube]);

        _ = await provider.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"llueve sobre la ciudad"}"""), CancellationToken.None);
        ExternalCapabilityReceipt second = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"llueve sobre la ciudad"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(second.Verified, Is.False);
            Assert.That(second.EffectObserved, Is.True);
            Assert.That(second.ErrorCode, Is.EqualTo("youtube_search_unavailable"));
            JsonElement pause = second.Result!.Value.GetProperty("pausedAssistantPlayback")[0];
            Assert.That(pause.GetProperty("sourceAppUserModelId").GetString(), Is.EqualTo(Client));
            Assert.That(pause.GetProperty("resumed").GetBoolean(), Is.False);
            Assert.That(second.AssistantPlaybackPauses.Single().Resumed, Is.False);
        });
    }

    // Revisión 2, sonda 2: BAXY's video in the browser ended and the person put their own stream on in the same
    // browser; «pon X en spotify» never pauses the person's stream.
    [Test]
    public async Task ThePersonsStreamInTheBrowserBaxyUsedIsNeverPaused()
    {
        var sessions = new FakeSessions((Opera, "", false));
        var youtube = new Player("media.play.youtube", sessions, () =>
        {
            sessions.Set(Opera, "Video de BAXY", true);
            return ExternalJson.Success("media.play.youtube", Json($$"""{"sourceAppUserModelId":"{{Opera}}"}"""));
        });
        var client = new Player("media.play.query", sessions,
            () => ExternalJson.Success("media.play.query", Json($$"""{"sourceAppUserModelId":"{{Client}}"}""")));
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null, sessions: sessions.Access);
        using var provider = new WindowsExternalCapabilityProvider([client, media, youtube]);

        ExternalCapabilityReceipt first = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"video de baxy"}"""), CancellationToken.None);
        sessions.Set(Opera, "Su propio stream", true);
        ExternalCapabilityReceipt second = await provider.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.True);
            Assert.That(second.Verified, Is.True);
            Assert.That(sessions.Paused, Is.Empty);
            Assert.That(sessions.IsPlaying(Opera), Is.True);
            Assert.That(second.AssistantPlaybackPauses, Is.Empty);
        });
    }

    // Revisión 2, sonda 2 al revés: the person put their own song on in the client BAXY used; «pon X en youtube»
    // never pauses it.
    [Test]
    public async Task ThePersonsSongInTheClientBaxyUsedIsNeverPaused()
    {
        var sessions = new FakeSessions((Client, "aruarian dance", false));
        var client = new Player("media.play.query", sessions, () =>
        {
            sessions.Set(Client, "Cancion de BAXY", true);
            return ExternalJson.Success("media.play.query", Json($$"""{"sourceAppUserModelId":"{{Client}}"}"""));
        });
        var youtube = new Player("media.play.youtube", sessions,
            () => ExternalJson.Success("media.play.youtube", Json($$"""{"sourceAppUserModelId":"{{Opera}}"}""")));
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null, sessions: sessions.Access);
        using var provider = new WindowsExternalCapabilityProvider([client, media, youtube]);

        _ = await provider.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"cancion de baxy"}"""), CancellationToken.None);
        sessions.Set(Client, "Su propia cancion", true);
        _ = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"los bunkers"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sessions.Paused, Is.Empty);
            Assert.That(sessions.IsPlaying(Client), Is.True);
        });
    }

    // Revisión 2: two sessions of the same browser (BAXY's video and the person's stream in another tab); only
    // BAXY's is paused.
    [Test]
    public async Task OnlyBaxysSessionOfTheSameAppIsPaused()
    {
        var sessions = new FakeSessions((Opera, "Su propio stream", true));
        var youtube = new Player("media.play.youtube", sessions, () =>
        {
            sessions.Add(Opera, "Video de BAXY", true);
            return ExternalJson.Success("media.play.youtube", Json($$"""{"sourceAppUserModelId":"{{Opera}}"}"""));
        });
        var client = new Player("media.play.query", sessions,
            () => ExternalJson.Success("media.play.query", Json($$"""{"sourceAppUserModelId":"{{Client}}"}""")));
        using var media = new WindowsMediaSessionAdapter(new HttpClient(), () => null, sessions: sessions.Access);
        using var provider = new WindowsExternalCapabilityProvider([client, media, youtube]);

        _ = await provider.InvokeAsync(
            "media.play.youtube", Json("""{"query":"video de baxy"}"""), CancellationToken.None);
        _ = await provider.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sessions.Paused, Is.EqualTo(new[] { Opera }));
            Assert.That(sessions.IsPlaying(Opera, "Su propio stream"), Is.True);
            Assert.That(sessions.IsPlaying(Opera, "Video de BAXY"), Is.False);
        });
    }

    private const string NotConfirmedOutput =
        "{\"ok\":false,\"effectObserved\":true,\"error\":\"spotify_query_result_not_confirmed\",\"title\":\"Nujabes - aruarian dance\",\"selectedControl\":\"Reproducir\",\"beforeNowPlaying\":\"aruarian dance de nujabes\",\"observedNowPlaying\":\"aruarian dance de nujabes\",\"pauseBefore\":false,\"selectedFlipped\":false,\"processId\":42}";

    private static JsonElement Json(string text)
    {
        using JsonDocument document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }

    private sealed class Runner(string output, Action? effect = null) : IExternalProcessRunner
    {
        internal string[] Arguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            Arguments = arguments.ToArray();
            effect?.Invoke();
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    /// <summary>The system media sessions, as a list the test plays, pauses and resumes.</summary>
    private sealed class FakeSessions
    {
        private readonly List<(string Source, string Title, bool Playing)> _sessions;

        internal FakeSessions(params (string Source, string Title, bool Playing)[] sessions)
        {
            _sessions = [.. sessions];
            Access = new WindowsMediaSessionAdapter.MediaSessionAccess(
                () => ValueTask.FromResult<IReadOnlyList<(string Source, string Title, bool Playing)>>(_sessions.ToArray()),
                (source, title) =>
                {
                    Paused.Add(source);
                    SetPlaying(source, title, false);
                    return ValueTask.CompletedTask;
                },
                (source, title) =>
                {
                    Resumed.Add(source);
                    if (ResumeWorks)
                    {
                        SetPlaying(source, title, true);
                    }
                    return ValueTask.CompletedTask;
                });
        }

        internal WindowsMediaSessionAdapter.MediaSessionAccess Access { get; }

        internal List<string> Paused { get; } = [];

        internal List<string> Resumed { get; } = [];

        internal bool ResumeWorks { get; init; } = true;

        internal bool IsPlaying(string source) => _sessions.Any(session => session.Source == source && session.Playing);

        internal bool IsPlaying(string source, string title) =>
            _sessions.Any(session => session.Source == source && session.Title == title && session.Playing);

        internal void Play(string source) => Set(source, true);

        /// <summary>The one session of that source now plays (or not) that title.</summary>
        internal void Set(string source, string title, bool playing)
        {
            int index = _sessions.FindIndex(session => session.Source == source);
            _sessions[index] = (source, title, playing);
        }

        /// <summary>Another session of that source (another browser tab).</summary>
        internal void Add(string source, string title, bool playing) => _sessions.Add((source, title, playing));

        private void Set(string source, bool playing)
        {
            for (int index = 0; index < _sessions.Count; index++)
            {
                if (_sessions[index].Source == source)
                {
                    _sessions[index] = _sessions[index] with { Playing = playing };
                }
            }
        }

        private void SetPlaying(string source, string title, bool playing)
        {
            for (int index = 0; index < _sessions.Count; index++)
            {
                if (_sessions[index].Source == source && _sessions[index].Title == title)
                {
                    _sessions[index] = _sessions[index] with { Playing = playing };
                }
            }
        }
    }

    /// <summary>A play operation's adapter: its receipt, and what it does to the sessions while it plays.</summary>
    private sealed class Player(string operation, FakeSessions sessions, Func<ExternalCapabilityReceipt> play)
        : IExternalOperationAdapter
    {
        internal FakeSessions Sessions { get; } = sessions;

        public bool CanHandle(string candidate) => candidate == operation;

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string candidate, JsonElement arguments, CancellationToken cancellationToken) =>
            ValueTask.FromResult(play());
    }

    /// <summary>The browser's video playback: verified, and it starts its own session.</summary>
    private sealed class Browser(FakeSessions sessions) : IExternalOperationAdapter
    {
        internal bool? ClientPlayingWhenItStarted { get; private set; }

        public bool CanHandle(string operation) => operation == "media.play.youtube";

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken)
        {
            ClientPlayingWhenItStarted = sessions.IsPlaying(Client);
            return ValueTask.FromResult(ExternalJson.Success(operation, Json("""{"sourceAppUserModelId":"OperaSoftware.OperaGXWebBrowser.1732473326"}""")));
        }
    }
}
