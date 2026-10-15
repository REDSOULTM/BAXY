using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using Windows.Foundation;
using Windows.Media.Control;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Every call into Windows' media sessions waits at most <see cref="CallLimit"/>. SP2 (notebook tandas): after the first
/// video opened in the browser every media operation ran out its budget (media.play.query 75 s of 65, media.play.youtube
/// 90 of 90, a pause 30,4 of 20): a session whose app hangs never answers, and an unbounded await held the whole
/// operation. A session that does not answer is left out and the others are read; while its read is still pending it is
/// left out at once, so a polling loop never pays the limit twice. The operation in course is told
/// (<see cref="Watch"/>), and its failure says <see cref="Unresponsive"/>.
/// </summary>
internal static class MediaSessionCalls
{
    internal const string Unresponsive = "media_session_unresponsive";

    internal static readonly TimeSpan CallLimit = TimeSpan.FromSeconds(2.5);

    private static readonly AsyncLocal<StrongBox<bool>?> Unanswered = new();

    private static readonly ConditionalWeakTable<object, Task> Pending = new();

    /// <summary>Watches the operation in course: the box turns true when a media session call in it went unanswered.</summary>
    internal static StrongBox<bool> Watch() => Unanswered.Value = new StrongBox<bool>();

    /// <summary>The receipt of a watched operation: a failure in which a session went unanswered says so.</summary>
    internal static ExternalCapabilityReceipt Diagnosed(ExternalCapabilityReceipt receipt, StrongBox<bool> watch) =>
        !watch.Value || receipt.Verified
            ? receipt
            : receipt with
            {
                Result = ExternalJson.Extended(receipt.Result, writer => writer.WriteString("diagnostic", Unresponsive)),
            };

    /// <summary>Awaits one call within the limit; a call that does not answer in time throws <see cref="TimeoutException"/>.</summary>
    internal static async Task<T> WithinLimitAsync<T>(Task<T> call, CancellationToken cancellationToken = default)
    {
        try
        {
            return await call.WaitAsync(CallLimit, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            MarkUnanswered();
            throw;
        }
    }

    internal static Task<T> Bounded<T>(this IAsyncOperation<T> call, CancellationToken cancellationToken = default) =>
        WithinLimitAsync(call.AsTask(), cancellationToken);

    /// <summary>
    /// Reads every session at once, each within the limit, in their order. A session that does not answer, or whose
    /// earlier read is still pending, is left out; any other failure of a read is the read's.
    /// </summary>
    internal static async Task<IReadOnlyList<TRead>> ReadEachAsync<TSession, TRead>(
        IEnumerable<TSession> sessions,
        Func<TSession, Task<TRead>> read,
        CancellationToken cancellationToken = default)
        where TSession : class
    {
        (bool Answered, TRead Value)[] reads = await Task.WhenAll(sessions.Select(async session =>
        {
            if (Pending.TryGetValue(session, out Task? earlier) && !earlier.IsCompleted)
            {
                MarkUnanswered();
                return (false, default(TRead)!);
            }

            Task<TRead> call = Task.Run(() => read(session), CancellationToken.None);
            Pending.AddOrUpdate(session, call);
            try
            {
                return (true, await WithinLimitAsync(call, cancellationToken).ConfigureAwait(false));
            }
            catch (TimeoutException)
            {
                return (false, default(TRead)!);
            }
        })).ConfigureAwait(false);
        return reads.Where(item => item.Answered).Select(item => item.Value).ToArray();
    }

    /// <summary>The system media sessions now: source, title, artist and playback status. Empty when unreadable.</summary>
    internal static async Task<IReadOnlyList<UserMediaSession>> ReadAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            GlobalSystemMediaTransportControlsSessionManager manager =
                await GlobalSystemMediaTransportControlsSessionManager.RequestAsync().Bounded(cancellationToken)
                    .ConfigureAwait(false);
            return await ReadEachAsync(manager.GetSessions(), ReadOneAsync, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            // No media session service: nothing can be observed through it.
            return [];
        }
    }

    /// <summary>
    /// Plays or pauses the first system session of that source with that title, and says whether it took the command.
    /// A session that does not answer is never commanded.
    /// </summary>
    internal static async Task<bool> ControlAsync(
        string source, string title, bool pause, CancellationToken cancellationToken = default)
    {
        GlobalSystemMediaTransportControlsSessionManager manager =
            await GlobalSystemMediaTransportControlsSessionManager.RequestAsync().Bounded(cancellationToken)
                .ConfigureAwait(false);
        IReadOnlyList<(GlobalSystemMediaTransportControlsSession Session, UserMediaSession Read)> sessions =
            await ReadEachAsync(
                manager.GetSessions().Where(session =>
                    string.Equals(session.SourceAppUserModelId, source, StringComparison.Ordinal)),
                async session => (session, await ReadOneAsync(session).ConfigureAwait(false)),
                cancellationToken).ConfigureAwait(false);
        GlobalSystemMediaTransportControlsSession? target = sessions
            .FirstOrDefault(item => string.Equals(item.Read.Title, title, StringComparison.Ordinal)).Session;
        return target is not null
            && await (pause ? target.TryPauseAsync() : target.TryPlayAsync()).Bounded(cancellationToken)
                .ConfigureAwait(false);
    }

    private static async Task<UserMediaSession> ReadOneAsync(GlobalSystemMediaTransportControlsSession session)
    {
        string title = string.Empty;
        string artist = string.Empty;
        try
        {
            GlobalSystemMediaTransportControlsSessionMediaProperties properties =
                await session.TryGetMediaPropertiesAsync();
            title = properties?.Title ?? string.Empty;
            artist = properties?.Artist ?? string.Empty;
        }
        catch (Exception exception) when (exception is COMException or InvalidOperationException)
        {
            // A session without readable metadata still has a state.
        }

        return new UserMediaSession(
            session.SourceAppUserModelId ?? string.Empty,
            title,
            artist,
            StatusName(session.GetPlaybackInfo()?.PlaybackStatus));
    }

    private static string StatusName(GlobalSystemMediaTransportControlsSessionPlaybackStatus? status) =>
        status switch
        {
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing => "playing",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Paused => "paused",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Stopped => "stopped",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Closed => "closed",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Opened => "opened",
            GlobalSystemMediaTransportControlsSessionPlaybackStatus.Changing => "changing",
            _ => string.Empty,
        };

    private static void MarkUnanswered()
    {
        if (Unanswered.Value is { } watch)
        {
            watch.Value = true;
        }
    }
}
