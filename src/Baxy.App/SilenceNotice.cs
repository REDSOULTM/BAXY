using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// The goal's notice (PROMPT_GOAL_RENEW.md, identity: «un aviso que no afirma resultado si el turno va a pasar de 3 s en
/// silencio»): a turn the person opened that has published nothing <see cref="After"/> after it started, and is still
/// working, says once the mind's own notice phrase (the <c>notice</c> of its <c>catalog.ready</c>). The words are the
/// mind's: with no phrase from it there is no notice. The notice is not the turn's answer: it is only said aloud, never
/// a line of the conversation. Whatever comes first closes it, the turn's own line or the notice, under one gate, so the
/// notice is never said after the answer nor twice.
/// </summary>
internal sealed class SilenceNotice
{
    /// <summary>
    /// 2.0 s: e2e p11/p12 left 31 of 72 commands silent past 3 s (file.find 11-12 s, web.fetch 9-14 s); the same runs
    /// simulated with a notice at 2.0 s gave a first sound at 2.0 s p50 and 2 of 72 past 3 s (leader, 2026-10-16).
    /// </summary>
    internal static readonly TimeSpan After = TimeSpan.FromSeconds(2.0);

    private readonly object _gate = new();
    private readonly TimeProvider _time;
    private ITimer? _timer;
    private long _turn;
    private bool _open;

    internal SilenceNotice(TimeProvider time)
    {
        _time = time ?? throw new ArgumentNullException(nameof(time));
    }

    /// <summary>The mind's phrase in its <c>catalog.ready</c>, trimmed; null when it sent none.</summary>
    internal static string? PhraseOf(JsonObject? catalogReady) =>
        catalogReady?["notice"] is JsonValue value && value.TryGetValue(out string? text)
            && !string.IsNullOrWhiteSpace(text)
                ? text.Trim()
                : null;

    /// <summary>
    /// A turn the person opened starts: <see cref="After"/> later, if the turn has published nothing, has not ended and
    /// <paramref name="mayNotice"/> holds, <paramref name="say"/> gets <paramref name="phrase"/> once. The timer fires on
    /// the thread pool; the check and the notice run on the context the turn runs on (the interface's thread, where the
    /// turn publishes too), when it has one.
    /// </summary>
    internal void Open(string? phrase, Func<bool> mayNotice, Action<string> say)
    {
        ArgumentNullException.ThrowIfNull(mayNotice);
        ArgumentNullException.ThrowIfNull(say);
        lock (_gate)
        {
            CloseLocked();
            long turn = ++_turn;
            if (phrase is null)
            {
                return;
            }

            _open = true;
            SynchronizationContext? context = SynchronizationContext.Current;
            Action notice = () => Notice(turn, phrase, mayNotice, say);
            _timer = _time.CreateTimer(
                _ =>
                {
                    if (context is null)
                    {
                        notice();
                    }
                    else
                    {
                        context.Post(static state => ((Action)state!)(), notice);
                    }
                },
                null,
                After,
                Timeout.InfiniteTimeSpan);
        }
    }

    /// <summary>The turn publishes its own line (answer, question, confirmation): no notice can follow it.</summary>
    internal void Publish(Action publish)
    {
        ArgumentNullException.ThrowIfNull(publish);
        lock (_gate)
        {
            CloseLocked();
            publish();
        }
    }

    /// <summary>The turn ended.</summary>
    internal void Close()
    {
        lock (_gate)
        {
            CloseLocked();
        }
    }

    private void Notice(long turn, string phrase, Func<bool> mayNotice, Action<string> say)
    {
        lock (_gate)
        {
            if (!_open || turn != _turn || !mayNotice())
            {
                return;
            }

            CloseLocked();
            say(phrase);
        }
    }

    private void CloseLocked()
    {
        _open = false;
        _timer?.Dispose();
        _timer = null;
    }
}
