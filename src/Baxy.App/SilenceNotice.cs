namespace Baxy.App;

/// <summary>
/// The goal's notice (PROMPT_GOAL_RENEW.md, identity: «un aviso que no afirma resultado si el turno va a pasar de 3 s en
/// silencio»): a turn the person opened that has published nothing <see cref="After"/> after the person's words (or
/// press) arrived, and is still working, asks the mind for its notice (<c>turn.notice</c>) and says the phrase it gets,
/// and asks again every <see cref="Again"/> while it stays silent. The words are the model's, written for what the turn
/// is doing: it is asked only while a call of the turn runs in the App (<see cref="Running"/>) and said only if it still
/// runs, the mind never writes the same phrase twice in a turn, and with no phrase nothing is said and the next expiry
/// asks again. So a turn whose line is published and not yet heard (al máximo 9.2b, below) or whose question for the
/// person's yes is on its way gets no notice now: no call runs then, and the owner wants none right before the turn can
/// be heard (2026-10-27: «no siempre»).
/// Until 2026-10-27 it was one phrase the mind wrote when it warmed up (the <c>notice</c> of its <c>catalog.ready</c>),
/// and the owner heard the same «Estoy procesando…» in every turn. The notice is not the turn's answer: it is only said
/// aloud, never a line of the conversation. The first sound of the turn's own line closes it under one gate, so the
/// notice is never said after the answer is heard, and a phrase that arrives once the turn closed or another opened is
/// not said. Al máximo 9.2b (2026-10-22): it closed when the line was published, and an answer published at 2.4 s that
/// sounded at 3.9 s left more than 3 s without a signal; a published line now keeps it open, even after the turn ends,
/// until the voice says the line began to sound (<see cref="Sounded"/>), for one more notice at most: a line the voice
/// never sounds (its synthesis failed) does not repeat it until the next turn. The voice says the notice from its own
/// audio while the line is still synthesized, and never once a line began to sound (voice_output.py).
/// Uso-124 (RX 7600 on Vulkan, ~100 tokens/s): between two calls, or before the first, the model may read for up to 89 s
/// (measured), and no notice can be written or said then: the model is busy, and it is said only while a call runs. While
/// its reading advances, a sound without words comes every <see cref="ReadingSign"/> (<see cref="Advanced"/>). There too
/// a notice takes 3 s to write and a web call under 1 s, so a phrase written for a call is said once that call ended as
/// well, when the mind says its notices are slow and the call completed: the turn's answer is still a long read away, and
/// the phrase says what the turn did, no result. One refused, failed or waiting for the person's yes did not do what the
/// phrase says (revisión PCR1, A1: «Borrando el archivo…» before «¿Lo borro?»), so its phrase is dropped, as is any on a
/// fast GPU: the answer is about to come.
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
    /// While the turn stays silent, the notice is due again this often (al máximo, flujos: a call of 30 to 160 s said
    /// it once at 2.5 s and then nothing, past the owner's 3 s without a sign).
    /// </summary>
    internal static readonly TimeSpan Again = TimeSpan.FromSeconds(10);

    /// <summary>
    /// How long a turn whose model is reading stays with nothing to hear before it sounds (<see cref="Advanced"/>): three
    /// such waits fit the minute a person should never spend hearing nothing; an NVIDIA GPU reads a whole turn in less.
    /// </summary>
    internal static readonly TimeSpan ReadingSign = TimeSpan.FromSeconds(20);

    private readonly object _gate = new();
    private readonly TimeProvider _time;
    private ITimer? _timer;
    private long _turn;
    private bool _open;
    // The turn published its line: the notice waits for that line's first sound, not for the turn's end.
    private bool _published;
    // This turn's question to the mind has not answered yet: an expiry meanwhile asks no other.
    private bool _asking;
    // Cancels that question when the notice closes (the question owns and disposes its source).
    private Action? _stopAsking;
    // A call of the turn runs in the App now (Running): the notice speaks of it, so it is asked and said only then.
    private bool _running;
    // The notice came due while no call ran (the model decided, or the answer was on its way): asked when one starts.
    private Action? _waiting;
    // This turn's way to ask (Open), and the question that last went to the mind (AheadAsync waits for it).
    private Func<Task>? _askNow;
    private Task _lastQuestion = Task.CompletedTask;
    // The sound of a model still reading (Open), and when the person last had something to hear.
    private Action? _reading;
    private long _lastSign;
    // Whether the mind says its notices are slow (Open), so a phrase may come after its call ended, and whether the
    // turn's last call that ended completed (Running): only then.
    private Func<bool>? _slow;
    private bool _completed;

    internal SilenceNotice(TimeProvider time)
    {
        _time = time ?? throw new ArgumentNullException(nameof(time));
    }

    /// <summary>
    /// A turn the person opened starts; their words or press arrived at <paramref name="arrivedAt"/>, a timestamp of this
    /// notice's clock (<see cref="System.Diagnostics.Stopwatch.GetTimestamp"/> for the system's), maybe well before the
    /// turn started (it waited for a heartbeat to end). <see cref="After"/> after that moment, if the turn has published
    /// nothing (or its line is not heard yet) and has not ended, <paramref name="ask"/> is asked for a phrase and
    /// <paramref name="say"/> gets it, and again every <see cref="Again"/>; with that moment already past, the check runs
    /// now, on the turn's thread. With no <paramref name="ask"/> (nobody would hear the notice) there is none. Otherwise
    /// the timer fires on the thread pool, and the check and the phrase the mind answers run on the context the turn runs
    /// on (the interface's thread, where the turn publishes too), when it has one. <paramref name="reading"/> sounds while
    /// the model reads (<see cref="Advanced"/>); <paramref name="slow"/> tells whether a phrase may be said after its call
    /// ended.
    /// </summary>
    internal void Open(Func<CancellationToken, Task<string?>>? ask, long arrivedAt, Action<string> say,
        Action? reading = null, Func<bool>? slow = null)
    {
        ArgumentNullException.ThrowIfNull(say);
        lock (_gate)
        {
            CloseLocked();
            long turn = ++_turn;
            if (ask is null)
            {
                return;
            }

            _open = true;
            _reading = reading;
            _slow = slow;
            _lastSign = arrivedAt;
            SynchronizationContext? context = SynchronizationContext.Current;
            // Each turn's timer asks with that turn's own number: an earlier turn's expiry says nothing in the next one.
            Func<Task> askNow = () => _lastQuestion = AskAsync(turn, ask, say, context);
            _askNow = askNow;
            Action notice = () => Due(() => askNow());
            TimeSpan due = After - _time.GetElapsedTime(arrivedAt);
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

    /// <summary>
    /// A call of the turn starts (<paramref name="running"/>) or ends running in the App, <paramref name="completed"/>
    /// or not. Feria 2026-10-27: a notice asked while the model decided waited behind that decision in the mind and spoke
    /// of a call that had already ended, or of one that was only asking the person's yes; it is asked while a call runs
    /// and said only if it still runs, or, with slow notices, once it ended completed.
    /// </summary>
    internal void Running(bool running, bool completed = false)
    {
        Action? waiting;
        lock (_gate)
        {
            _running = running;
            _completed = !running && completed;
            waiting = running ? _waiting : null;
            if (waiting is not null)
            {
                // Asked now: the next expiry is a whole Again from here, not a moment later.
                _waiting = null;
                _timer?.Change(Again, Again);
            }
        }

        waiting?.Invoke();
    }

    /// <summary>
    /// The mind says its model advanced through this turn's prompt or answer (a «progress» line, on the client's reader).
    /// With no call running (its notice speaks then) and no line of the turn on its way, and nothing to hear for
    /// <see cref="ReadingSign"/>, the turn's sound for a model still reading is played.
    /// </summary>
    internal void Advanced()
    {
        Action? reading;
        lock (_gate)
        {
            if (!_open || _running || _published || _time.GetElapsedTime(_lastSign) < ReadingSign)
            {
                return;
            }

            _lastSign = _time.GetTimestamp();
            reading = _reading;
        }

        reading?.Invoke();
    }

    /// <summary>
    /// Uso-125: the running call needs the model's own server (the description of a capture), so a notice asked once it
    /// began waits behind it and runs out of its time: asked now, and the call starts when the mind has answered. With a
    /// question already on its way (it came due before the call), that one is waited for. Nothing when no call runs.
    /// </summary>
    internal Task AheadAsync()
    {
        Func<Task>? askNow;
        lock (_gate)
        {
            if (!_open || !_running || _published)
            {
                return Task.CompletedTask;
            }

            if (_asking)
            {
                return _lastQuestion;
            }

            _waiting = null;
            _timer?.Change(Again, Again);
            askNow = _askNow;
        }

        return askNow?.Invoke() ?? Task.CompletedTask;
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

    // The notice is due: asked now while a call runs, else when the next one starts.
    private void Due(Action ask)
    {
        lock (_gate)
        {
            if (!_running)
            {
                _waiting = _open ? ask : null;
                return;
            }
        }

        ask();
    }

    // The mind is asked for a phrase unless this turn's question has not answered yet.
    private async Task AskAsync(
        long turn,
        Func<CancellationToken, Task<string?>> ask,
        Action<string> say,
        SynchronizationContext? context)
    {
        using var cancel = new CancellationTokenSource();
        Action stop = cancel.Cancel;
        lock (_gate)
        {
            if (!_open || turn != _turn || _asking)
            {
                return;
            }

            _asking = true;
            _stopAsking = stop;
        }

        string? phrase = null;
        try
        {
            phrase = await ask(cancel.Token).ConfigureAwait(false);
        }
        catch (Exception)
        {
            // The notice is only a sound beside the turn: a question that failed, or that the turn's close cancelled,
            // says nothing and never reaches the turn (the mind's client already traced a failed request).
        }
        finally
        {
            // Under the gate: the notice never cancels a source this question already disposed.
            lock (_gate)
            {
                if (ReferenceEquals(_stopAsking, stop))
                {
                    _stopAsking = null;
                }
            }
        }

        string? said = string.IsNullOrWhiteSpace(phrase) ? null : phrase.Trim();
        // An answer that came at once is still on the turn's thread; one that came later goes back to it.
        if (context is null || SynchronizationContext.Current == context)
        {
            Notice(turn, said, say);
        }
        else
        {
            context.Post(_ => Notice(turn, said, say), null);
        }
    }

    // The mind answered this turn's question: its phrase is said while the notice is still open for that turn.
    private void Notice(long turn, string? phrase, Action<string> say)
    {
        lock (_gate)
        {
            if (turn != _turn)
            {
                return;
            }

            _asking = false;
            if (!_open || phrase is null || (!_running && (!_completed || _slow?.Invoke() != true)))
            {
                return;
            }

            if (_published)
            {
                CloseLocked();
            }

            _lastSign = _time.GetTimestamp();
            say(phrase);
        }
    }

    private void CloseLocked()
    {
        _open = false;
        _published = false;
        _asking = false;
        _waiting = null;
        _askNow = null;
        _reading = null;
        _slow = null;
        _completed = false;
        _timer?.Dispose();
        _timer = null;
        Action? stop = _stopAsking;
        _stopAsking = null;
        stop?.Invoke();
    }
}
