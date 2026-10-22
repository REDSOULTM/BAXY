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
    // FT/proveedores goal (review of receipts): Chromium and Electron hide a closing window first and destroy it once
    // its tabs end; a hidden window is watched this many more times for its end before it is told «hidden».
    private const int HiddenSettleAttempts = 10;

    private readonly IWindowControlPlatform _platform;
    private readonly WindowsInstalledApplicationOpenProvider _applications;
    private readonly WindowsWindowControlVerifier _verifier;
    private readonly object _gate = new();
    private readonly Dictionary<string, WindowIdentity> _handles = new(StringComparer.Ordinal);
    private readonly LaunchProvenance _provenance;

    public WindowsWindowControlProvider()
        : this(new Win32WindowControlPlatform(), new WindowsInstalledApplicationOpenProvider(), LaunchProvenance.Shared)
    {
    }

    public WindowsWindowControlProvider(WindowsInstalledApplicationOpenProvider applications)
        : this(new Win32WindowControlPlatform(), applications, LaunchProvenance.Shared)
    {
    }

    internal WindowsWindowControlProvider(IWindowControlPlatform platform)
        : this(platform, new WindowsInstalledApplicationOpenProvider())
    {
    }

    internal WindowsWindowControlProvider(
        IWindowControlPlatform platform,
        WindowsInstalledApplicationOpenProvider applications)
        : this(platform, applications, new LaunchProvenance())
    {
    }

    internal WindowsWindowControlProvider(
        IWindowControlPlatform platform,
        WindowsInstalledApplicationOpenProvider applications,
        LaunchProvenance provenance)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _applications = applications ?? throw new ArgumentNullException(nameof(applications));
        _provenance = provenance ?? throw new ArgumentNullException(nameof(provenance));
        _verifier = new WindowsWindowControlVerifier(platform);
    }

    /// <summary>
    /// The windowId of a window another verified operation already identified (the window app.open verified), so the
    /// window operations can act on it without resolving it again; null when it is not on the desktop now.
    /// </summary>
    public string? IssueFor(nint handle)
    {
        WindowSnapshot? snapshot;
        try
        {
            snapshot = _platform.DesktopWindows().FirstOrDefault(window => window.Identity.Handle == handle);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return null;
        }

        return snapshot is null ? null : Issue(snapshot.Identity);
    }

    public ValueTask<WindowResolveResult> ResolveForegroundAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        WindowSnapshot? snapshot;
        WindowSnapshot? baxyInFront = null;
        try
        {
            snapshot = _platform.FindForegroundWindow();
            // M149 (D71.2, dueño 2026-10-03 «cierra la ventana activa … la ventana en la que yo estoy actuando»):
            // when the person writes to BAXY its own window takes the foreground, but it is not the person's
            // window: theirs is the one they were using right before, the next one down the z-order that a
            // person sees (titled, root owner, not minimized) and that is not BAXY's. With Opera in front and
            // YouTube behind it, that is Opera. Any other foreground (the harness guard Notepad included) stays
            // exactly what it was. Nothing behind BAXY → nothing is named and nothing is acted on.
            if (snapshot is not null && OwnProcessNames.Contains(snapshot.Identity.ProcessName))
            {
                baxyInFront = snapshot;
                snapshot = _platform.DesktopWindowsBehind(baxyInFront.Identity)
                    .FirstOrDefault(static window => window.State != "minimized"
                        && !OwnProcessNames.Contains(window.Identity.ProcessName));
            }
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
        WindowCandidate candidate = WithProvenance(ToCandidate(snapshot, windowId), snapshot.Identity);
        bool verified = baxyInFront is null
            ? candidate.Foreground && _verifier.Verify(snapshot.Identity, candidate, expectedAction: null)
            : !candidate.Foreground && _verifier.Verify(snapshot.Identity, candidate, expectedAction: null)
                && ForegroundIsStill(baxyInFront.Identity);
        if (!verified)
        {
            Revoke(windowId);
            return ValueTask.FromResult(new WindowResolveResult(
                false, false, [], WindowControlErrorCodes.VerificationFailed));
        }

        // M149: «foreground» on window.active is the window the person is acting in (the mind reads it as
        // is_current_window_for_user_interaction); behind BAXY's own window that is the verified one under it.
        if (baxyInFront is not null)
            candidate = candidate with { Foreground = true };
        return ValueTask.FromResult(new WindowResolveResult(true, true, [candidate], null));
    }

    // M149: the person's window was read under BAXY's; it stays theirs only while BAXY still holds the front.
    private bool ForegroundIsStill(WindowIdentity front)
    {
        try
        {
            return _platform.FindForegroundWindow() is { } now && now.Identity.Handle == front.Handle
                && now.Identity.ProcessId == front.ProcessId;
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException
            or NotSupportedException)
        {
            return false;
        }
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
            WindowCandidate candidate = WithProvenance(
                WithStanding(ToCandidate(snapshot, windowId), snapshot.Identity), snapshot.Identity);
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
            var resolution = await _applications.ResolveApplicationWindowsAsync(
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
                    _platform.UtcNow, Path.GetFullPath(observation.ExecutablePath),
                    resolution.AppUserModelId);
                WindowSnapshot snapshot = _platform.Observe(identity);
                string windowId = Issue(identity);
                issued.Add(windowId);
                WindowCandidate candidate = WithProvenance(
                    WithStanding(ToCandidate(snapshot, windowId), identity), identity);
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

    // Renew al máximo (auditoría de flujos): the application's processes running with no visible window.
    public ValueTask<IReadOnlyList<int>> BackgroundProcessesAsync(
        string applicationName,
        CancellationToken cancellationToken) =>
        _applications.ResolveBackgroundProcessesAsync(applicationName, cancellationToken);

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
        // Ronda final: a window already minimized, maximized, restored or in front is the state reached (changed:false),
        // never an action this call made.
        if (action is WindowControlAction.Minimize or WindowControlAction.Maximize or WindowControlAction.Restore
                or WindowControlAction.Focus
            && WindowsWindowControlVerifier.MatchesExpectedAction(before, action))
        {
            return new WindowActionResult(true, true, ToCandidate(before, Issue(before.Identity)), null,
                AlreadyReached: true);
        }

        if (!_platform.Execute(before.Identity, action))
        {
            // Round A: focusing a minimized window restores it before bringing it to the front, and a refused front
            // may come after that restore.
            bool mayHaveChanged = action == WindowControlAction.Focus && before.State == "minimized";
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.ActionFailed,
                EffectMayHaveOccurred: mayHaveChanged,
                StateAfter: mayHaveChanged ? ReadStateAfter(before.Identity, action) : null);
        }

        WindowSnapshot? lastRead = null;
        bool restoredAgain = false;
        for (int attempt = 0; attempt < StateVerificationAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            WindowSnapshot after;
            try
            {
                after = _platform.Observe(before.Identity);
                // Renew al máximo (auditoría de flujos): a window minimized from maximized comes back maximized from its
                // first restore (WPF_RESTORETOMAXIMIZED); the restore is asked once more for its normal size.
                if (action == WindowControlAction.Restore && !restoredAgain && before.State == "minimized"
                    && after.State == "maximized")
                {
                    restoredAgain = true;
                    _ = _platform.Execute(before.Identity, WindowControlAction.Restore);
                    after = _platform.Observe(before.Identity);
                }
            }
            catch (WindowIdentityChangedException changed)
            {
                // Renew al máximo (8.3): a window gone (or hidden) by the read is the state after, not a failed read.
                return new WindowActionResult(
                    false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true,
                    StateAfter: GoneAfter(changed, requestedStateReached: false));
            }
            catch (Exception exception) when (exception is Win32Exception
                or InvalidOperationException)
            {
                return new WindowActionResult(
                    false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true);
            }

            lastRead = after;
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

        // Renew al máximo (8.3): the last read, when it showed another state, is the state after; one that showed the
        // asked state and was not confirmed settles nothing.
        return new WindowActionResult(
            false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true,
            StateAfter: lastRead is not null && !WindowsWindowControlVerifier.MatchesExpectedAction(lastRead, action)
                ? PresentAfter(lastRead, requestedStateReached: false)
                : null);
    }

    // Renew al máximo (8.3): one read of the window after an ambiguous failure; nothing when it cannot be read.
    private WindowStateAfter? ReadStateAfter(WindowIdentity identity, WindowControlAction? action)
    {
        try
        {
            WindowSnapshot after = _platform.Observe(identity);
            return PresentAfter(
                after, action is { } asked && WindowsWindowControlVerifier.MatchesExpectedAction(after, asked));
        }
        catch (WindowIdentityChangedException changed)
        {
            return GoneAfter(changed, requestedStateReached: false);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return null;
        }
    }

    private static WindowStateAfter PresentAfter(WindowSnapshot after, bool requestedStateReached) => new(
        Present: true, Hidden: false, after.State, after.Foreground,
        after.Bounds.X, after.Bounds.Y, after.Bounds.Width, after.Bounds.Height, requestedStateReached);

    private static WindowStateAfter GoneAfter(WindowIdentityChangedException changed, bool requestedStateReached) => new(
        Present: false, changed.Hidden, State: null, Foreground: null, X: null, Y: null, Width: null, Height: null,
        requestedStateReached);

    // Auditoría final (regla 3): a desktop window that is there and could not be read is not among «all» of them: the
    // result carries how many, and the handler says none of «all minimized» or «all closed».
    public async ValueTask<WindowMinimizeAllResult> MinimizeAllAsync(CancellationToken cancellationToken)
    {
        WindowMinimizeAllResult result = await MinimizeAllReadAsync(cancellationToken).ConfigureAwait(false);
        int unread = _platform.UnreadDesktopWindows;
        int cloaked = _platform.CloakedDesktopWindows;
        return result.Succeeded ? result with { Unread = unread, Cloaked = cloaked } : result;
    }

    public async ValueTask<WindowCloseAllResult> CloseAllAsync(CancellationToken cancellationToken)
    {
        WindowCloseAllResult result = await CloseAllReadAsync(cancellationToken).ConfigureAwait(false);
        int unread = _platform.UnreadDesktopWindows;
        int cloaked = _platform.CloakedDesktopWindows;
        return result.Succeeded ? result with { Unread = unread, Cloaked = cloaked } : result;
    }

    private async ValueTask<WindowMinimizeAllResult> MinimizeAllReadAsync(CancellationToken cancellationToken)
    {
        // MINALL1687 «minimizá todas las ventanas»: every desktop window that is
        // not already minimized gets the minimize command, and the result is
        // verified by re-observing each one until it is iconic. Nothing is
        // closed; a window that refuses to minimize keeps the effect unverified.
        cancellationToken.ThrowIfCancellationRequested();
        IReadOnlyList<WindowSnapshot> desktop;
        try
        {
            desktop = _platform.DesktopWindows();
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException or NotSupportedException)
        {
            return new WindowMinimizeAllResult(false, false, 0, 0, 0, WindowControlErrorCodes.InventoryFailed);
        }

        // Uso real (tandas 4–7, the official window): «abre el homescreen» minimized BAXY's own window with the
        // rest; its reply was written into a minimized window and the person saw nothing. Showing the desktop
        // leaves the companion the person is talking to on screen.
        List<WindowSnapshot> targets = desktop
            .Where(static window => window.State != "minimized" && !OwnProcessNames.Contains(window.Identity.ProcessName))
            .ToList();
        if (targets.Count == 0)
        {
            return new WindowMinimizeAllResult(true, true, desktop.Count, 0, 0, null);
        }

        foreach (WindowSnapshot target in targets)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                _ = _platform.Execute(target.Identity, WindowControlAction.Minimize);
            }
            catch (Exception exception) when (exception is Win32Exception
                or InvalidOperationException or WindowIdentityChangedException)
            {
                // A window that vanished meanwhile is not visible any more.
            }
        }

        int remaining = targets.Count;
        int minimizedSeen = 0;
        int gone = 0;
        for (int attempt = 0; attempt < StateVerificationAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            remaining = 0;
            minimizedSeen = 0;
            gone = 0;
            foreach (WindowSnapshot target in targets)
            {
                try
                {
                    if (_platform.Observe(target.Identity).State != "minimized")
                        remaining++;
                    else
                        minimizedSeen++;
                }
                catch (Exception exception) when (exception is Win32Exception
                    or InvalidOperationException or WindowIdentityChangedException)
                {
                    // Gone windows are not visible windows, nor windows this call minimized (ronda final).
                    gone++;
                }
            }
            if (remaining == 0)
            {
                return new WindowMinimizeAllResult(true, true, desktop.Count, minimizedSeen, 0, null, Gone: gone);
            }
            if (attempt + 1 < StateVerificationAttempts)
            {
                await _platform.DelayAsync(VerificationDelay, cancellationToken).ConfigureAwait(false);
            }
        }

        return new WindowMinimizeAllResult(
            true, false, desktop.Count, minimizedSeen, remaining, WindowControlErrorCodes.VerificationFailed,
            EffectMayHaveOccurred: true, Gone: gone);
    }

    // CLOSEALL1733 «cerrame todo»: every desktop window is asked to close the way
    // a person would (WM_CLOSE, then the system-menu close) except this product's
    // own; a window that stays — an application asking whether to save, a client
    // that refuses — is counted as remaining and never forced, so no document is
    // lost. Auditoría final G1: no application is spared by its name in code.
    // The product's own windows: the App runs as «Baxy» (Baxy.exe), and «Baxy.App» in development hosts.
    // Also what tells an opening that the request was written in BAXY's own window (ForegroundHandBack.PersonWorkingIn).
    internal static readonly HashSet<string> OwnProcessNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Baxy", "Baxy.App", "baxy-core",
    };

    /// <summary>
    /// Renew al máximo (B-CU-2): whether <paramref name="processId"/> is the product's own: this process (the Core,
    /// which shows no window) or one whose executable is named as the product's (<see cref="OwnProcessNames"/>: BAXY's
    /// chat is Baxy.exe's window). <paramref name="imageOf"/> reads a process's executable (tests give it).
    /// </summary>
    internal static bool ProductProcess(int processId, Func<int, string?>? imageOf = null) =>
        processId == Environment.ProcessId
        || (processId > 0
            && (imageOf ?? WindowsInstalledApplicationPlatform.ExecutableImagePath)(processId) is { } path
            && OwnProcessNames.Contains(Path.GetFileNameWithoutExtension(path)));

    private async ValueTask<WindowCloseAllResult> CloseAllReadAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        IReadOnlyList<WindowSnapshot> desktop;
        try
        {
            desktop = _platform.DesktopWindows();
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException or NotSupportedException)
        {
            return new WindowCloseAllResult(false, false, 0, 0, 0, 0, [], [], WindowControlErrorCodes.InventoryFailed);
        }

        // Renew al máximo (lote 4, d): «never forces» holds only where a close can be answered. A console's close ends
        // the processes attached to it without asking, and a terminal or an editor is where the developer's agent
        // lives: every window no act reaches (VisibleControlSurface.ProtectedFrom, BAXY's own included) is kept, and
        // the result says how many and which.
        static bool Spared(WindowSnapshot window) => External.VisibleControlSurface.ProtectedFrom(window.Identity.ProcessName, null);
        List<WindowSnapshot> kept = desktop.Where(Spared).ToList();
        List<WindowSnapshot> targets = desktop.Where(static window => !Spared(window)).ToList();
        List<string> keptNames = kept.Select(static window => window.Identity.ProcessName).Distinct(StringComparer.OrdinalIgnoreCase).Order(StringComparer.OrdinalIgnoreCase).ToList();
        List<WindowSnapshot> spared = kept.Where(static window => !OwnProcessNames.Contains(window.Identity.ProcessName)).ToList();
        List<string> sparedNames = spared.Select(static window => window.Identity.ProcessName).Distinct(StringComparer.OrdinalIgnoreCase).Order(StringComparer.OrdinalIgnoreCase).ToList();
        if (targets.Count == 0)
        {
            return new WindowCloseAllResult(true, true, desktop.Count, 0, 0, kept.Count, keptNames, [], null,
                ProtectedKept: spared.Count, ProtectedProcesses: sparedNames);
        }

        // Auditoría D7 and final G2: only a window BAXY's close reached (Windows took the request) is BAXY's to count
        // as closed; one that ended without being asked (gone before, a request Windows refused) is already gone.
        var asked = new HashSet<nint>();
        foreach (WindowSnapshot target in targets)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                if (_platform.RequestClose(target.Identity))
                    _ = asked.Add(target.Identity.Handle);
            }
            catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
            {
                // Not asked (gone or changed before the request, or refused): never counted as closed by BAXY.
            }
        }

        List<WindowSnapshot> remaining = await RemainingOpenAsync(targets, PrimaryCloseVerificationAttempts, cancellationToken).ConfigureAwait(false);
        if (remaining.Count > 0)
        {
            foreach (WindowSnapshot target in remaining)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    _ = _platform.Observe(target.Identity);
                    if (_platform.RequestSystemClose(target.Identity))
                        _ = asked.Add(target.Identity.Handle);
                }
                catch (Exception exception) when (exception is Win32Exception
                    or InvalidOperationException or WindowIdentityChangedException)
                {
                    // Gone or changed: nothing more to ask.
                }
            }
            remaining = await RemainingOpenAsync(remaining, FallbackCloseVerificationAttempts, cancellationToken).ConfigureAwait(false);
        }

        List<string> remainingNames = remaining.Select(static window => window.Identity.ProcessName).Distinct(StringComparer.OrdinalIgnoreCase).Order(StringComparer.OrdinalIgnoreCase).ToList();
        List<WindowSnapshot> ended = targets.Except(remaining).ToList();
        int hidden = ended.Count(window => _verifier.Fate(window.Identity) == WindowFate.Hidden);
        int alreadyGone = ended.Count(window => !asked.Contains(window.Identity.Handle)
            && _verifier.Fate(window.Identity) != WindowFate.Hidden);
        return new WindowCloseAllResult(
            true, true, desktop.Count, ended.Count - hidden - alreadyGone, remaining.Count, kept.Count, keptNames, remainingNames,
            null, hidden, alreadyGone, ProtectedKept: spared.Count, ProtectedProcesses: sparedNames);
    }

    private async ValueTask<List<WindowSnapshot>> RemainingOpenAsync(
        IReadOnlyList<WindowSnapshot> targets,
        int attempts,
        CancellationToken cancellationToken)
    {
        List<WindowSnapshot> open = targets.ToList();
        for (int attempt = 0; attempt < attempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            open = open.Where(window => _verifier.Fate(window.Identity) == WindowFate.Present).ToList();
            if (open.Count == 0 || attempt + 1 >= attempts)
            {
                break;
            }
            await _platform.DelayAsync(VerificationDelay, cancellationToken).ConfigureAwait(false);
        }
        return open;
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
        // Ronda final: a window already at those bounds, read before, is the state reached (changed:false); nothing sent.
        if (before.Bounds == expected)
        {
            return ValueTask.FromResult(new WindowActionResult(
                true, true, ToCandidate(before, Issue(before.Identity)), null, AlreadyReached: true));
        }

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
        catch (WindowIdentityChangedException changed)
        {
            // Renew al máximo (8.3): a window gone (or hidden) by the read is the state after.
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true,
                StateAfter: GoneAfter(changed, requestedStateReached: false)));
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException)
        {
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true));
        }
        if (after.Bounds != expected)
        {
            // Renew al máximo (8.3): the bounds the read found are the state after, never dropped.
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true,
                StateAfter: PresentAfter(after, requestedStateReached: false)));
        }

        string refreshedId = Issue(after.Identity);
        WindowCandidate candidate = ToCandidate(after, refreshedId);
        if (!_verifier.Verify(after.Identity, candidate, expectedAction: null))
        {
            Revoke(refreshedId);
            return ValueTask.FromResult(new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true));
        }
        return ValueTask.FromResult(new WindowActionResult(true, true, candidate, null));
    }

    // Renew al máximo (auditoría de flujos): a window closed or changed while it is placed (each act reads it first, for
    // seconds when it leaves a full screen) threw out of the provider and stopped the core; the placement ends saying so.
    public async ValueTask<WindowActionResult> SnapAsync(
        string windowId,
        string side,
        CancellationToken cancellationToken)
    {
        try
        {
            return await PlaceOnHalfAsync(windowId, side, cancellationToken).ConfigureAwait(false);
        }
        catch (WindowIdentityChangedException)
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.WindowIdentityChanged, EffectMayHaveOccurred: true);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException or ArgumentException)
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true);
        }
    }

    private async ValueTask<WindowActionResult> PlaceOnHalfAsync(
        string windowId,
        string side,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        bool left = string.Equals(side, "left", StringComparison.Ordinal);
        if (!left && !string.Equals(side, "right", StringComparison.Ordinal))
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InvalidSelector);
        }
        if (!TryConsume(windowId, out WindowIdentity? identity))
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InvalidOrExpiredWindowId);
        }

        WindowSnapshot before;
        WindowBounds? workArea;
        try
        {
            before = _platform.Observe(identity!);
            workArea = _platform.WorkArea(before.Identity);
        }
        catch (WindowIdentityChangedException)
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.WindowIdentityChanged);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InventoryFailed);
        }
        if (workArea is null || workArea.Width < 2 || workArea.Height < 1)
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.InventoryFailed);
        }

        // Ronda final: a normal window already on that half, read before, is the state reached (changed:false).
        int alreadyHalf = workArea.Width / 2;
        var alreadyExpected = new WindowBounds(
            left ? workArea.X : workArea.X + alreadyHalf,
            workArea.Y,
            left ? alreadyHalf : workArea.Width - alreadyHalf,
            workArea.Height);
        if (string.Equals(before.State, "normal", StringComparison.Ordinal) && before.Bounds == alreadyExpected)
        {
            return new WindowActionResult(
                true, true, ToCandidate(before, Issue(before.Identity)), null, AlreadyReached: true);
        }

        // A maximized or minimized window keeps no bounds of its own: it is
        // restored first, the way the desktop does before docking it.
        bool restored = false;
        if (!string.Equals(before.State, "normal", StringComparison.Ordinal))
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!_platform.Execute(before.Identity, WindowControlAction.Restore))
            {
                return new WindowActionResult(
                    false, false, null, WindowControlErrorCodes.ActionFailed);
            }
            restored = true;
            await _platform.DelayAsync(VerificationDelay, cancellationToken)
                .ConfigureAwait(false);
            // Renew al máximo (auditoría de flujos): one minimized from maximized came back maximized; restored once more.
            if (before.State == "minimized" && _platform.Observe(before.Identity).State == "maximized")
            {
                _ = _platform.Execute(before.Identity, WindowControlAction.Restore);
                await _platform.DelayAsync(VerificationDelay, cancellationToken).ConfigureAwait(false);
            }
        }

        int half = workArea.Width / 2;
        var expected = new WindowBounds(
            left ? workArea.X : workArea.X + half,
            workArea.Y,
            left ? half : workArea.Width - half,
            workArea.Height);
        cancellationToken.ThrowIfCancellationRequested();
        if (!_platform.SetBounds(before.Identity, expected))
        {
            // Round A: a window restored for the placement stays restored.
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.ActionFailed, EffectMayHaveOccurred: restored);
        }

        (WindowSnapshot? placed, bool larger) = await ObserveSnapAsync(
                before.Identity, expected, acceptLarger: true, workArea, cancellationToken)
            .ConfigureAwait(false);
        // BAXY Renew cu (C13 en el PC): a window in full screen (a video, a browser's F11) keeps its whole monitor and takes
        // no size. It is asked to leave by its own keys (Esc, then F11), and placed again once it did; one that stays in
        // full screen is left as it was, and said (window_size_not_taken).
        if (placed is null && _platform.FullScreen(before.Identity))
        {
            ushort? leftBy = await LeaveFullScreenAsync(before.Identity, cancellationToken).ConfigureAwait(false);
            if (leftBy is null)
            {
                return new WindowActionResult(
                    false, false, null, WindowControlErrorCodes.WindowSizeNotTaken, EffectMayHaveOccurred: false);
            }

            WindowSnapshot now = _platform.Observe(before.Identity);
            if (!string.Equals(now.State, "normal", StringComparison.Ordinal))
            {
                _ = _platform.Execute(before.Identity, WindowControlAction.Restore);
                await _platform.DelayAsync(VerificationDelay, cancellationToken).ConfigureAwait(false);
            }

            if (_platform.SetBounds(before.Identity, expected))
            {
                (placed, larger) = await ObserveSnapAsync(
                        before.Identity, expected, acceptLarger: true, workArea, cancellationToken)
                    .ConfigureAwait(false);
            }

            if (placed is null)
            {
                // Back to full screen when its own key toggles it (F11); out of it otherwise, and said.
                bool back = leftBy == FullScreenKey && _platform.PostKey(before.Identity, FullScreenKey, FullScreenScan);
                return new WindowActionResult(
                    false, false, null, WindowControlErrorCodes.WindowSizeNotTaken, EffectMayHaveOccurred: !back);
            }
        }

        // BAXY Renew cu (C13 en el PC): a window just restored from maximized may take its restored bounds after the
        // move (a browser on a second screen stayed as wide as the whole screen): the move is asked once more.
        if (placed is null && restored)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!_platform.SetBounds(before.Identity, expected))
            {
                return new WindowActionResult(
                    false, false, null, WindowControlErrorCodes.ActionFailed, EffectMayHaveOccurred: true);
            }

            (placed, larger) = await ObserveSnapAsync(
                    before.Identity, expected, acceptLarger: true, workArea, cancellationToken)
                .ConfigureAwait(false);
            if (placed is null)
            {
                // It took neither move (a browser in full screen keeps the whole screen): put back as it was, and said.
                bool back = string.Equals(before.State, "maximized", StringComparison.Ordinal)
                    && _platform.Execute(before.Identity, WindowControlAction.Maximize);
                return new WindowActionResult(
                    false, false, null, WindowControlErrorCodes.WindowSizeNotTaken, EffectMayHaveOccurred: !back);
            }
        }

        if (placed is null)
        {
            return new WindowActionResult(
                false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true);
        }

        WindowRequestedSize? largerThanRequested = null;
        if (larger)
        {
            // M159 (DEV-I v4w I-s048 «pasame la ventana de spotify a la derecha»): Spotify's
            // minimum width (814) is larger than half of this 1536 work area. Windows keeps
            // the asked position and clamps the size, so the window ended at x 768, width
            // 814, past the right edge, and the exact-half check answered «la verificación
            // del lado derecho falló» on every try. The window is put flush against the
            // asked edge at the size it imposes, and that placement is what is verified:
            // on the edge, inside the work area, with the window's own larger size.
            largerThanRequested = new WindowRequestedSize(expected.Width, expected.Height);
            var flush = new WindowBounds(
                left ? workArea.X : workArea.X + workArea.Width - placed.Bounds.Width,
                expected.Y,
                placed.Bounds.Width,
                placed.Bounds.Height);
            if (placed.Bounds != flush)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!_platform.SetBounds(before.Identity, flush))
                {
                    // The first placement already moved it.
                    return new WindowActionResult(
                        false, false, null, WindowControlErrorCodes.ActionFailed, EffectMayHaveOccurred: true);
                }
                (placed, _) = await ObserveSnapAsync(
                        before.Identity, flush, acceptLarger: false, workArea, cancellationToken)
                    .ConfigureAwait(false);
                if (placed is null)
                {
                    return new WindowActionResult(
                        false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true);
                }
            }
        }

        string refreshedId = Issue(placed.Identity);
        WindowCandidate candidate = ToCandidate(placed, refreshedId);
        if (_verifier.Verify(placed.Identity, candidate, expectedAction: null))
        {
            return new WindowActionResult(true, true, candidate, null, largerThanRequested);
        }
        Revoke(refreshedId);
        return new WindowActionResult(
            false, false, null, WindowControlErrorCodes.VerificationFailed, EffectMayHaveOccurred: true);
    }

    // BAXY Renew cu (C13 en el PC): the keys a full screen leaves by, each posted once and read back: Esc (a video in full
    // screen), then F11 (a browser's full screen). The key that worked, or null when the window stayed in full screen.
    private const ushort LeaveVideoKey = 0x1B;
    private const ushort LeaveVideoScan = 0x01;
    private const ushort FullScreenKey = 0x7A;
    private const ushort FullScreenScan = 0x57;
    private static readonly TimeSpan FullScreenLeaveDelay = TimeSpan.FromMilliseconds(900);

    private async ValueTask<ushort?> LeaveFullScreenAsync(WindowIdentity identity, CancellationToken cancellationToken)
    {
        foreach ((ushort key, ushort scan) in new[] { (LeaveVideoKey, LeaveVideoScan), (FullScreenKey, FullScreenScan) })
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!_platform.PostKey(identity, key, scan))
            {
                continue;
            }

            await _platform.DelayAsync(FullScreenLeaveDelay, cancellationToken).ConfigureAwait(false);
            if (!_platform.FullScreen(identity))
            {
                return key;
            }
        }

        return null;
    }

    // The placement read back: the exact target, or (acceptLarger) the window held at a
    // size larger than the target that it imposes itself. Null when neither settles.
    private async ValueTask<(WindowSnapshot? Window, bool Larger)> ObserveSnapAsync(
        WindowIdentity identity,
        WindowBounds target,
        bool acceptLarger,
        WindowBounds workArea,
        CancellationToken cancellationToken)
    {
        WindowBounds? held = null;
        for (int attempt = 0; attempt < StateVerificationAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            WindowSnapshot after;
            try
            {
                after = _platform.Observe(identity);
            }
            catch (Exception exception) when (exception is Win32Exception
                or InvalidOperationException
                or WindowIdentityChangedException)
            {
                return (null, false);
            }
            bool normal = string.Equals(after.State, "normal", StringComparison.Ordinal);
            if (normal && after.Bounds == target)
            {
                return (after, false);
            }
            if (acceptLarger && normal && KeepsLargerMinimum(after.Bounds, target, workArea))
            {
                // M159: the same larger bounds on two reads, one delay apart: the window
                // settled there; a read taken before the move had landed is not trusted.
                if (after.Bounds == held)
                {
                    return (after, true);
                }
                held = after.Bounds;
            }
            else
            {
                held = null;
            }
            if (attempt + 1 < StateVerificationAttempts)
            {
                await _platform.DelayAsync(VerificationDelay, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return (null, false);
    }

    // M159: the window refused the asked size only by being larger (its minimum), never
    // smaller; that size still fits the work area; it kept the asked top edge and either
    // the asked near edge (Windows clamps the size, not the position) or the asked far
    // edge (the window pulled itself back onto the screen).
    internal static bool KeepsLargerMinimum(
        WindowBounds observed,
        WindowBounds requested,
        WindowBounds workArea) =>
        observed.Width >= requested.Width
        && observed.Height >= requested.Height
        && (observed.Width > requested.Width || observed.Height > requested.Height)
        // BAXY Renew cu (C13 en el PC): as wide as the whole work area is no minimum of the window's own: it was not
        // resized at all (restored to its whole screen), never «it does not fit in half».
        && observed.Width < workArea.Width
        && observed.Height <= workArea.Height
        && observed.Y == requested.Y
        && (observed.X == requested.X
            || observed.X + observed.Width == requested.X + requested.Width);

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

        string? title;
        try
        {
            title = _platform.Observe(identity!).Title;
        }
        catch (WindowIdentityChangedException changed)
        {
            // FT/proveedores goal (review of receipts): gone (or hidden) before BAXY touched it, as at RequestClose
            // (Auditoría D7): an application's second frame ends with the first one's close, and that was a failure
            // (window_identity_changed) of an app.close that closed the whole application; app.restart never reopened.
            return Ended(identity!, null, changed.Hidden ? WindowCloseOutcomes.Hidden : WindowCloseOutcomes.AlreadyGone);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return new WindowCloseResult(false, false, null, WindowControlErrorCodes.InventoryFailed);
        }

        // v3 r22 uso real: the dialogs the window already owned before the close; a new one after it is the
        // application asking something of its own (whether to save), which BAXY never answers.
        IReadOnlySet<nint> dialogsBefore = OwnedDialogs(identity!);

        bool primaryAccepted;
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            primaryAccepted = _platform.RequestClose(identity!);
        }
        catch (WindowIdentityChangedException changed)
        {
            // Auditoría D7: gone (or hidden) before BAXY's close reached it: never «closed by BAXY».
            return Ended(identity!, title, changed.Hidden ? WindowCloseOutcomes.Hidden : WindowCloseOutcomes.AlreadyGone);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return new WindowCloseResult(
                false, false, identity!.ProcessId, WindowControlErrorCodes.ActionFailed);
        }

        WindowFate primaryFate = primaryAccepted
            ? await WaitForClosedAsync(identity!, PrimaryCloseVerificationAttempts, cancellationToken).ConfigureAwait(false)
            : WindowFate.Present;
        if (primaryFate != WindowFate.Present)
        {
            return Ended(identity!, title, OutcomeOf(primaryFate));
        }

        if (primaryAccepted && AskedOnClose(identity!, dialogsBefore))
        {
            return Prompted(identity!);
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
        catch (WindowIdentityChangedException changed)
        {
            // Gone after BAXY's close was sent: closed by it; gone with no close sent: it was not BAXY's doing.
            return Ended(identity!, title, changed.Hidden ? WindowCloseOutcomes.Hidden
                : primaryAccepted ? WindowCloseOutcomes.Closed : WindowCloseOutcomes.AlreadyGone);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            fallbackAccepted = false;
        }

        WindowFate fallbackFate = fallbackAccepted
            ? await WaitForClosedAsync(identity!, FallbackCloseVerificationAttempts, cancellationToken).ConfigureAwait(false)
            : WindowFate.Present;
        if (fallbackFate != WindowFate.Present)
        {
            return Ended(identity!, title, OutcomeOf(fallbackFate));
        }

        if (fallbackAccepted && AskedOnClose(identity!, dialogsBefore))
        {
            return Prompted(identity!);
        }

        // Round A: a close Windows took (WM_CLOSE or the system-menu close) and a window still there: the application
        // got the request and may act on it later; it was a clean failure. Renew al máximo (8.3): one more read says
        // whether it is still there (gone by then is what was asked; hidden, it still exists).
        bool closeTaken = primaryAccepted || fallbackAccepted;
        WindowStateAfter? stateAfter = closeTaken ? ReadStateAfter(identity!, action: null) : null;
        return new WindowCloseResult(
            false,
            false,
            identity!.ProcessId,
            closeTaken
                ? WindowControlErrorCodes.VerificationFailed
                : WindowControlErrorCodes.ActionFailed,
            EffectMayHaveOccurred: closeTaken,
            StateAfter: stateAfter is { Present: false, Hidden: false }
                ? stateAfter with { RequestedStateReached = true }
                : stateAfter);
    }

    private static WindowCloseResult Ended(WindowIdentity identity, string? title, string outcome) =>
        new(true, true, identity.ProcessId, null, Title: title, Outcome: outcome);

    private static string OutcomeOf(WindowFate fate) =>
        fate == WindowFate.Hidden ? WindowCloseOutcomes.Hidden : WindowCloseOutcomes.Closed;

    private static WindowCloseResult Prompted(WindowIdentity identity) =>
        new(false, true, identity.ProcessId, WindowControlErrorCodes.ClosePrompted, ClosePrompted: true);

    private HashSet<nint> OwnedDialogs(WindowIdentity identity)
    {
        try
        {
            return _platform.OwnedDialogs(identity).ToHashSet();
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return new HashSet<nint>();
        }
    }

    // The window is still there (the close was not verified) and now owns a visible dialog it did not own before.
    private bool AskedOnClose(WindowIdentity identity, IReadOnlySet<nint> before)
    {
        try
        {
            _ = _platform.Observe(identity);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return false;
        }

        return OwnedDialogs(identity).Any(dialog => !before.Contains(dialog));
    }

    // What became of the window within the attempts: gone, hidden, or still there (Present).
    private async ValueTask<WindowFate> WaitForClosedAsync(
        WindowIdentity identity,
        int attempts,
        CancellationToken cancellationToken)
    {
        for (int attempt = 0; attempt < attempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            WindowFate fate = _verifier.Fate(identity);
            for (int settle = 0; fate == WindowFate.Hidden && settle < HiddenSettleAttempts; settle++)
            {
                await _platform.DelayAsync(VerificationDelay, cancellationToken).ConfigureAwait(false);
                WindowFate later = _verifier.Fate(identity);
                if (later == WindowFate.Present)
                    break;
                fate = later;
            }

            if (fate != WindowFate.Present)
            {
                return fate;
            }

            if (attempt + 1 < attempts)
            {
                await _platform.DelayAsync(VerificationDelay, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return WindowFate.Present;
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

    /// <summary>
    /// v3 r6 lectores (t2-r4 c04-5 «cierra configuración» pidió confirmación): whether the window an id names holds no
    /// document of the person, read without consuming the id. Its application is the catalog identity it was resolved
    /// from or its executable, looked up in <see cref="DocumentlessApplications"/>; an unknown, expired or malformed id
    /// holds one (fail-closed).
    /// v3 r22 uso real (t3-c18 «ya ciérrala» sobre la Calculadora que BAXY abrió y sólo clicó; t4-c03 «ya cierra
    /// discord»): a window of an application whose content lives in the person's account (data «accountBacked»), or
    /// a window of a process a verified app.open of BAXY launched in this session and BAXY never wrote into
    /// (<see cref="LaunchProvenance"/>), holds nothing of the person either. An identity listed as never closing
    /// without asking (data «neverWithoutAsking») always holds one.
    /// </summary>
    public bool HoldsNoDocument(string windowId)
    {
        if (string.IsNullOrEmpty(windowId) || windowId.Length != 36
            || !windowId.StartsWith("win_", StringComparison.Ordinal))
        {
            return false;
        }

        WindowIdentity? identity;
        lock (_gate)
        {
            RemoveExpired();
            if (!_handles.TryGetValue(windowId, out identity))
            {
                return false;
            }
        }

        if (DocumentlessApplications.NeverWithoutAsking(identity.AppUserModelId, identity.ExecutablePath))
        {
            return false;
        }

        // v3 r22 revisión (la persona en plena reunión pide cerrar la app): an application capturing the microphone
        // is in a call or a recording; closing its window may leave it, and opening the application again does not
        // bring it back.
        if (CapturesMicrophone(identity))
        {
            return false;
        }

        return DocumentlessApplications.Contains(identity.AppUserModelId, identity.ExecutablePath)
            || _provenance.LaunchedAndUnwritten(
                identity.Handle, identity.ProcessId, identity.ProcessCreationTimeUtcTicks);
    }

    private bool CapturesMicrophone(WindowIdentity identity)
    {
        try
        {
            return _platform.CapturesMicrophone(identity);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
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

    // Ronda 22 (revisión 1): a resolve publishes where each window stands (z rank, topmost, its monitor's work
    // area) so the person's frame is chosen from the desktop itself, never from the order a read listed it in.
    private WindowCandidate WithStanding(WindowCandidate candidate, WindowIdentity identity)
    {
        WindowStanding? standing;
        try
        {
            standing = _platform.Standing(identity);
        }
        catch (Exception exception) when (exception is Win32Exception
            or InvalidOperationException
            or NotSupportedException)
        {
            standing = null;
        }

        return standing is null
            ? candidate
            : candidate with
            {
                ZOrder = standing.WindowsAbove,
                Topmost = standing.Topmost,
                WorkAreaWidth = standing.WorkArea?.Width,
                WorkAreaHeight = standing.WorkArea?.Height,
            };
    }

    // BAXY Renew al máximo, F002 («¿abriste Spotify?» sobre el Spotify de la persona → «Sí»): a read that tells which
    // windows are open says beside each whether BAXY launched it in this run, as a fact.
    private WindowCandidate WithProvenance(WindowCandidate candidate, WindowIdentity identity) =>
        candidate with
        {
            OpenedByBaxy = _provenance.Launched(
                identity.Handle, identity.ProcessId, identity.ProcessCreationTimeUtcTicks),
        };

    private static WindowCandidate ToCandidate(WindowSnapshot snapshot, string id) =>
        new(id, snapshot.Identity.ProcessId, snapshot.Identity.ProcessName,
            snapshot.State, snapshot.Foreground, snapshot.Bounds.X, snapshot.Bounds.Y,
            snapshot.Bounds.Width, snapshot.Bounds.Height, snapshot.Title, snapshot.Owned);
}

// Auditoría D7: what became of a window: still there, gone, or hidden (it still exists, invisible).
internal enum WindowFate
{
    Present,
    Gone,
    Hidden,
}

internal sealed class WindowsWindowControlVerifier(IWindowControlPlatform platform)
{
    public WindowFate Fate(WindowIdentity identity)
    {
        try
        {
            _ = platform.Observe(identity);
            return WindowFate.Present;
        }
        catch (WindowIdentityChangedException changed)
        {
            return changed.Hidden ? WindowFate.Hidden : WindowFate.Gone;
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            return WindowFate.Present;
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
    string? ExecutablePath = null,
    string? AppUserModelId = null);

internal sealed record WindowBounds(int X, int Y, int Width, int Height);

internal sealed record WindowSnapshot(
    WindowIdentity Identity,
    string State,
    bool Foreground,
    WindowBounds Bounds,
    string? Title = null,
    bool Owned = false);

// Ronda 22 (revisión 1): the top-level windows above this one in the desktop's z-order, WS_EX_TOPMOST, and the work
// area of the monitor that shows it.
internal sealed record WindowStanding(int WindowsAbove, bool Topmost, WindowBounds? WorkArea);

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
    // MINALL1687: the windows a person sees on the desktop (visible, not cloaked,
    // not a tool window, root owner, titled), excluding the shell and this process.
    IReadOnlyList<WindowSnapshot> DesktopWindows() => [];
    // How many windows the last DesktopWindows() saw alive and visible but could not read (their process).
    int UnreadDesktopWindows => 0;
    // Ronda final 11: how many titled windows the last DesktopWindows() left out because DWM cloaks them (another
    // virtual desktop, a suspended app): not on screen, not touched, and never among «all».
    int CloakedDesktopWindows => 0;
    // M149: the same desktop windows, only those below `front` in the z-order, nearest first.
    IReadOnlyList<WindowSnapshot> DesktopWindowsBehind(WindowIdentity front) => [];
    bool Execute(WindowIdentity identity, WindowControlAction action);
    bool SetBounds(WindowIdentity identity, WindowBounds bounds);
    // ARRANGE1781: the work area (desktop minus taskbar) of the monitor
    // that shows the window; null when the platform cannot tell.
    WindowBounds? WorkArea(WindowIdentity identity) => null;
    // Ronda 22 (revisión 1): where the window stands on the desktop; null when the platform cannot tell.
    WindowStanding? Standing(WindowIdentity identity) => null;
    bool RequestClose(WindowIdentity identity);
    bool RequestSystemClose(WindowIdentity identity);
    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
    // v3 r22 uso real: the visible top-level windows of the same process that the window owns (its dialogs).
    IReadOnlyList<nint> OwnedDialogs(WindowIdentity identity) => [];
    // v3 r22 revisión: whether the window's application is capturing the microphone now (MicrophoneInUse).
    bool CapturesMicrophone(WindowIdentity identity) => false;
    // BAXY Renew cu (C13 en el PC): a window in full screen covers its whole monitor (taskbar included) with no title bar.
    bool FullScreen(WindowIdentity identity) => false;
    // BAXY Renew cu (C13 en el PC): one key posted to the window itself (never the real keyboard): Esc or F11.
    bool PostKey(WindowIdentity identity, ushort virtualKey, ushort scanCode) => false;
}

// Hidden (auditoría D7): the window still exists and is invisible; otherwise it is gone (or its handle is another's).
internal sealed class WindowIdentityChangedException(bool hidden = false) : InvalidOperationException
{
    internal bool Hidden { get; } = hidden;
}

internal sealed partial class Win32WindowControlPlatform : IWindowControlPlatform
{
    private const uint CloseMessage = 0x0010;
    private const uint SystemCommandMessage = 0x0112;
    private const int SystemCloseCommand = 0xF060;
    private const int ShowMinimized = 6;
    private const int ShowMaximized = 3;
    private const int Restore = 9;

    // Renew al máximo (auditoría de flujos): a window's executable, read as the application inventory reads it (the least
    // access Windows grants); its main module, read before, is refused for a program running as administrator, and every
    // window of one resolved by its application failed verification.
    private readonly Func<int, string?> _imagePath;

    public Win32WindowControlPlatform()
        : this(null)
    {
    }

    internal Win32WindowControlPlatform(Func<int, string?>? imagePath)
    {
        _imagePath = imagePath ?? WindowsInstalledApplicationPlatform.ExecutableImagePath;
    }

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
        // Auditoría final V3/G3: a title is the one asked only when it is that title, folded (case, accents, whitespace).
        string? title = byTitle ? InstalledApplicationResolver.Normalize(processName) : null;
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
                bool matches = allWindows || (title is not null
                    ? title.Length > 0 && InstalledApplicationResolver.Normalize(ReadWindowTitle(handle)) == title
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
        if (!IsWindow(identity.Handle))
        {
            throw new WindowIdentityChangedException();
        }

        _ = GetWindowThreadProcessId(identity.Handle, out uint owner);
        if (owner != checked((uint)identity.ProcessId))
        {
            throw new WindowIdentityChangedException();
        }

        if (!IsWindowVisible(identity.Handle))
        {
            throw new WindowIdentityChangedException(hidden: true);
        }

        using Process process = Process.GetProcessById(identity.ProcessId);
        if (process.StartTime.ToUniversalTime().Ticks != identity.ProcessCreationTimeUtcTicks
            || !string.Equals(process.ProcessName, identity.ProcessName,
                StringComparison.OrdinalIgnoreCase)
            || (identity.ExecutablePath is not null
                && !string.Equals(_imagePath(identity.ProcessId), identity.ExecutablePath,
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
            ReadWindowTitle(identity.Handle),
            Owned: GetWindow(identity.Handle, OwnerWindow) != 0);
    }

    // window.focus hands the front over the way app.open hands it back (ForegroundRight): a plain SetForegroundWindow
    // from this background process is refused once the process used its right, and every window.focus of a turn after
    // the first failed with action_failed (e2e 2026-10-19: 17 of 17 in one run).
    public bool Execute(WindowIdentity identity, WindowControlAction action) =>
        Act(Observe(identity), action, ShowWindowAsync, static handle => External.ForegroundRight.Give(handle).Held);

    // Each of these acts moves the front because it was asked for (focus, maximize and restore activate the window,
    // a snap restores it first; minimize hands the front to the next window): the front is noted as taken on purpose
    // first, so the guard of an opening (ForegroundHandBack) never hands it back to the window it had before.
    internal static bool Act(
        WindowSnapshot snapshot,
        WindowControlAction action,
        Func<nint, int, bool> showWindowAsync,
        Func<nint, bool> setForegroundWindow)
    {
        if (action is not (WindowControlAction.Focus or WindowControlAction.Minimize
            or WindowControlAction.Maximize or WindowControlAction.Restore))
            return false;
        ForegroundHandBack.NoteFrontTaken();
        nint handle = snapshot.Identity.Handle;
        return action switch
        {
            WindowControlAction.Focus => ExecuteFocus(snapshot, showWindowAsync, setForegroundWindow),
            WindowControlAction.Minimize => showWindowAsync(handle, ShowMinimized),
            WindowControlAction.Maximize => showWindowAsync(handle, ShowMaximized),
            _ => showWindowAsync(handle, Restore),
        };
    }

    public IReadOnlyList<WindowSnapshot> DesktopWindows()
    {
        List<WindowSnapshot> found = EnumerateDesktopWindows(below: 0, out int unread, out int cloakedTitled);
        UnreadDesktopWindows = unread;
        CloakedDesktopWindows = cloakedTitled;
        return found;
    }

    public int UnreadDesktopWindows { get; private set; }

    public int CloakedDesktopWindows { get; private set; }

    // M149: EnumWindows walks the top-level windows in z-order, top first; collection starts right after
    // `front`. A front window that is gone meanwhile yields nothing rather than a guess.
    public IReadOnlyList<WindowSnapshot> DesktopWindowsBehind(WindowIdentity front) =>
        front.Handle == 0 ? [] : EnumerateDesktopWindows(front.Handle, out _, out _);

    private List<WindowSnapshot> EnumerateDesktopWindows(nint below, out int unread, out int cloakedTitled)
    {
        int failed = 0;
        var cloakedTitledWindows = new List<nint>();
        // MINALL1687: what the taskbar would show as windows. The shell's own
        // surfaces (desktop, taskbar), cloaked UWP hosts, tool windows, owned
        // popups and untitled windows are not windows a person minimizes; the
        // product's own window is left alone.
        var found = new List<WindowSnapshot>();
        int self = Environment.ProcessId;
        bool collecting = below == 0;
        EnumWindowsProc callback = (handle, _) =>
        {
            if (!collecting)
            {
                collecting = handle == below;
                return true;
            }
            if (!IsWindowVisible(handle) || GetAncestor(handle, GetRootOwner) != handle)
                return true;
            long exStyle = GetWindowLongPtr(handle, ExtendedStyleIndex).ToInt64();
            if ((exStyle & ToolWindowStyle) != 0)
                return true;
            if (DwmGetWindowAttribute(handle, CloakedAttribute, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
            {
                GetWindowThreadProcessId(handle, out uint cloakedOwner);
                if ((int)cloakedOwner != self && ReadWindowTitle(handle).Length > 0)
                    cloakedTitledWindows.Add(handle);
                return true;
            }
            string className = ReadClassName(handle);
            if (className is "Progman" or "WorkerW" or "Shell_TrayWnd" or "Shell_SecondaryTrayWnd")
                return true;
            GetWindowThreadProcessId(handle, out uint owner);
            if (owner == 0 || owner > int.MaxValue || (int)owner == self)
                return true;
            try
            {
                using Process process = Process.GetProcessById(checked((int)owner));
                string title = ReadWindowTitle(handle);
                if (string.IsNullOrWhiteSpace(title))
                    return true;
                var identity = new WindowIdentity(handle, process.Id,
                    process.StartTime.ToUniversalTime().Ticks, process.ProcessName, UtcNow);
                found.Add(Observe(identity));
            }
            catch (Exception exception) when (exception is Win32Exception
                or InvalidOperationException or NotSupportedException or ArgumentException)
            {
                // A window or its owner can disappear during enumeration; one still there was not read.
                if (IsWindow(handle) && IsWindowVisible(handle))
                    failed++;
            }
            return true;
        };
        if (!EnumWindows(callback, nint.Zero))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        unread = failed;
        // Ronda final 12 (regla 3): of the cloaked windows, those on another virtual desktop are left open elsewhere;
        // one the shell does not place is counted too (not known to be here), a suspended app on this desktop is not.
        // Only the whole desktop's read (below 0) reports them; the windows behind a front one do not need it.
        cloakedTitled = below != 0 ? 0
            : VirtualDesktops.OnAnotherDesktop(cloakedTitledWindows).Count(static elsewhere => elsewhere != false);
        return found;
    }

    private static unsafe string ReadClassName(nint window)
    {
        const int capacity = 256;
        char* buffer = stackalloc char[capacity];
        int length = GetClassName(window, buffer, capacity);
        return length <= 0 ? string.Empty : new string(buffer, 0, length);
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

    public bool CapturesMicrophone(WindowIdentity identity) => MicrophoneInUse.Capturing(identity);

    public IReadOnlyList<nint> OwnedDialogs(WindowIdentity identity)
    {
        var dialogs = new List<nint>();
        EnumWindowsProc callback = (handle, _) =>
        {
            if (handle != identity.Handle && IsWindowVisible(handle)
                && GetWindow(handle, OwnerWindow) == identity.Handle)
            {
                GetWindowThreadProcessId(handle, out uint owner);
                if (owner == unchecked((uint)identity.ProcessId))
                {
                    dialogs.Add(handle);
                }
            }

            return true;
        };
        if (!EnumWindows(callback, nint.Zero))
        {
            throw new InvalidOperationException("The owned windows could not be enumerated.");
        }

        GC.KeepAlive(callback);
        return dialogs;
    }

    public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    public WindowStanding? Standing(WindowIdentity identity)
    {
        _ = Observe(identity);
        long exStyle = GetWindowLongPtr(identity.Handle, ExtendedStyleIndex).ToInt64();
        int above = 0;
        nint previous = identity.Handle;
        // GW_HWNDPREV walks up the top-level windows; the bound only guards against a list that changes under it.
        while ((previous = GetWindow(previous, PreviousWindow)) != 0)
        {
            if (++above > MaximumWindowsAbove)
                return null;
        }
        return new WindowStanding(above, (exStyle & TopmostStyle) != 0, WorkArea(identity));
    }

    public WindowBounds? WorkArea(WindowIdentity identity)
    {
        _ = Observe(identity);
        nint monitor = MonitorFromWindow(identity.Handle, MonitorDefaultToNearest);
        if (monitor == nint.Zero)
        {
            return null;
        }
        var info = new NativeMonitorInfo { Size = (uint)Marshal.SizeOf<NativeMonitorInfo>() };
        if (!GetMonitorInfo(monitor, ref info))
        {
            return null;
        }
        return new WindowBounds(
            info.Work.Left,
            info.Work.Top,
            info.Work.Right - info.Work.Left,
            info.Work.Bottom - info.Work.Top);
    }

    public bool FullScreen(WindowIdentity identity)
    {
        _ = Observe(identity);
        nint monitor = MonitorFromWindow(identity.Handle, MonitorDefaultToNearest);
        var info = new NativeMonitorInfo { Size = (uint)Marshal.SizeOf<NativeMonitorInfo>() };
        if (monitor == nint.Zero || !GetMonitorInfo(monitor, ref info) || !GetWindowRect(identity.Handle, out NativeRect box))
        {
            return false;
        }

        const long TitleBar = 0x00C00000;
        long style = GetWindowLongPtr(identity.Handle, StyleIndex).ToInt64();
        return (style & TitleBar) != TitleBar
            && box.Left <= info.Monitor.Left && box.Top <= info.Monitor.Top
            && box.Right >= info.Monitor.Right && box.Bottom >= info.Monitor.Bottom;
    }

    public bool PostKey(WindowIdentity identity, ushort virtualKey, ushort scanCode)
    {
        _ = Observe(identity);
        nint down = 1 | ((nint)scanCode << 16);
        nint up = down | (nint)0x40000000 | unchecked((nint)0x80000000L);
        return PostMessage(identity.Handle, KeyDownMessage, virtualKey, down)
            && PostMessage(identity.Handle, KeyUpMessage, virtualKey, up);
    }

    private const uint KeyDownMessage = 0x0100;
    private const uint KeyUpMessage = 0x0101;
    private const int StyleIndex = -16;

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

    private const uint GetRootOwner = 3;
    private const int ExtendedStyleIndex = -20;
    private const long ToolWindowStyle = 0x00000080;
    private const uint CloakedAttribute = 14;

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint windowHandle, uint flags);

    private const uint OwnerWindow = 4;
    private const uint PreviousWindow = 3;
    private const long TopmostStyle = 0x00000008;
    private const int MaximumWindowsAbove = 65536;

    [LibraryImport("user32.dll")]
    private static partial nint GetWindow(nint windowHandle, uint command);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
    private static partial nint GetWindowLongPtr(nint windowHandle, int index);

    [LibraryImport("user32.dll", EntryPoint = "GetClassNameW")]
    private static unsafe partial int GetClassName(nint windowHandle, char* className, int capacity);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(nint windowHandle, uint attribute, out int value, int size);

    private const uint MonitorDefaultToNearest = 2;

    [LibraryImport("user32.dll")]
    private static partial nint MonitorFromWindow(nint windowHandle, uint flags);

    [LibraryImport("user32.dll", EntryPoint = "GetMonitorInfoW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetMonitorInfo(nint monitor, ref NativeMonitorInfo info);

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeMonitorInfo
    {
        public uint Size;
        public NativeRect Monitor;
        public NativeRect Work;
        public uint Flags;
    }
}
