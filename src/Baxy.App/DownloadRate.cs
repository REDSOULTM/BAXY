namespace Baxy.App;

/// <summary>
/// How fast a download goes and how long it has left. Encargo del dueño 2026-11-08: «un porcentaje de descarga que se vea
/// bonito, que yo pueda ver, ah, se está descargando». The speed is an exponential moving average, the usual way to keep a
/// time left from swinging with each burst (bugzilla.mozilla.org/show_bug.cgi?id=726445, «Improve time left indication»;
/// stackoverflow.com/questions/2779600): each sample weighs 1 − e^(−Δt/τ), so how often samples come does not change it.
/// Seen in the real App (2026-11-09): with the speed of the last 5 s, the time left went 4 → 3 → 2 → 3 min.
/// </summary>
internal sealed class DownloadRate(Func<DateTimeOffset>? clock = null)
{
    // The average's time constant: a change of speed shows in about this long.
    private static readonly TimeSpan Smoothing = TimeSpan.FromSeconds(20);

    // Nothing more arrived in this long: stalled, and no speed nor time is said. Counted to the moment it is read, not to the
    // last sample: a download that stopped dead sends none (REV_APP DL-a).
    private static readonly TimeSpan Stall = TimeSpan.FromSeconds(5);

    private readonly Func<DateTimeOffset> _clock = clock ?? (() => DateTimeOffset.UtcNow);
    private readonly object _sync = new();
    private DateTimeOffset? _at;
    private long _done;
    private DateTimeOffset _moved;
    private double? _speed;

    /// <summary>The download has <paramref name="done"/> bytes now.</summary>
    internal void Saw(long done)
    {
        lock (_sync)
        {
            DateTimeOffset now = _clock();
            if (_at is not { } before)
            {
                (_at, _done, _moved) = (now, done, now);
                return;
            }

            double seconds = (now - before).TotalSeconds;
            if (seconds < 0.25)
            {
                return;
            }

            if (done > _done)
            {
                _moved = now;
            }

            double sample = Math.Max(done - _done, 0) / seconds;
            double weight = 1 - Math.Exp(-seconds / Smoothing.TotalSeconds);
            _speed = _speed is { } average ? average + (weight * (sample - average)) : sample;
            (_at, _done) = (now, done);
        }
    }

    /// <summary>A new download starts.</summary>
    internal void Reset()
    {
        lock (_sync)
        {
            (_at, _done, _speed) = (null, 0, null);
        }
    }

    /// <summary>The bytes a second, smoothed; null before two samples, 0 when nothing arrived in the last seconds.</summary>
    internal long? BytesPerSecond
    {
        get
        {
            lock (_sync)
            {
                return _speed is not { } speed ? null : _at is not null && _clock() - _moved >= Stall ? 0 : (long)speed;
            }
        }
    }

    /// <summary>The seconds left to reach <paramref name="total"/> at that speed; null when there is none.</summary>
    internal long? SecondsLeft(long total)
    {
        long? speed = BytesPerSecond;
        long done;
        lock (_sync)
        {
            done = _done;
        }

        return speed is > 0 && total > done ? (long)Math.Ceiling((total - done) / (double)speed) : null;
    }
}
