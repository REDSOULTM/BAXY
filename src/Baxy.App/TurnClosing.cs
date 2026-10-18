namespace Baxy.App;

/// <summary>
/// When a turn of the native tool loop takes no more calls and the model answers in words from the results it has (the
/// mind's final continue: tool_choice none). The model still decides every move; this only bounds how long and how
/// often it may move, from what ran, never from what the person said.
/// <list type="bullet">
/// <item>Its moves: <see cref="MaximumModelCalls"/>.</item>
/// <item>Its time (FT/proveedores goal, E5): <see cref="Budget"/> from the turn's start. An app.open of a console app
/// waited 30 s per verification and the model retried it up to the move cap: 7.5 min with no answer.</item>
/// <item>A call that came back the same: the same operation with the same arguments and the same outcome as the call
/// before it, twice when it failed (nothing changed, so a third try fails too) and three times otherwise (e2e E022:
/// the same page fetched eight times, until the results overflowed the context and the turn ended with no answer).</item>
/// </list>
/// </summary>
internal sealed class TurnClosing
{
    /// <summary>Model moves per turn.</summary>
    internal const int MaximumModelCalls = 15;

    /// <summary>The turn's time: longer than any turn of the practice e2e that passes (57 s at most, lote 3).</summary>
    internal static readonly TimeSpan Budget = TimeSpan.FromSeconds(90);

    private string? _last;
    private int _same;

    /// <summary>
    /// The call number <paramref name="calls"/> of the turn came back, <paramref name="elapsed"/> after the turn started,
    /// with <paramref name="status"/> and <paramref name="error"/>: whether the model answers now.
    /// </summary>
    internal bool AfterCall(int calls, TimeSpan elapsed, string operation, string arguments, string status, string? error)
    {
        string call = string.Join('\n', operation, arguments, status, error ?? string.Empty);
        _same = call == _last ? _same + 1 : 1;
        _last = call;
        bool failed = status is not (Contracts.OperationStatuses.Completed or Contracts.OperationStatuses.Pending);
        return calls >= MaximumModelCalls || elapsed >= Budget || _same >= (failed ? 2 : 3);
    }
}
