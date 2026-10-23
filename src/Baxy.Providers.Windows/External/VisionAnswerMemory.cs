namespace Baxy.Providers.Windows.External;

/// <summary>
/// Renew al máximo (velocidad): the last answer of the vision stage that pressed nothing (no place named, or a place on
/// another written label twice), with the label asked and the drawing of the window it was asked on. The same label on
/// the same drawing of the same window, a moment later, gets that answer again without asking the model (8-20 s on the
/// CPU projector, asked at temperature 0 on the same image): a click the model retries at once, and a later look of the
/// same click's wait. The drawing is the same when its image is, or when it differs only in a caret (at most two cells
/// one above the other, VisibleControlSurface.MotionCell): Notepad's caret blinks between any two captures.
/// </summary>
internal sealed class VisionAnswerMemory(Func<DateTime>? utcNow = null)
{
    /// <summary>How long an answer is kept: a retry of the same click comes within seconds.</summary>
    internal static readonly TimeSpan KeptFor = TimeSpan.FromSeconds(90);

    private readonly Func<DateTime> _utcNow = utcNow ?? (() => DateTime.UtcNow);
    private readonly object _lock = new();
    private Answered? _last;

    private sealed record Answered(string Label, VisibleControlSurface.CapturedWindow Image, string? Code, DateTime At);

    /// <summary>The answer given to <paramref name="label"/> on this drawing of the window, if one was given: null for
    /// «no place named», otherwise the code it ended with.</summary>
    internal bool Recall(string label, VisibleControlSurface.CapturedWindow image, out string? code)
    {
        code = null;
        Answered? last;
        lock (_lock)
        {
            last = _last;
        }

        if (last is null || _utcNow() - last.At > KeptFor
            || !string.Equals(last.Label, label, StringComparison.Ordinal)
            || !SameDrawing(last.Image, image))
            return false;
        code = last.Code;
        return true;
    }

    internal void Note(string label, VisibleControlSurface.CapturedWindow image, string? code)
    {
        lock (_lock)
        {
            _last = new Answered(label, image, code, _utcNow());
        }
    }

    internal void Forget()
    {
        lock (_lock)
        {
            _last = null;
        }
    }

    internal static bool SameDrawing(VisibleControlSurface.CapturedWindow before, VisibleControlSurface.CapturedWindow now)
    {
        if (before.Hwnd != now.Hwnd || before.Left != now.Left || before.Top != now.Top
            || before.Width != now.Width || before.Height != now.Height)
            return false;
        if (string.Equals(before.Sha256, now.Sha256, StringComparison.Ordinal))
            return true;
        if (VisibleControlSurface.DifferingCells(before, now, out int columns, out _) is not { } differing)
            return false;
        int[] changed = [.. Enumerable.Range(0, differing.Length).Where(cell => differing[cell]).Take(3)];
        return changed.Length switch
        {
            0 => true,
            1 => true,
            2 => changed[1] - changed[0] == columns,
            _ => false,
        };
    }
}
