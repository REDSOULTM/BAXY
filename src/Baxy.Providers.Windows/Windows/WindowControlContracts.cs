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
    string? ErrorCode);

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

public interface IWindowControlProvider
{
    ValueTask<WindowResolveResult> ResolveForegroundAsync(
        CancellationToken cancellationToken);

    ValueTask<WindowResolveResult> ResolveAsync(
        string processName,
        int limit,
        CancellationToken cancellationToken,
        bool byTitle = false);

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

    ValueTask<WindowCloseResult> CloseAsync(
        string windowId,
        CancellationToken cancellationToken);
}
