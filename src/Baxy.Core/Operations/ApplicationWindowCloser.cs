using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

/// <summary>What closing every window of one application observed.</summary>
/// <param name="ErrorCode">Why it stopped (app_not_running, app_running_in_background, close_prompted, the window provider's code), or null.</param>
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

/// <summary>An application's windows as resolved by its name (its dialogs among them), or why there are none.</summary>
/// <param name="ErrorCode">The window provider's code, app_running_in_background or app_not_running when it has no frame;
/// null with its windows.</param>
/// <param name="Background">With no frame, the application's processes still running (Steam in the notification area).</param>
internal sealed record ApplicationWindows(string? ErrorCode, IReadOnlyList<WindowCandidate> Windows,
    IReadOnlyList<int> Background);

/// <summary>
/// Auditoría de los pedidos reales (2026-10-17): an application's windows closed by its name, for app.close with appId
/// and for app.restart. The 4B model did not resolve a window before app.close and invented its windowId («1»), so the
/// name is resolved here. Each frame closes as app.close closes one window (gracefully, never forced); a window that
/// answers with a dialog of its own (to save) stops everything and is said; dialogs a frame owns go with it.
/// </summary>
internal static class ApplicationWindowCloser
{
    private const int MaximumWindows = 20;
    internal const string AppRunningInBackground = "app_running_in_background";

    internal static async ValueTask<ApplicationWindowsClosed> CloseAllAsync(
        IWindowControlProvider windows,
        string appId,
        CancellationToken cancellationToken)
    {
        ApplicationWindows resolved = await ResolveAsync(windows, appId, cancellationToken).ConfigureAwait(false);
        if (resolved.ErrorCode is { } missing)
        {
            return new(missing, 0, resolved.Background, [], false, 0, 0);
        }

        WindowCandidate[] frames = resolved.Windows.Where(window => !window.Owned).ToArray();

        var processes = new SortedSet<int>();
        var titles = new List<string>();
        int closedWindows = 0, hidden = 0;
        foreach (WindowCandidate frame in frames)
        {
            WindowCloseResult closed = await windows.CloseAsync(frame.WindowId, cancellationToken).ConfigureAwait(false);
            if (closed.ClosePrompted)
            {
                // Revisión del núcleo (q-core): a window already hidden is an effect too, as at the end.
                return new(WindowControlErrorCodes.ClosePrompted, closedWindows, processes, titles,
                    closedWindows > 0 || hidden > 0, hidden, frames.Length);
            }

            if (!closed.Succeeded || !closed.Verified || closed.ProcessId is null)
            {
                return new(closed.ErrorCode ?? "app_close_failed", closedWindows, processes, titles,
                    closedWindows > 0 || hidden > 0 || closed.EffectMayHaveOccurred, hidden, frames.Length);
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

        // Renew al máximo (auditoría de flujos): a window that only hid (the application went on in the notification
        // area) leaves its process running: never an application closed.
        return hidden > 0
            ? new(AppRunningInBackground, closedWindows, processes, titles, true, hidden, frames.Length)
            : new(null, closedWindows, processes, titles, closedWindows > 0, hidden, frames.Length);
    }

    /// <summary>
    /// Read only: the application's windows, or why there is none to close. Al máximo, flujos: app.close reads it before
    /// asking the person (IInvocationPreflight), and closing reads it again.
    /// </summary>
    internal static async ValueTask<ApplicationWindows> ResolveAsync(
        IWindowControlProvider windows,
        string appId,
        CancellationToken cancellationToken)
    {
        WindowResolveResult resolved = await windows.ResolveApplicationAsync(appId, MaximumWindows, cancellationToken)
            .ConfigureAwait(false);
        if (resolved.Succeeded && resolved.Verified && resolved.Windows.Any(window => !window.Owned))
        {
            return new(null, resolved.Windows, []);
        }

        if (!(resolved.Succeeded && resolved.Verified) && resolved.ErrorCode != WindowControlErrorCodes.WindowNotFound)
        {
            return new(resolved.ErrorCode ?? WindowControlErrorCodes.WindowNotFound, [], []);
        }

        // Renew al máximo (auditoría de flujos): with no window of it, an application whose processes still run (Steam in
        // the notification area) is said running in the background, with them; never «not running».
        IReadOnlyList<int> background = await windows.BackgroundProcessesAsync(appId, cancellationToken)
            .ConfigureAwait(false);
        return background.Count > 0
            ? new(AppRunningInBackground, [], [.. background.Order()])
            : new("app_not_running", [], []);
    }
}
