using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 79 (F11, uso real: a misheard search played its result and came back failed in 5,9 s, the now-playing line
/// still on the track before it): what a search played is read after the press from Windows' media session, against
/// the same session before the call, with a bounded wait; the receipt says what plays.
/// </summary>
[TestFixture]
public sealed class SpotifySessionConfirmationTests
{
    private const string Client = "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify";
    private const string Misheard = """{"provider":"spotify","query":"Los Andamius Cobri"}""";
    private const string StaleLine = "marea lenta de nora vidal";
    private const string NewLine = "lluvia de cobre de los andamios";

    private static readonly UserMediaSession LoadedPaused = new(Client, "Marea Lenta", "Nora Vidal", "paused");
    private static readonly UserMediaSession LoadedPlaying = new(Client, "Marea Lenta", "Nora Vidal", "playing");
    private static readonly UserMediaSession Result = new(Client, "Lluvia de Cobre", "Los Andamios", "playing");

    private static string Answer(
        bool ok, string? error, string line, string title, string control, string? evidence, string before = StaleLine) =>
        JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["ok"] = ok,
            ["effectObserved"] = true,
            ["error"] = error,
            ["title"] = title,
            ["selectedControl"] = control,
            ["beforeNowPlaying"] = before,
            ["observedNowPlaying"] = line,
            ["playbackEvidence"] = evidence,
            ["processId"] = 42,
        });

    // The real case: the press showed, the line had not moved, the words searched are none of the result's. Windows
    // reports Playing with the old metadata first (measured live, 60-580 ms before the new title): the wait goes on.
    [Test]
    public async Task ASearchWhoseSessionMovedIsConfirmedAndSaysWhatPlaysThoughTheLineIsLate()
    {
        var sessions = new Sessions([LoadedPaused], [LoadedPlaying], [new("Opera", "Otra Cosa", "", "playing"), Result]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(true, null, StaleLine, "Los Andamios - Lluvia de Cobre", "Reproducir Lluvia de Cobre", "pressed_control_reads_pause")),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Result?.GetProperty("observedNowPlaying").GetString(), Is.EqualTo(NewLine));
            Assert.That(receipt.Result?.GetProperty("beforeNowPlaying").GetString(), Is.EqualTo(StaleLine));
            Assert.That(receipt.Result?.GetProperty("playbackEvidence").GetString(), Is.EqualTo("media_session_changed"));
            // Nothing says it is what was asked for: the words searched are none of what plays, and that is told.
            Assert.That(receipt.Result?.GetProperty("queryMatched").GetBoolean(), Is.False);
            Assert.That(sessions.Reads, Is.EqualTo(3));
        });
    }

    // The script's own wait ended on «only the loaded track resumed» with a client that was paused, so it cannot have
    // moved by itself: the session that shows another track is the press's.
    [Test]
    public async Task TheScriptsNotConfirmedGivesWayToASessionThatMoved()
    {
        var sessions = new Sessions([LoadedPaused], [Result]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(false, "spotify_query_result_not_confirmed", StaleLine, "Los Andamios - Lluvia de Cobre", "Reproducir", null)),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("observedNowPlaying").GetString(), Is.EqualTo(NewLine));
            Assert.That(receipt.Result?.GetProperty("playbackEvidence").GetString(), Is.EqualTo("media_session_changed"));
        });
    }

    // Ronda 19 stays: the press only resumed what the client had loaded. A paused client's window title moves to it too,
    // which is why the title alone proves nothing and the session is compared with itself. The wait is bounded.
    [Test]
    public async Task ASessionThatOnlyResumedTheLoadedTrackIsStillNotConfirmed()
    {
        var sessions = new Sessions([LoadedPaused], [LoadedPlaying]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(true, null, StaleLine, "Nora Vidal - Marea Lenta", "Reproducir", "pressed_control_reads_pause")),
            sessions: sessions.Read);
        var clock = System.Diagnostics.Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_query_result_not_confirmed"));
            Assert.That(receipt.Result?.GetProperty("observedNowPlaying").GetString(), Is.EqualTo(StaleLine));
            Assert.That(sessions.Reads, Is.GreaterThan(2));
            Assert.That(clock.Elapsed, Is.LessThan(SpotifyDesktopAdapter.SessionSettleLimit + TimeSpan.FromSeconds(2)));
        });
    }

    // A track that ended by itself while the search ran: the line the script read just before the press already names
    // what the session plays, so the press did not move it.
    [Test]
    public async Task ATrackThatAdvancedBeforeThePressIsNotThePressesDoing()
    {
        var sessions = new Sessions([LoadedPlaying], [Result]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(true, null, NewLine, "Los Andamios - Lluvia de Cobre", "Reproducir", "pressed_control_reads_pause", before: NewLine)),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_query_result_not_confirmed"));
    }

    // A press the client never showed taking stays a failure (a playing client's track can end by itself in those
    // seconds), and its receipt still says what plays.
    [Test]
    public async Task AnotherFailureStaysAFailureAndSaysWhatPlays()
    {
        var sessions = new Sessions([LoadedPlaying], [Result]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(false, "spotify_play_clicked_not_verified", StaleLine, "Los Andamios - Lluvia de Cobre", "Reproducir", null)),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_play_clicked_not_verified"));
            Assert.That(receipt.Result?.GetProperty("observedNowPlaying").GetString(), Is.EqualTo(NewLine));
        });
    }

    // The same for a title: its verdict is the now-playing line's identity, and only what plays is told.
    [Test]
    public async Task AnExactFailureKeepsItsVerdictAndSaysWhatPlays()
    {
        var sessions = new Sessions([LoadedPaused], [Result]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(false, "spotify_play_clicked_not_verified", StaleLine, "Los Andamios - Lluvia de Cobre", "Reproducir Marea", null)),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact", Json("""{"provider":"spotify","title":"Marea"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.Result?.GetProperty("observedNowPlaying").GetString(), Is.EqualTo(NewLine));
        });
    }

    // The loaded track was the first result: the session cannot move, but what was pressed, by name, is what plays.
    [TestCase("Reproducir Marea Lenta", true)]
    [TestCase("Reproducir Lluvia de Cobre", false)]
    [TestCase("Reproducir", false)]
    [TestCase("Reproducir U2", false)]
    public async Task AnUnmovedSessionIsConfirmedOnlyWhenThePressedResultIsNamedInWhatPlays(string control, bool verified)
    {
        var sessions = new Sessions([LoadedPaused], [LoadedPlaying]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(true, null, StaleLine, "Nora Vidal - Marea Lenta", control, "resumed_track_shares_word_prefix_with_pressed_result")),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.That(receipt.Verified, Is.EqualTo(verified), receipt.ErrorCode);
    }

    // The line already moved: nothing is waited for and the script's read stands (the session is read once, before).
    [Test]
    public async Task ALineThatMovedNeedsNoWait()
    {
        var sessions = new Sessions([LoadedPaused], [Result]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(true, null, NewLine, "Los Andamios - Lluvia de Cobre", "Reproducir", "now_playing_changed")),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("playbackEvidence").GetString(), Is.EqualTo("now_playing_changed"));
            Assert.That(sessions.Reads, Is.EqualTo(1));
        });
    }

    // Nothing pressed: there is no «after» to read.
    [Test]
    public async Task NoPressNoReadAfterIt()
    {
        var sessions = new Sessions([LoadedPaused], [Result]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner("""{"ok":false,"effectObserved":false,"error":"spotify_exact_result_not_found","stage":"searched"}"""),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_exact_result_not_found"));
            Assert.That(sessions.Reads, Is.EqualTo(1));
        });
    }

    // A client with no session (or Windows' service not answering) leaves the script's read as it was.
    [Test]
    public async Task NoSessionLeavesTheScriptsAnswer()
    {
        var sessions = new Sessions(new UserMediaSession[] { new("Opera", "Otra Cosa", "", "playing") });
        var adapter = new SpotifyDesktopAdapter(
            new Runner(Answer(true, null, StaleLine, "Los Andamios - Lluvia de Cobre", "Reproducir", "pressed_control_reads_pause")),
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_query_result_not_confirmed"));
    }

    // The whole call stays inside its budget: with nothing left of it the session is not waited for.
    [Test]
    public async Task ASpentCallBudgetWaitsForNoSession()
    {
        var time = new Clock();
        var sessions = new Sessions([LoadedPaused], [LoadedPlaying], [Result]);
        var adapter = new SpotifyDesktopAdapter(
            new Runner(
                Answer(true, null, StaleLine, "Los Andamios - Lluvia de Cobre", "Reproducir", "pressed_control_reads_pause"),
                () => time.Advance(SpotifyDesktopAdapter.CallBudget)),
            time: time,
            sessions: sessions.Read);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", Json(Misheard), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(sessions.Reads, Is.EqualTo(1));
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_query_result_not_confirmed"));
        });
    }

    // The product's adapter reads Windows' sessions (the seam's absence would silently turn all this off).
    [Test]
    public void TheProductsAdapterReadsTheSessions()
    {
        using var adapter = new SpotifyDesktopAdapter();

        Assert.That(adapter.ReadsMediaSessions, Is.True);
    }

    private static JsonElement Json(string text)
    {
        using JsonDocument document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }

    // Each read answers the next list; the last one stands.
    private sealed class Sessions(params UserMediaSession[][] reads)
    {
        internal int Reads { get; private set; }

        internal Task<IReadOnlyList<UserMediaSession>> Read(CancellationToken cancellationToken)
        {
            IReadOnlyList<UserMediaSession> read = reads[Math.Min(Reads, reads.Length - 1)];
            Reads++;
            return Task.FromResult(read);
        }
    }

    private sealed class Runner(string output, Action? effect = null) : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            effect?.Invoke();
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    private sealed class Clock : TimeProvider
    {
        private long _ticks;

        public override long TimestampFrequency => TimeSpan.TicksPerSecond;

        public override long GetTimestamp() => _ticks;

        internal void Advance(TimeSpan by) => _ticks += by.Ticks;
    }
}
