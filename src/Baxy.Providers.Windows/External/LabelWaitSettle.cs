namespace Baxy.Providers.Windows.External;

/// <summary>
/// When a look that waits for a label (<c>waitForLabel</c>) can stop before its budget: the window showed the same
/// controls in <see cref="SettledLooks"/> looks in a row, so nothing in it is loading and the label is not coming. Banco
/// ciego c3 (2026-10-31): 12 of 16 such looks waited the whole 24 s for a label the still window never showed. A window
/// that shows nothing yet (a splash, a window still being drawn) is never settled: its budget stays.
/// </summary>
internal sealed class LabelWaitSettle
{
    internal const int SettledLooks = 3;

    private IReadOnlyList<string>? _last;
    private int _same;

    /// <summary>One more look's controls: whether the window has settled with them.</summary>
    internal bool Look(IReadOnlyList<string> names)
    {
        ArgumentNullException.ThrowIfNull(names);
        _same = names.Count > 0 && _last is not null && _last.SequenceEqual(names, StringComparer.Ordinal) ? _same + 1 : 1;
        _last = names;
        return names.Count > 0 && _same >= SettledLooks;
    }
}
