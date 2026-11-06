namespace Baxy.App;

/// <summary>
/// The relaunches of a piece of the engine (core or mind) after a start that failed or a loss: retried on their own with
/// a growing wait (10 s, 20 s, 40 s, then 60 s), within a limit. Uso 85 (notebook, Steam session): a core that failed the
/// same way at every start was relaunched for ever, the mind beside it killed each time mid-load, and the person saw
/// nothing but «Arrancando». The same cause <see cref="IdenticalLimit"/> times in a row, or <see cref="Limit"/> failures
/// of any cause, is a breakdown the interface shows (MainWindowViewModel.EngineUnavailable) instead of another relaunch.
/// A piece that stayed up <see cref="Stable"/> starts counting again (as systemd counts starts within an interval).
/// </summary>
internal sealed class StartupRetries
{
    internal const int IdenticalLimit = 5;
    internal const int Limit = 10;
    internal static readonly TimeSpan Stable = TimeSpan.FromMinutes(2);

    private int _failures;
    private int _identical;
    private string? _cause;
    private DateTimeOffset? _upSince;

    internal int Failures => _failures;

    /// <summary>A start or a run that failed by <paramref name="cause"/>: the wait before the next relaunch, or null when
    /// there is none to make (a breakdown).</summary>
    internal TimeSpan? Failed(string cause, DateTimeOffset at)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(cause);
        if (_upSince is { } up && at - up >= Stable)
        {
            Reset();
        }

        _upSince = null;
        _failures++;
        _identical = string.Equals(cause, _cause, StringComparison.Ordinal) ? _identical + 1 : 1;
        _cause = cause;
        return _identical >= IdenticalLimit || _failures >= Limit ? null : Delay(_failures);
    }

    /// <summary>The piece came up at <paramref name="at"/>.</summary>
    internal void Up(DateTimeOffset at) => _upSince = at;

    /// <summary>The person asked to try again: the count starts anew.</summary>
    internal void Reset()
    {
        _failures = 0;
        _identical = 0;
        _cause = null;
        _upSince = null;
    }

    internal static TimeSpan Delay(int failures) =>
        TimeSpan.FromSeconds(Math.Min(60, 10 * Math.Pow(2, Math.Clamp(failures, 1, 16) - 1)));
}
