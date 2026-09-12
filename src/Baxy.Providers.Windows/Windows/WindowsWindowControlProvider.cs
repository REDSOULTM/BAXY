using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Providers.Windows.Windows;

public sealed class WindowsWindowControlProvider : IWindowControlProvider
{
    private static readonly TimeSpan HandleLifetime = TimeSpan.FromMinutes(5);
    private static readonly TimeSpan VerificationDelay = TimeSpan.FromMilliseconds(100);
    private const int MaximumHandles = 512;
    private const int StateVerificationAttempts = 20;
    private const int PrimaryCloseVerificationAttempts = 5;
    private const int FallbackCloseVerificationAttempts = 20;

    private readonly IWindowControlPlatform _platform;
    private readonly WindowsInstalledApplicationOpenProvider _applications;
    private readonly WindowsWindowControlVerifier _verifier;
    private readonly object _gate = new();
    private readonly Dictionary<string, WindowIdentity> _handles = new(StringComparer.Ordinal);

    public WindowsWindowControlProvider()
        : this(new Win32WindowControlPlatform(), new WindowsInstalledApplicationOpenProvider())
    {
    }

    public WindowsWindowControlProvider(WindowsInstalledApplicationOpenProvider applications)
        : this(new Win32WindowControlPlatform(), applications)
    {
    }

    internal WindowsWindowControlProvider(IWindowControlPlatform platform)
        : this(platform, new WindowsInstalledApplicationOpenProvider())
    {
    }

    internal WindowsWindowControlProvider(
        IWindowControlPlatform platform,
        WindowsInstalledApplicationOpenProvider applications)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _applications = applications ?? throw new ArgumentNullException(nameof(applications));
        _verifier = new WindowsWindowControlVerifier(platform);
    }

    public ValueTask<WindowResolveResult> ResolveForegroundAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        WindowSnapshot? snapshot;
        try
        {
            snapshot = _platform.FindForegroundWindow();
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException
            or NotSupportedException)
        {
            return ValueTask.FromResult(new WindowResolveResult(
                false, false, [], WindowControlErrorCodes.InventoryFailed));
        }

        if (snapshot is null)
        {
            return ValueTask.FromResult(new WindowResolveResult(
                false, false, [], WindowControlErrorCodes.WindowNotFound));
        }

        string windowId = Issue(snapshot.Identity);
        WindowCandidate candidate = ToCandidate(snapshot, windowId);
        if (!candidate.Foreground
            || !_verifier.Verify(snapshot.Identity, candidate, expectedAction: null))
        {
            Revoke(windowId);
            return ValueTask.FromResult(new WindowResolveResult(
                false, false, [], WindowControlErrorCodes.VerificationFailed));
        }

        return ValueTask.FromResult(new WindowResolveResult(true, true, [candidate], null));
    }

    public ValueTask<WindowResolveResult> ResolveAsync(
        string processName,
        int limit,
        CancellationToken cancellationToken,
        bool byTitle = false,
        int offset = 0)
    {
        cancellationToken.ThrowIfCancellationRequested();
        // Recognize this before normalizing .exe; "*.exe" remains a process
        // selector and byTitle=true always keeps title matching semantics.
        bool allWindows = !byTitle && string.Equals(processName?.Trim(), "*", StringComparison.Ordinal);
        string? selector = byTitle
            ? (!string.IsNullOrWhiteSpace(processName) && processName.Length <= 260
                && !processName.Contains('\0') ? processName.Trim() : null)
            : NormalizeProcessName(processName);
        if (selector is null || limit is < 1 or > 50 || offset < 0)
        {
            return ValueTask.FromResult(new WindowResolveResult(
                false, false, [], WindowControlErrorCodes.InvalidSelector));
        }

        WindowEnumeration enumeration;
        try
        {
            enumeration = _platform.FindVisibleWindows(
                selector, limit, byTitle, offset, allWindows, cancellationToken);
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException
            or NotSupportedException)
        {
            return ValueTask.FromResult(new WindowResolveResult(
                false, false, [], WindowControlErrorCodes.InventoryFailed));
        }

        cancellationToken.ThrowIfCancellationRequested();
        IReadOnlyList<WindowSnapshot> snapshots = enumeration.Windows;
        if (!allWindows && enumeration.ObservedCount == 0)
        {
            return ValueTask.FromResult(new WindowResolveResult(
                false, false, [], WindowControlErrorCodes.WindowNotFound));
        }

        List<WindowCandidate> candidates = new(snapshots.Count);
        foreach (WindowSnapshot snapshot in snapshots)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string windowId = Issue(snapshot.Identity);
            WindowCandidate candidate = ToCandidate(snapshot, windowId);
            if (!_verifier.Verify(snapshot.Identity, candidate, expectedAction: null))
            {
                Revoke(windowId);
                return ValueTask.FromResult(new WindowResolveResult(
                    false, false, [], WindowControlErrorCodes.VerificationFailed));
            }

            candidates.Add(candidate);
        }

        int? nextOffset = (long)offset + snapshots.Count < enumeration.ObservedCount
            ? offset + snapshots.Count
            : null;
        var page = new WindowInventoryPage(limit, offset,
            enumeration.ObservedCount, enumeration.Complete, nextOffset);
        return ValueTask.FromResult(new WindowResolveResult(true, true, candidates, null, page));
    }

    public async ValueTask<WindowResolveResult> ResolveApplicationAsync(
        string applicationName,
        int limit,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!ApplicationIds.IsValidRequest(applicationName) || limit is < 1 or > 50)
            return new(false, false, [], WindowControlErrorCodes.InvalidSelector);

        var issued = new List<string>();
        bool published = false;
        try
        {
            var resolution = await _applications.ResolveWindowIdentitiesAsync(
                applicationName, cancellationToken).ConfigureAwait(false);
            if (resolution.ErrorCode is not null)
                return new(false, false, [], resolution.ErrorCode);
            InstalledApplicationObservation[] observations = resolution.Windows
                .DistinctBy(static item => (item.WindowHandle, item.ProcessId, item.ProcessCreationTimeUtcTicks))
                .ToArray();
            if (observations.Length == 0)
                return new(false, false, [], WindowControlErrorCodes.WindowNotFound);
            // A partial application selection must not look like one unambiguous
            // dependency result. Never issue a first-page-only close candidate.
            if (observations.Length > limit)
                return new(false, false, [], "application_window_selection_incomplete");

            var candidates = new List<WindowCandidate>(observations.Length);
            foreach (InstalledApplicationObservation observation in observations)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!observation.Visible || observation.WindowHandle == 0
                    || string.IsNullOrWhiteSpace(observation.ProcessName)
                    || !Path.IsPathFullyQualified(observation.ExecutablePath))
                    return new(false, false, [], WindowControlErrorCodes.VerificationFailed);
                var identity = new WindowIdentity(
                    checked((nint)observation.WindowHandle), observation.ProcessId,
                    observation.ProcessCreationTimeUtcTicks, observation.ProcessName,
                    _platform.UtcNow, Path.GetFullPath(observation.ExecutablePath));
                WindowSnapshot snapshot = _platform.Observe(identity);
                string windowId = Issue(identity);
                issued.Add(windowId);
                WindowCandidate candidate = ToCandidate(snapshot, windowId);
                if (!_verifier.Verify(identity, candidate, expectedAction: null))
                    return new(false, false, [], WindowControlErrorCodes.VerificationFailed);
                candidates.Add(candidate);
            }
            published = true;
            return new(true, true, candidates, null,
                new WindowInventoryPage(limit, 0, candidates.Count, true, null));
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException or NotSupportedException
            or ArgumentException or OverflowException)
        {
            return new(false, false, [], WindowControlErrorCodes.VerificationFailed);
        }
        finally
        {
            if (!published)
                foreach (string windowId in issued)
                    Revoke(windowId);
        }
    }

    public async ValueTask<WindowActionResult> ExecuteAsync(
        string windowId,
        WindowControlAction action,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!TryConsume(windowId, out WindowIdentity? identity))
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InvalidOrExpiredWindowId);
        }

        WindowSnapshot before;
        try
        {
            before = _platform.Observe(identity!);
        }
        catch (WindowIdentityChangedException)
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.WindowIdentityChanged);
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException)
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InventoryFailed);
        }

        cancellationToken.ThrowIfCancellationRequested();
        if (!_platform.Execute(before.Identity, action))
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.ActionFailed);
        }

        for (int attempt = 0; attempt < StateVerificationAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            WindowSnapshot after;
            try
            {
                after = _platform.Observe(before.Identity);
            }
            catch (Exception exception) when (exception is Win32Exception
                or InvalidOperationException
                or WindowIdentityChangedException)
            {
                return new WindowActionResult(
                    false, false, null, WindowControlErrorCodes.VerificationFailed);
            }

            if (WindowsWindowControlVerifier.MatchesExpectedAction(after, action))
            {
                string refreshedId = Issue(after.Identity);
                WindowCandidate candidate = ToCandidate(after, refreshedId);
                if (_verifier.Verify(after.Identity, candidate, action))
                {
                    return new WindowActionResult(true, true, candidate, null);
                }

                Revoke(refreshedId);
            }

            if (attempt + 1 < StateVerificationAttempts)
            {
                await _platform.DelayAsync(VerificationDelay, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return new WindowActionResult(
            false, false, null, WindowControlErrorCodes.VerificationFailed);
    }

    public ValueTask<WindowActionResult> SetBoundsAsync(
        string windowId,
        int? x,
        int? y,
        int? width,
        int? height,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        bool move = x.HasValue && y.HasValue && !width.HasValue && !height.HasValue;
        bool resize = !x.HasValue && !y.HasValue && width.HasValue && height.HasValue;
        if ((!move && !resize) || width is <= 0 || height is <= 0)
        {
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InvalidSelector));
        }
        if (!TryConsume(windowId, out WindowIdentity? identity))
        {
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InvalidOrExpiredWindowId));
        }

        WindowSnapshot before;
        try
        {
            before = _platform.Observe(identity!);
        }
        catch (WindowIdentityChangedException)
        {
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.WindowIdentityChanged));
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InventoryFailed));
        }

        var expected = new WindowBounds(
            x ?? before.Bounds.X,
            y ?? before.Bounds.Y,
            width ?? before.Bounds.Width,
            height ?? before.Bounds.Height);
        cancellationToken.ThrowIfCancellationRequested();
        if (!_platform.SetBounds(before.Identity, expected))
        {
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.ActionFailed));
        }

        WindowSnapshot after;
        try
        {
            after = _platform.Observe(before.Identity);
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException
            or WindowIdentityChangedException)
        {
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed));
        }
        if (after.Bounds != expected)
        {
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed));
        }

        string refreshedId = Issue(after.Identity);
        WindowCandidate candidate = ToCandidate(after, refreshedId);
        if (!_verifier.Verify(after.Identity, candidate, expectedAction: null))
        {
            Revoke(refreshedId);
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed));
        }
        return ValueTask.FromResult(new WindowActionResult(true, true, candidate, null));
    }

    public async ValueTask<WindowCloseResult> CloseAsync(
        string windowId,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!TryConsume(windowId, out WindowIdentity? identity))
        {
            return new WindowCloseResult(
                false, false, null, WindowControlErrorCodes.InvalidOrExpiredWindowId);
        }

        try
        {
            _ = _platform.Observe(identity!);
        }
        catch (WindowIdentityChangedException)
        {
            return new WindowCloseResult(
                false, false, null, WindowControlErrorCodes.WindowIdentityChanged);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return new WindowCloseResult(false, false, null, WindowControlErrorCodes.InventoryFailed);
        }

        bool primaryAccepted;
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            primaryAccepted = _platform.RequestClose(identity!);
        }
        catch (WindowIdentityChangedException)
        {
            return new WindowCloseResult(true, true, identity!.ProcessId, null);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return new WindowCloseResult(
                false, false, identity!.ProcessId, WindowControlErrorCodes.ActionFailed);
        }

        if (primaryAccepted
            && await WaitForClosedAsync(
                    identity!,
                    PrimaryCloseVerificationAttempts,
                    cancellationToken)
                .ConfigureAwait(false))
        {
            return new WindowCloseResult(true, true, identity!.ProcessId, null);
        }

        // Some system-hosted and UIAccess windows deliberately ignore or reject
        // WM_CLOSE but accept the same close command from their system menu. Rebind
        // the exact identity before using that fallback so an HWND reuse cannot be
        // targeted.
        bool fallbackAccepted;
        try
        {
            _ = _platform.Observe(identity!);
            cancellationToken.ThrowIfCancellationRequested();
            fallbackAccepted = _platform.RequestSystemClose(identity!);
        }
        catch (WindowIdentityChangedException)
        {
            return new WindowCloseResult(true, true, identity!.ProcessId, null);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            fallbackAccepted = false;
        }

        if (fallbackAccepted
            && await WaitForClosedAsync(
                    identity!,
                    FallbackCloseVerificationAttempts,
                    cancellationToken)
                .ConfigureAwait(false))
        {
            return new WindowCloseResult(true, true, identity!.ProcessId, null);
        }

        return new WindowCloseResult(
            false,
            false,
            identity!.ProcessId,
            primaryAccepted || fallbackAccepted
                ? WindowControlErrorCodes.VerificationFailed
                : WindowControlErrorCodes.ActionFailed);
    }

    private async ValueTask<bool> WaitForClosedAsync(
        WindowIdentity identity,
        int attempts,
        CancellationToken cancellationToken)
    {
        for (int attempt = 0; attempt < attempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (_verifier.VerifyClosed(identity))
            {
                return true;
            }

            if (attempt + 1 < attempts)
            {
                await _platform.DelayAsync(VerificationDelay, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return false;
    }

    private string Issue(WindowIdentity identity)
    {
        lock (_gate)
        {
            RemoveExpired();
            while (_handles.Count >= MaximumHandles)
            {
                string oldest = _handles.MinBy(static pair => pair.Value.IssuedAtUtc).Key;
                _handles.Remove(oldest);
            }

            string id;
            do
            {
                id = string.Concat("win_", Convert.ToHexString(RandomNumberGenerator.GetBytes(16))
                    .ToLowerInvariant());
            }
            while (_handles.ContainsKey(id));

            _handles.Add(id, identity with { IssuedAtUtc = _platform.UtcNow });
            return id;
        }
    }

    private bool TryConsume(string id, out WindowIdentity? identity)
    {
        identity = null;
        if (string.IsNullOrEmpty(id)
            || id.Length != 36
            || !id.StartsWith("win_", StringComparison.Ordinal)
            || !id.AsSpan(4).ToString().All(static character =>
                character is >= '0' and <= '9' or >= 'a' and <= 'f'))
        {
            return false;
        }

        lock (_gate)
        {
            RemoveExpired();
            if (!_handles.Remove(id, out WindowIdentity? found))
            {
                return false;
            }

            identity = found;
            return true;
        }
    }

    private void Revoke(string id)
    {
        lock (_gate)
        {
            _handles.Remove(id);
        }
    }

    private void RemoveExpired()
    {
        DateTimeOffset cutoff = _platform.UtcNow - HandleLifetime;
        foreach (string id in _handles
                     .Where(pair => pair.Value.IssuedAtUtc <= cutoff)
                     .Select(static pair => pair.Key)
                     .ToArray())
        {
            _handles.Remove(id);
        }
    }

    private static string? NormalizeProcessName(string? value)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Length > 260
            || value.IndexOfAny(['\\', '/', ':', '\0']) >= 0)
        {
            return null;
        }

        string normalized = value.Trim();
        if (normalized.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
        {
            normalized = normalized[..^4];
        }

        return normalized.Length == 0 ? null : normalized;
    }

    private static WindowCandidate ToCandidate(WindowSnapshot snapshot, string id) =>
        new(id, snapshot.Identity.ProcessId, snapshot.Identity.ProcessName,
            snapshot.State, snapshot.Foreground, snapshot.Bounds.X, snapshot.Bounds.Y,
            snapshot.Bounds.Width, snapshot.Bounds.Height, snapshot.Title);
}

internal sealed class WindowsWindowControlVerifier(IWindowControlPlatform platform)
{
    public bool VerifyClosed(WindowIdentity identity)
    {
        try
        {
            _ = platform.Observe(identity);
            return false;
        }
        catch (WindowIdentityChangedException)
        {
            return true;
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return false;
        }
    }

    public bool Verify(
        WindowIdentity identity,
        WindowCandidate candidate,
        WindowControlAction? expectedAction)
    {
        WindowSnapshot observed;
        try
        {
            observed = platform.Observe(identity);
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException
            or WindowIdentityChangedException)
        {
            return false;
        }

        return MatchesExpectedAction(observed, expectedAction)
            && candidate.ProcessId == observed.Identity.ProcessId
            && string.Equals(candidate.ProcessName, observed.Identity.ProcessName,
                StringComparison.OrdinalIgnoreCase)
            && string.Equals(candidate.State, observed.State, StringComparison.Ordinal)
            && string.Equals(candidate.Title, observed.Title, StringComparison.Ordinal)
            && candidate.Foreground == observed.Foreground
            && candidate.X == observed.Bounds.X
            && candidate.Y == observed.Bounds.Y
            && candidate.Width == observed.Bounds.Width
            && candidate.Height == observed.Bounds.Height;
    }

    public static bool MatchesExpectedAction(
        WindowSnapshot observed,
        WindowControlAction? expectedAction) => expectedAction switch
        {
            WindowControlAction.Focus => observed.Foreground,
            WindowControlAction.Minimize => observed.State == "minimized"
                && !observed.Foreground,
            WindowControlAction.Maximize => observed.State == "maximized",
            WindowControlAction.Restore => observed.State == "normal",
            null => true,
            _ => false,
        };
}

internal sealed record WindowIdentity(
    nint Handle,
    int ProcessId,
    long ProcessCreationTimeUtcTicks,
    string ProcessName,
    DateTimeOffset IssuedAtUtc,
    string? ExecutablePath = null);

internal sealed record WindowBounds(int X, int Y, int Width, int Height);

internal sealed record WindowSnapshot(
    WindowIdentity Identity,
    string State,
    bool Foreground,
    WindowBounds Bounds,
    string? Title = null);

internal sealed record WindowEnumeration(
    IReadOnlyList<WindowSnapshot> Windows,
    int ObservedCount,
    bool Complete);

internal interface IWindowControlPlatform
{
    DateTimeOffset UtcNow { get; }
    WindowSnapshot? FindForegroundWindow();
    WindowEnumeration FindVisibleWindows(string processName, int limit,
        bool byTitle = false, int offset = 0, bool allWindows = false,
        CancellationToken cancellationToken = default);
    WindowSnapshot Observe(WindowIdentity identity);
    bool Execute(WindowIdentity identity, WindowControlAction action);
    bool SetBounds(WindowIdentity identity, WindowBounds bounds);
    bool RequestClose(WindowIdentity identity);
    bool RequestSystemClose(WindowIdentity identity);
    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
}

internal sealed class WindowIdentityChangedException : InvalidOperationException;

internal sealed partial class Win32WindowControlPlatform : IWindowControlPlatform
{
    private const uint CloseMessage = 0x0010;
    private const uint SystemCommandMessage = 0x0112;
    private const int SystemCloseCommand = 0xF060;
    private const int ShowMinimized = 6;
    private const int ShowMaximized = 3;
    private const int Restore = 9;

    public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;

    public WindowSnapshot? FindForegroundWindow()
    {
        nint handle = GetForegroundWindow();
        if (handle == 0 || !IsWindow(handle) || !IsWindowVisible(handle))
        {
            return null;
        }

        _ = GetWindowThreadProcessId(handle, out uint owner);
        if (owner == 0 || owner > int.MaxValue)
        {
            return null;
        }

        using Process process = Process.GetProcessById(checked((int)owner));
        process.Refresh();
        var identity = new WindowIdentity(
            handle,
            process.Id,
            process.StartTime.ToUniversalTime().Ticks,
            process.ProcessName,
            UtcNow);
        return Observe(identity);
    }

    public WindowEnumeration FindVisibleWindows(string processName, int limit,
        bool byTitle = false, int offset = 0, bool allWindows = false,
        CancellationToken cancellationToken = default)
    {
        var result = new List<WindowSnapshot>(limit);
        int observedCount = 0;
        bool complete = true;
        string selector = InstalledApplicationResolver.Normalize(processName);
        EnumWindowsProc callback = (handle, _) =>
        {
            if (cancellationToken.IsCancellationRequested)
                return false;
            if (!IsWindowVisible(handle))
                return true;
            GetWindowThreadProcessId(handle, out uint owner);
            if (owner == 0 || owner > int.MaxValue)
            {
                complete = false;
                return true;
            }
            try
            {
                using Process process = Process.GetProcessById(checked((int)owner));
                string title = ReadWindowTitle(handle);
                bool matches = allWindows || (byTitle
                    ? string.Equals(title.Trim(), processName, StringComparison.OrdinalIgnoreCase)
                        || selector.Length > 0 && WindowsInstalledApplicationPlatform.WindowTitleIdentifiesApplication(
                            InstalledApplicationResolver.Normalize(title), selector)
                    : string.Equals(process.ProcessName, processName, StringComparison.OrdinalIgnoreCase));
                if (!matches)
                    return true;
                var identity = new WindowIdentity(handle, process.Id,
                    process.StartTime.ToUniversalTime().Ticks, process.ProcessName, UtcNow);
                WindowSnapshot snapshot = Observe(identity);
                if (observedCount >= offset && result.Count < limit)
                    result.Add(snapshot);
                observedCount++;
            }
            catch (Exception exception) when (exception is Win32Exception
                or InvalidOperationException or NotSupportedException or ArgumentException)
            {
                // A window or its owner can disappear during enumeration.
                complete = false;
            }
            // Count the rest without retaining another page or issuing handles.
            return true;
        };
        bool enumerated = EnumWindows(callback, nint.Zero);
        int error = Marshal.GetLastPInvokeError();
        cancellationToken.ThrowIfCancellationRequested();
        if (!enumerated)
            throw new Win32Exception(error);
        return new WindowEnumeration(result, observedCount, complete);
    }

    public WindowSnapshot Observe(WindowIdentity identity)
    {
        if (!IsWindow(identity.Handle) || !IsWindowVisible(identity.Handle))
        {
            throw new WindowIdentityChangedException();
        }

        _ = GetWindowThreadProcessId(identity.Handle, out uint owner);
        if (owner != checked((uint)identity.ProcessId))
        {
            throw new WindowIdentityChangedException();
        }

        using Process process = Process.GetProcessById(identity.ProcessId);
        if (process.StartTime.ToUniversalTime().Ticks != identity.ProcessCreationTimeUtcTicks
            || !string.Equals(process.ProcessName, identity.ProcessName,
                StringComparison.OrdinalIgnoreCase)
            || (identity.ExecutablePath is not null
                && !string.Equals(process.MainModule?.FileName, identity.ExecutablePath,
                    StringComparison.OrdinalIgnoreCase)))
        {
            throw new WindowIdentityChangedException();
        }

        string state = IsIconic(identity.Handle)
            ? "minimized"
            : IsZoomed(identity.Handle) ? "maximized" : "normal";
        if (!GetWindowRect(identity.Handle, out NativeRect rectangle))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        return new WindowSnapshot(
            identity,
            state,
            GetForegroundWindow() == identity.Handle,
            new WindowBounds(
                rectangle.Left,
                rectangle.Top,
                checked(rectangle.Right - rectangle.Left),
                checked(rectangle.Bottom - rectangle.Top)),
            ReadWindowTitle(identity.Handle));
    }

    public bool Execute(WindowIdentity identity, WindowControlAction action)
    {
        WindowSnapshot snapshot = Observe(identity);
        return action switch
        {
            WindowControlAction.Focus => ExecuteFocus(snapshot, ShowWindowAsync, SetForegroundWindow),
            WindowControlAction.Minimize => ShowWindowAsync(identity.Handle, ShowMinimized),
            WindowControlAction.Maximize => ShowWindowAsync(identity.Handle, ShowMaximized),
            WindowControlAction.Restore => ShowWindowAsync(identity.Handle, Restore),
            _ => false,
        };
    }

    internal static bool ExecuteFocus(
        WindowSnapshot snapshot,
        Func<nint, int, bool> showWindowAsync,
        Func<nint, bool> setForegroundWindow) =>
        (snapshot.State != "minimized" || showWindowAsync(snapshot.Identity.Handle, Restore))
        && setForegroundWindow(snapshot.Identity.Handle);

    public bool RequestClose(WindowIdentity identity)
    {
        _ = Observe(identity);
        return PostMessage(identity.Handle, CloseMessage, 0, 0);
    }

    public bool RequestSystemClose(WindowIdentity identity)
    {
        _ = Observe(identity);
        return PostMessage(identity.Handle, SystemCommandMessage, SystemCloseCommand, 0);
    }

    public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    public bool SetBounds(WindowIdentity identity, WindowBounds bounds)
    {
        _ = Observe(identity);
        return MoveWindow(
            identity.Handle,
            bounds.X,
            bounds.Y,
            bounds.Width,
            bounds.Height,
            repaint: true);
    }

    private static unsafe string ReadWindowTitle(nint handle)
    {
        const int capacity = 1024;
        char* buffer = stackalloc char[capacity];
        int length = GetWindowText(handle, buffer, capacity);
        return length > 0 ? new string(buffer, 0, length) : string.Empty;
    }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint window, nint lParam);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextW")]
    private static unsafe partial int GetWindowText(nint window, char* text, int capacity);

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeRect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint windowHandle);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint windowHandle);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint windowHandle);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsZoomed(nint windowHandle);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindowAsync(nint windowHandle, int command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint windowHandle);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint windowHandle, out NativeRect rectangle);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool MoveWindow(
        nint windowHandle,
        int x,
        int y,
        int width,
        int height,
        [MarshalAs(UnmanagedType.Bool)] bool repaint);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint windowHandle, out uint processId);

    [LibraryImport("user32.dll", EntryPoint = "PostMessageW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool PostMessage(nint windowHandle, uint message, nint wParam, nint lParam);
}
