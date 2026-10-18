using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

/// <summary>What closing every window of one application observed.</summary>
/// <param name="ErrorCode">Why it stopped (app_not_running, close_prompted, the window provider's code), or null.</param>
/// <param name="ClosedWindows">Windows that went away after BAXY's close (not those already gone or hidden).</param>
/// <param name="ProcessIds">The processes of the windows BAXY closed or found gone.</param>
/// <param name="Titles">The titles the closed windows had, as Windows wrote them.</param>
internal sealed record ApplicationWindowsClosed(
    string? ErrorCode,
    int ClosedWindows,
    IReadOnlyCollection<int> ProcessIds,
    IReadOnlyList<string> Titles,
    bool EffectMayHaveOccurred,
    int HiddenWindows,
    int Frames);

/// <summary>
/// Auditoría de los pedidos reales (2026-10-17): an application's windows closed by its name, for app.close with appId
/// and for app.restart. The 4B model did not resolve a window before app.close and invented its windowId («1»), so the
/// name is resolved here. Each frame closes as app.close closes one window (gracefully, never forced); a window that
/// answers with a dialog of its own (to save) stops everything and is said; dialogs a frame owns go with it.
/// </summary>
internal static class ApplicationWindowCloser
{
    private const int MaximumWindows = 20;

    internal static async ValueTask<ApplicationWindowsClosed> CloseAllAsync(
        IWindowControlProvider windows,
        string appId,
        CancellationToken cancellationToken)
    {
        WindowResolveResult resolved = await windows.ResolveApplicationAsync(appId, MaximumWindows, cancellationToken)
            .ConfigureAwait(false);
        if (!resolved.Succeeded || !resolved.Verified)
        {
            return new(resolved.ErrorCode ?? WindowControlErrorCodes.WindowNotFound, 0, [], [], false, 0, 0);
        }

        WindowCandidate[] frames = resolved.Windows.Where(window => !window.Owned).ToArray();
        if (frames.Length == 0)
        {
            return new("app_not_running", 0, [], [], false, 0, 0);
        }

        var processes = new SortedSet<int>();
        var titles = new List<string>();
        int closedWindows = 0, hidden = 0;
        foreach (WindowCandidate frame in frames)
        {
            WindowCloseResult closed = await windows.CloseAsync(frame.WindowId, cancellationToken).ConfigureAwait(false);
            if (closed.ClosePrompted)
            {
                return new(WindowControlErrorCodes.ClosePrompted, closedWindows, processes, titles, closedWindows > 0, hidden,
                    frames.Length);
            }

            if (!closed.Succeeded || !closed.Verified || closed.ProcessId is null)
            {
                return new(closed.ErrorCode ?? "app_close_failed", closedWindows, processes, titles,
                    closedWindows > 0 || closed.EffectMayHaveOccurred, hidden, frames.Length);
            }

            processes.Add(closed.ProcessId.Value);
            if (closed.Outcome == WindowCloseOutcomes.Closed)
            {
                closedWindows++;
                if (!string.IsNullOrWhiteSpace(closed.Title))
                    titles.Add(closed.Title);
            }
            else if (closed.Outcome == WindowCloseOutcomes.Hidden)
            {
                hidden++;
            }
        }

        return new(null, closedWindows, processes, titles, closedWindows > 0, hidden, frames.Length);
    }
}
