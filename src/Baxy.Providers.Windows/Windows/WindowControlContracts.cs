namespace Baxy.Providers.Windows.Windows;

public static class WindowControlErrorCodes
{
    public const string InvalidSelector = "invalid_selector";
    public const string WindowNotFound = "window_not_found";
    public const string InvalidOrExpiredWindowId = "invalid_or_expired_window_id";
    public const string WindowIdentityChanged = "window_identity_changed";
    public const string ActionFailed = "action_failed";
    public const string VerificationFailed = "verification_failed";
    public const string InventoryFailed = "inventory_failed";
}

public enum WindowControlAction
{
    Focus,
    Minimize,
    Maximize,
    Restore,
}

public sealed record WindowCandidate(
    string WindowId,
    int ProcessId,
    string ProcessName,
    string State,
    bool Foreground,
    int X,
    int Y,
    int Width,
    int Height,
    string? Title = null);

public sealed record WindowResolveResult(
    bool Succeeded,
    bool Verified,
    IReadOnlyList<WindowCandidate> Windows,
    string? ErrorCode,
    WindowInventoryPage? Page = null);

// Each request enumerates again. Offset does not bind later pages to a snapshot.
public sealed record WindowInventoryPage(
    int Limit,
    int Offset,
    int ObservedCount,
    bool Complete,
    int? NextOffset);

public sealed record WindowActionResult(
    bool Succeeded,
    bool Verified,
    WindowCandidate? Window,
    string? ErrorCode);

public sealed record WindowCloseResult(
    bool Succeeded,
    bool Verified,
    int? ProcessId,
    string? ErrorCode);

// MINALL1687 «minimizá todas las ventanas»: the desktop windows found before,
// how many were minimized and verified iconic, how many stayed visible.
public sealed record WindowMinimizeAllResult(
    bool Succeeded,
    bool Verified,
    int Found,
    int Minimized,
    int Remaining,
    string? ErrorCode);

// CLOSEALL1733 «cerrame todo»: the desktop windows found before, how many were
// verified closed, how many stayed visible, how many were kept on purpose
// (the editor hosting the person's work and the terminal).
public sealed record WindowCloseAllResult(
    bool Succeeded,
    bool Verified,
    int Found,
    int Closed,
    int Remaining,
    int Kept,
    IReadOnlyList<string> KeptProcesses,
    IReadOnlyList<string> RemainingProcesses,
    string? ErrorCode);

public interface IWindowControlProvider
{
    ValueTask<WindowCloseAllResult> CloseAllAsync(CancellationToken cancellationToken) =>
        ValueTask.FromResult(new WindowCloseAllResult(
            false, false, 0, 0, 0, 0, [], [], WindowControlErrorCodes.ActionFailed));

    ValueTask<WindowMinimizeAllResult> MinimizeAllAsync(CancellationToken cancellationToken) =>
        ValueTask.FromResult(new WindowMinimizeAllResult(
            false, false, 0, 0, 0, WindowControlErrorCodes.ActionFailed));

    ValueTask<WindowResolveResult> ResolveForegroundAsync(
        CancellationToken cancellationToken);

    ValueTask<WindowResolveResult> ResolveAsync(
        string processName,
        int limit,
        CancellationToken cancellationToken,
        bool byTitle = false,
        int offset = 0);

    ValueTask<WindowResolveResult> ResolveApplicationAsync(
        string applicationName,
        int limit,
        CancellationToken cancellationToken) =>
        ValueTask.FromResult(new WindowResolveResult(
            false, false, [], WindowControlErrorCodes.InvalidSelector));

    ValueTask<WindowActionResult> ExecuteAsync(
        string windowId,
        WindowControlAction action,
        CancellationToken cancellationToken);

    ValueTask<WindowActionResult> SetBoundsAsync(
        string windowId,
        int? x,
        int? y,
        int? width,
        int? height,
        CancellationToken cancellationToken);

    // ARRANGE1781: the window takes the left or right half of its monitor's
    // work area («poné chrome a la izquierda»); exact bounds verified.
    ValueTask<WindowActionResult> SnapAsync(
        string windowId,
        string side,
        CancellationToken cancellationToken) =>
        ValueTask.FromResult(new WindowActionResult(
            false, false, null, WindowControlErrorCodes.InvalidSelector));

    ValueTask<WindowCloseResult> CloseAsync(
        string windowId,
        CancellationToken cancellationToken);
}
