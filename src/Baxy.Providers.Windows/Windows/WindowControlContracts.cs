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
    // v3 r22 uso real: the close was asked politely and the application answered with a dialog of its own (it asks
    // whether to save); the window stays, and BAXY never answers that dialog.
    public const string ClosePrompted = "close_prompted";
    // BAXY Renew cu (C13 en el PC): the window takes no size nor place it is given (a browser in full screen kept the
    // whole screen); it was put back as it was, maximized.
    public const string WindowSizeNotTaken = "window_size_not_taken";
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
    string? Title = null,
    // A dialog or tool window an application window owns («Guardar como»): never the frame a person arranges.
    bool Owned = false,
    // Ronda 22 (revisión 1): where the window stands on the desktop when it was read. ZOrder counts the top-level
    // windows above it (0 = the top; the smallest is the one used last), Topmost is WS_EX_TOPMOST, and the work area
    // is that of the monitor that shows it. Null or false when the platform cannot tell.
    int? ZOrder = null,
    bool Topmost = false,
    int? WorkAreaWidth = null,
    int? WorkAreaHeight = null);

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
    string? ErrorCode,
    WindowRequestedSize? LargerThanRequested = null,
    // Round A: the failure came after the command reached the window (a state, a placement or a restore that was
    // sent and not read back as asked), so the window may have changed.
    bool EffectMayHaveOccurred = false,
    // Ronda final: the window already was as asked, read before anything was sent; nothing was sent.
    bool AlreadyReached = false);

// M159 (DEV-I v4w I-s048 «pasame la ventana de spotify a la derecha»): a placed
// window whose own minimum size is larger than the half it was asked to take.
// This is the size it was asked for; Window keeps its larger, observed one.
public sealed record WindowRequestedSize(int Width, int Height);

public sealed record WindowCloseResult(
    bool Succeeded,
    bool Verified,
    int? ProcessId,
    string? ErrorCode,
    // v3 r22 uso real: the window survived the polite close with a new dialog of its own application (closePrompted).
    bool ClosePrompted = false,
    // Encargo H1 (tandas fin1/fin2 t2-c03 t2: «He cerrado la ventana de Configuración de Valorant»): the title the
    // closed window had, as Windows wrote it, read right before the close; the receipt names what it closed.
    string? Title = null,
    // Auditoría D7: what was observed of the window (WindowCloseOutcomes), never «closed» for what BAXY did not close.
    string Outcome = WindowCloseOutcomes.Closed,
    // Round A: Windows took the close request and the window was still there when the reads ended.
    bool EffectMayHaveOccurred = false);

// Auditoría D7: closed (it went away after BAXY's close), alreadyGone (it was gone before BAXY's close reached it) or
// hidden (it still exists, invisible: an application that hides in the notification area instead of closing).
public static class WindowCloseOutcomes
{
    public const string Closed = "closed";
    public const string AlreadyGone = "alreadyGone";
    public const string Hidden = "hidden";
}

// MINALL1687 «minimizá todas las ventanas»: the desktop windows found before,
// how many were minimized and verified iconic, how many stayed visible.
public sealed record WindowMinimizeAllResult(
    bool Succeeded,
    bool Verified,
    int Found,
    int Minimized,
    int Remaining,
    string? ErrorCode,
    // Round A: the minimize was sent and some windows were not read back minimized.
    bool EffectMayHaveOccurred = false,
    // Ronda final: windows that were gone when sent to or read back (closed meanwhile): never counted as minimized.
    int Gone = 0,
    // Auditoría final: desktop windows there and not read, so not among «all».
    int Unread = 0,
    // Ronda final 11: titled windows DWM cloaks (another virtual desktop, a suspended app), not touched.
    int Cloaked = 0);

// CLOSEALL1733 «cerrame todo»: the desktop windows found before, how many were
// verified closed, how many stayed visible, how many were kept on purpose
// (BAXY's own windows, WindowsWindowControlProvider.OwnProcessNames, and the protected ones).
public sealed record WindowCloseAllResult(
    bool Succeeded,
    bool Verified,
    int Found,
    int Closed,
    int Remaining,
    int Kept,
    IReadOnlyList<string> KeptProcesses,
    IReadOnlyList<string> RemainingProcesses,
    string? ErrorCode,
    // Auditoría D7: windows that went invisible instead of closing, and windows gone before the close reached them;
    // neither is counted in Closed.
    int Hidden = 0,
    int AlreadyGone = 0,
    // Auditoría final: desktop windows there and not read, so not among «all».
    int Unread = 0,
    // Ronda final 11: titled windows DWM cloaks (another virtual desktop, a suspended app), not touched.
    int Cloaked = 0,
    // Renew al máximo (lote 4, d): of the kept, the windows no act reaches (a terminal, a console, an editor, a system
    // configuration tool: VisibleControlSurface.ProtectedFrom), never asked to close, and their processes.
    int ProtectedKept = 0,
    IReadOnlyList<string>? ProtectedProcesses = null);

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

    // Renew al máximo (auditoría de flujos): the processes of the application (by the executable its windows are told
    // by) that run with no visible window, as in the notification area; empty when none, or when the provider cannot
    // tell (a packaged application, the shell's own entry).
    ValueTask<IReadOnlyList<int>> BackgroundProcessesAsync(
        string applicationName,
        CancellationToken cancellationToken) =>
        ValueTask.FromResult<IReadOnlyList<int>>([]);

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
    // M159: a window whose own minimum is larger than that half ends flush
    // against the asked edge at its minimum, inside the work area, and the
    // result says so (LargerThanRequested).
    ValueTask<WindowActionResult> SnapAsync(
        string windowId,
        string side,
        CancellationToken cancellationToken) =>
        ValueTask.FromResult(new WindowActionResult(
            false, false, null, WindowControlErrorCodes.InvalidSelector));

    ValueTask<WindowCloseResult> CloseAsync(
        string windowId,
        CancellationToken cancellationToken);

    // v3 r6 lectores: whether the issued window holds no document of the person (closing it loses nothing), read
    // without consuming the id. Fail-closed: a provider that cannot tell says it may hold one.
    bool HoldsNoDocument(string windowId) => false;
}
