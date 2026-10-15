namespace Baxy.App;

/// <summary>
/// The whole turn's time budget, counted from the moment the turn leaves the queue. Tanda t4-r6 (2026-10-08) had
/// turns of 18-34 s, most of them spent in verification waits that ended in failure. Once the budget is spent the
/// turn starts no further work of its own —the next step of a plan, a replan, a second composition— and says what
/// it did and what it left undone. Work already running finishes under its own bounds, so an effect is never cut
/// halfway.
/// </summary>
internal static class TurnBudget
{
    internal static readonly TimeSpan Total = TimeSpan.FromSeconds(45);

    internal static bool IsSpent(TimeSpan elapsed) => elapsed >= Total;

    /// <summary>
    /// The time the current turn has taken, from its <see cref="System.Diagnostics.Stopwatch"/> start. Outside a
    /// turn there is no turn to budget: a message published between turns (long after the last one began) is not
    /// a spent turn and keeps its second composition.
    /// </summary>
    internal static TimeSpan Elapsed(bool turnActive, long startedTimestamp) =>
        turnActive ? System.Diagnostics.Stopwatch.GetElapsedTime(startedTimestamp) : TimeSpan.Zero;
}
