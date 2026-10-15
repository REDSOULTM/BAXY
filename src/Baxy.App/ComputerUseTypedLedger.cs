namespace Baxy.App;

/// <summary>
/// The texts BAXY typed in the computer-use missions of this session (falsos éxitos v3 M1, v3-17: the gallery's search
/// box still held the name typed a turn before, and the next turn cited it as done). Bounded; the newest kept.
/// </summary>
internal sealed class ComputerUseTypedLedger
{
    private const int Kept = 64;
    private readonly List<TypedEarlier> _entries = [];
    private readonly object _gate = new();

    /// <summary>
    /// Ronda 23 (v3-58): what was typed, the box it went into and the application of the window it was typed on, so a
    /// later turn tells the echo of an earlier search on that window from an arrival.
    /// </summary>
    internal void Add(string? text, string? into = null, string? process = null)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        lock (_gate)
        {
            _entries.Add(new TypedEarlier(text, into, process));
            if (_entries.Count > Kept)
            {
                _entries.RemoveAt(0);
            }
        }
    }

    internal IReadOnlyList<string> Texts
    {
        get
        {
            lock (_gate)
            {
                return [.. _entries.Select(entry => entry.Text)];
            }
        }
    }

    internal IReadOnlyList<TypedEarlier> Entries
    {
        get
        {
            lock (_gate)
            {
                return [.. _entries];
            }
        }
    }
}

/// <summary>A text typed in an earlier computer-use mission of the session: into which box, on which application.</summary>
internal readonly record struct TypedEarlier(string Text, string? Into, string? Process);
