using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// The goal's notice (PROMPT_GOAL_RENEW.md, identity: «un aviso que no afirma resultado si el turno va a pasar de 3 s en
/// silencio»): a turn the person opened that has published nothing <see cref="After"/> after the person's words (or
/// press) arrived, and is still working, says the mind's own notice phrase (the <c>notice</c> of its
/// <c>catalog.ready</c>), and again every <see cref="Again"/> while it stays silent. The words are the mind's: with no
/// phrase from it there is no notice. The notice is not the turn's answer: it is only said aloud, never a line of the
/// conversation. The first sound of the turn's own line closes it under one gate, so the notice is never said after the
/// answer is heard. Al máximo 9.2b (2026-10-22): it closed when the line was published, and an answer published at 2.4 s
/// that sounded at 3.9 s left more than 3 s without a signal; a published line now keeps it open, even after the turn
/// ends, until the voice says the line began to sound (<see cref="Sounded"/>), for one more notice at most: a line the
/// voice never sounds (its synthesis failed) does not repeat it until the next turn. The voice says the notice from its
/// own audio while the line is still synthesized, and never once a line began to sound (voice_output.py).
/// </summary>
internal sealed class SilenceNotice
{
    /// <summary>
    /// 2.5 s: e2e p11/p12 left 31 of 72 commands silent past 3 s (file.find 11-12 s, web.fetch 9-14 s). At 2.0 s (p14)
    /// the first sound came at 2106 ms p50 with none past 3 s, but the notice took the voice when an answer was due at
    /// 2-3 s: the answer's own first sound went from 2535 ms p50 (p13, no notice) to 3994 ms. 2.5 s lets those answers
    /// come first (leader, 2026-10-16).
    /// </summary>
    internal static readonly TimeSpan After = TimeSpan.FromSeconds(2.5);

    /// <summary>
    /// While the turn stays silent, the same notice comes again this often (al máximo, flujos: a call of 30 to 160 s
    /// said it once at 2.5 s and then nothing, past the owner's 3 s without a sign).
    /// </summary>
    internal static readonly TimeSpan Again = TimeSpan.FromSeconds(10);

    private readonly object _gate = new();
    private readonly TimeProvider _time;
    private ITimer? _timer;
    private long _turn;
    private bool _open;
    // The turn published its line: the notice waits for that line's first sound, not for the turn's end.
    private bool _published;

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
    /// A turn the person opened starts; their words or press arrived at <paramref name="arrivedAt"/>, a timestamp of this
    /// notice's clock (<see cref="System.Diagnostics.Stopwatch.GetTimestamp"/> for the system's), maybe well before the
    /// turn started (it waited for a heartbeat to end). <see cref="After"/> after that moment, if the turn has published
    /// nothing (or its line is not heard yet) and has not ended, <paramref name="say"/> gets <paramref name="phrase"/>,
    /// and again every <see cref="Again"/>; with that moment already past, the check and the notice run now, on the turn's thread. Otherwise the timer
    /// fires on the thread pool and the check and the notice run on the context the turn runs on (the interface's thread,
    /// where the turn publishes too), when it has one.
    /// </summary>
    internal void Open(string? phrase, long arrivedAt, Action<string> say)
    {
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
            Action notice = () => Notice(turn, phrase, say);
            TimeSpan due = After - _time.GetElapsedTime(arrivedAt);
            SynchronizationContext? context = SynchronizationContext.Current;
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
                due <= TimeSpan.Zero ? Again : due,
                Again);
            if (due <= TimeSpan.Zero)
            {
                notice();
            }
        }
    }

    /// <summary>
    /// The turn publishes its own line (answer, question, confirmation): the notice still counts until that line is
    /// heard (<see cref="Sounded"/>). A line that is not said aloud (the voice muted or unavailable) has no notice
    /// either: the host says none then.
    /// </summary>
    internal void Publish(Action publish)
    {
        ArgumentNullException.ThrowIfNull(publish);
        lock (_gate)
        {
            _published = _open;
            publish();
        }
    }

    /// <summary>
    /// A line BAXY says, not the notice, began to sound. Once the turn published its line no notice can follow; a
    /// sound before that (a heartbeat's words the turn waited for) is not this turn's answer and leaves it open.
    /// </summary>
    internal void Sounded()
    {
        lock (_gate)
        {
            if (_published)
            {
                CloseLocked();
            }
        }
    }

    /// <summary>The turn ended: a turn that published nothing says no notice; one whose line is not heard yet still may.</summary>
    internal void Close()
    {
        lock (_gate)
        {
            if (!_published)
            {
                CloseLocked();
            }
        }
    }

    private void Notice(long turn, string phrase, Action<string> say)
    {
        lock (_gate)
        {
            if (!_open || turn != _turn)
            {
                return;
            }

            if (_published)
            {
                CloseLocked();
            }

            say(phrase);
        }
    }

    private void CloseLocked()
    {
        _open = false;
        _published = false;
        _timer?.Dispose();
        _timer = null;
    }
}
