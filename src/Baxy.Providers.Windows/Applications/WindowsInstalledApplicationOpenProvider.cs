using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Microsoft.Win32;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Providers.Windows.Applications;

public sealed class WindowsInstalledApplicationOpenProvider :
    IApplicationOpenProvider,
    IApplicationInventoryProvider,
    IApplicationCatalogProvider
{
    // APPS1609 «Abre Steam»: a client that updates itself before showing anything
    // (Steam's login window at 4.6 s, its main window at 7.9 s after launch) never
    // fit the earlier 28 polls; the launch is verified as soon as the window shows,
    // so the longer budget costs nothing to a prompt application.
    // UI1771: a launcher restarted right after an unclean exit (the Epic Games
    // Launcher) draws its first window well after 12 s; a launch whose window
    // is still to come is waited on for up to 30 s before it is declared
    // unverified, the way a person waits for a heavy program to appear.
    private const int VerificationAttempts = 300;
    private static readonly TimeSpan ObservationDelay = TimeSpan.FromMilliseconds(100);
    private static readonly TimeSpan CatalogLifetime = TimeSpan.FromMinutes(5);
    // M89 (DEV-D v3r D-w11-t5 «¿Me abres el Spotify?»): app.open started and never completed; the shell gave up
    // at 90 s and restarted the core («el tiempo de espera se agotó»). Three waits had no clock of their own: the
    // 300 polls (each one a whole process inventory, so far more than the 30 s they were meant to be), the
    // catalog's PowerShell read, and bringing a window to the front of a thread that may not answer. Each one
    // now ends on the clock, so the call always returns its own verdict well inside the shell's wait.
    internal static readonly TimeSpan VerificationBudget = TimeSpan.FromSeconds(30);
    internal static readonly TimeSpan DefaultCatalogReadBudget = TimeSpan.FromSeconds(20);
    internal static readonly TimeSpan ForegroundBudget = TimeSpan.FromSeconds(2);
    // cu-v3-documento-nuevo: how long the document of the New command is looked for (a new Office window takes about a
    // second to show).
    internal static readonly TimeSpan NewDocumentBudget = TimeSpan.FromSeconds(6);
    // Ronda 20 P4 (v3-01): how far apart the windows of a cold start are looked at while they settle, and for how long.
    internal static readonly TimeSpan StartSettleDelay = TimeSpan.FromMilliseconds(400);
    internal static readonly TimeSpan StartSettleBudget = TimeSpan.FromSeconds(10);

    private readonly IInstalledApplicationPlatform _platform;
    private readonly TimeSpan _catalogReadBudget;
    private readonly object _catalogLock = new();
    private IReadOnlyList<InstalledApplicationEntry>? _catalog;
    private Task<IReadOnlyList<InstalledApplicationEntry>>? _catalogLoadTask;
    private DateTimeOffset _catalogLoadedAt;

    public WindowsInstalledApplicationOpenProvider()
        : this(new WindowsInstalledApplicationPlatform())
    {
    }

    internal WindowsInstalledApplicationOpenProvider(IInstalledApplicationPlatform platform)
        : this(platform, DefaultCatalogReadBudget)
    {
    }

    internal WindowsInstalledApplicationOpenProvider(IInstalledApplicationPlatform platform, TimeSpan catalogReadBudget)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _catalogReadBudget = catalogReadBudget;
    }

    public ValueTask<ApplicationOpenResult> OpenAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken) => OpenAsync(request, launchAnew: false, cancellationToken);

    // launchAnew (auditoría D6): a new instance is launched and only a window that was not there before counts; no
    // window the application already had is reused.
    private async ValueTask<ApplicationOpenResult> OpenAsync(
        ApplicationOpenRequest request,
        bool launchAnew,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        cancellationToken.ThrowIfCancellationRequested();
        // v3 point 1 review: a new opening replaces the one the looks while an application starts hand the front back
        // for; only an opening that leaves the person's window in front notes itself again below.
        _platform.ForgetOpening();
        if (!ApplicationIds.IsValidRequest(request.ApplicationId))
        {
            return Failure(request, string.Empty, ApplicationOpenErrorCodes.InvalidApplication);
        }

        if (request.NewDocument && request.FilePath is null)
        {
            return await OpenNewDocumentAsync(request, cancellationToken).ConfigureAwait(false);
        }

        if (request.FilePath is { } asked && (!Path.IsPathFullyQualified(asked) || !File.Exists(asked)))
        {
            return Failure(request, request.ApplicationId, ApplicationOpenErrorCodes.LaunchFailed);
        }

        IReadOnlyList<InstalledApplicationEntry> catalog;
        try
        {
            catalog = await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is InvalidDataException
            or InvalidOperationException
            or JsonException)
        {
            return Failure(request, request.ApplicationId, ApplicationOpenErrorCodes.InventoryFailed);
        }

        InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(request.ApplicationId, catalog);
        if (resolution.Entry is null)
        {
            return Failure(
                request,
                request.ApplicationId,
                resolution.Ambiguous
                    ? ApplicationOpenErrorCodes.ApplicationAmbiguous
                    : ApplicationOpenErrorCodes.ApplicationNotFound,
                candidates: resolution.Candidates);
        }

        InstalledApplicationEntry entry = resolution.Entry;
        IReadOnlyList<InstalledApplicationObservation> before;
        try
        {
            before = _platform.Inventory(entry);
        }
        catch (Exception exception) when (exception is ApplicationInventoryException
            or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return Failure(request, entry.Name, ApplicationOpenErrorCodes.InventoryFailed);
        }

        // cu-v3-abrir-archivo: a file is handed to the application by the shell, never by a window of it already
        // running (that one shows something else): the activation below always happens.
        // cu-v3-elevacion (r9 v3-23, v3-65): a window of it that runs as administrator cannot be read nor pressed; when
        // its program opens again with the person's rights (a console, measured live), an opening with those rights
        // never reuses the raised one: it reuses a copy that is not raised (review, finding 4: the raised one in front
        // no longer hides the copy BAXY opened before, so copies do not pile up), or starts a new one. The raised copy
        // stays: BAXY cannot close it (refused by Windows, measured).
        InstalledApplicationObservation? existing = request.FilePath is not null || launchAnew ? null
            : Choose(Reusable(request, before));

        // r20b palanca 4 (v3-40, v3-43): an opening asked in front while the person works in another window (their
        // input reaches it less than their pause ago, and it is not BAXY's) shows the application above it without
        // taking their keyboard: it goes as one not asked in front (the front Windows gives it goes back at once) and
        // its window is shown above theirs without the activation. A request written in BAXY's own window opens in
        // front as before. Review: who works where is read at the end of the opening, right before the front would be
        // asked for (OpeningFront), the same rule every path of app.open follows.
        bool reused = existing is not null;
        if (existing is not null)
        {
            InstalledApplicationObservation? focused;
            long person = OpeningFront.PersonWindow(_platform, request.Foreground, window => IsOpened(existing, window), 0);
            try
            {
                focused = await TryFocusAsync(
                    entry,
                    existing,
                    request.Foreground && person == 0,
                    cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is ApplicationInventoryException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
                return Failure(
                    request,
                    entry.Name,
                    ApplicationOpenErrorCodes.InventoryFailed,
                    reusedExisting: true);
            }

            if (focused is not null)
            {
                bool shown = person != 0 && await OpeningFront.ShowWithoutActivationAsync(
                    _platform, focused.WindowHandle, person, window => IsOpened(focused, window), cancellationToken)
                    .ConfigureAwait(false);
                return Success(request, entry, focused, reused: true, shownWithoutFocus: shown);
            }
        }

        // v3 point 0 (arreglo 4): an opening the person did not ask to see in front leaves the front where it is.
        // Windows activates some applications by itself (a packaged app through its activation manager, a browser
        // shell that ignores how it was asked to show): the window that had the front gets it back at once.
        // Asked in front, it is also read: a person working in it when the opening ends gets it back (OpeningFront).
        long previousFront = _platform.ForegroundWindow();
        // A file not handed is said by its cause (cu-v3-archivo-empaquetado: never «Windows does not list it» for an
        // application Windows lists).
        string? notIssued;
        try
        {
            notIssued = request.FilePath is { } file
                ? _platform.ActivateForFile(entry, file) switch
                {
                    FileActivation.Outcome.Issued => null,
                    FileActivation.Outcome.NotListed => ApplicationOpenErrorCodes.FileNotAccepted,
                    _ => ApplicationOpenErrorCodes.FileActivationFailed,
                }
                : _platform.Activate(entry, request.ForControl) ? null : ApplicationOpenErrorCodes.LaunchFailed;
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return Failure(
                request,
                entry.Name,
                ApplicationOpenErrorCodes.LaunchFailed,
                launchIssued: false,
                reusedExisting: reused);
        }

        if (notIssued is not null)
        {
            return Failure(
                request,
                entry.Name,
                notIssued,
                launchIssued: false,
                reusedExisting: reused);
        }

        Stopwatch verification = Stopwatch.StartNew();
        for (int attempt = 0; attempt <= VerificationAttempts && verification.Elapsed < VerificationBudget; attempt++)
        {
            InstalledApplicationObservation? candidate;
            bool running = reused;
            try
            {
                IReadOnlyList<InstalledApplicationObservation> current = _platform.Inventory(entry);
                // Auditoría D5: only a window that was not there before is the launch's. A window of the application
                // that was already there (Windows showed the instance that runs) is said as it is: already running,
                // never launched. A new instance asked for (launchAnew) has only a new window.
                candidate = Choose(current, before);
                if (candidate is null && !launchAnew && Choose(Reusable(request, current)) is { } kept)
                {
                    candidate = kept;
                    running = true;
                }
            }
            catch (Exception exception) when (exception is ApplicationInventoryException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
                return Failure(
                    request,
                    entry.Name,
                    ApplicationOpenErrorCodes.InventoryFailed,
                    launchIssued: !reused,
                    reusedExisting: reused);
            }

            if (candidate is null)
            {
                if (attempt < VerificationAttempts)
                {
                    await _platform.DelayAsync(ObservationDelay, cancellationToken)
                        .ConfigureAwait(false);
                }

                continue;
            }

            // Review of r20b palanca 4: the person may have gone to their window while the application started.
            long person = OpeningFront.PersonWindow(_platform, request.Foreground, window => IsOpened(candidate, window), previousFront);
            bool takeFront = request.Foreground && person == 0;
            long handBackTo = request.Foreground ? person : previousFront;
            InstalledApplicationObservation? focused;
            try
            {
                focused = await TryFocusAsync(
                    entry,
                    candidate,
                    takeFront,
                    cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is ApplicationInventoryException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
                return Failure(
                    request,
                    entry.Name,
                    ApplicationOpenErrorCodes.InventoryFailed,
                    launchIssued: !reused,
                    reusedExisting: reused);
            }

            if (focused is not null)
            {
                (bool activated, bool restored) = takeFront
                    ? (false, false)
                    : await HandBackFrontAsync(handBackTo, focused, cancellationToken).ConfigureAwait(false);
                bool shown = person != 0 && await OpeningFront.ShowWithoutActivationAsync(
                    _platform, focused.WindowHandle, person, window => IsOpened(focused, window), cancellationToken)
                    .ConfigureAwait(false);
                if (!takeFront && handBackTo != 0)
                {
                    LastFrontGuard = GuardFrontAsync(handBackTo, focused.ProcessId, _platform.FrontGuardStamp());
                    // v3 point 1: the looks while the application starts hand back a front it takes later.
                    _platform.NoteOpening(handBackTo, focused.ProcessId);
                }
                return Success(request, entry, focused, running, activated, restored, shownWithoutFocus: shown);
            }

            if (attempt < VerificationAttempts)
            {
                await _platform.DelayAsync(ObservationDelay, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return Failure(
            request,
            entry.Name,
            ApplicationOpenErrorCodes.VerificationFailed,
            launchIssued: !reused,
            reusedExisting: reused);
    }

    public async ValueTask<ApplicationInstalledResult> IsInstalledAsync(
        string applicationName,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (string.IsNullOrWhiteSpace(applicationName) || applicationName.Length > 256)
        {
            return new(applicationName ?? string.Empty, null, false, false,
                ApplicationOpenErrorCodes.InvalidApplication);
        }

        IReadOnlyList<InstalledApplicationEntry> catalog;
        try
        {
            catalog = await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return new(applicationName, null, false, false,
                ApplicationOpenErrorCodes.InventoryFailed);
        }

        InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(applicationName, catalog);
        if (resolution.Ambiguous)
        {
            return new(applicationName, null, false, false,
                ApplicationOpenErrorCodes.ApplicationAmbiguous);
        }
        return resolution.Entry is { } entry
            ? new(
                applicationName,
                entry.Name,
                true,
                true,
                null,
                TryReadInstalledVersion(entry.Name))
            : new(applicationName, null, false, true, null);
    }

    public async ValueTask<InstalledApplicationCatalogSnapshot> GetCatalogSnapshotAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            IReadOnlyList<InstalledApplicationEntry> catalog =
                await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
            return CreateCatalogSnapshot(catalog);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return new(false, false, Array.Empty<string>());
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return new(false, false, Array.Empty<string>());
        }
    }

    internal static InstalledApplicationCatalogSnapshot CreateCatalogSnapshot(
        IReadOnlyList<InstalledApplicationEntry> catalog)
    {
        ArgumentNullException.ThrowIfNull(catalog);
        if (catalog.Any(static entry =>
            entry.Name.Contains('\uFFFD', StringComparison.Ordinal)
            || entry.AppUserModelId.Contains('\uFFFD', StringComparison.Ordinal)))
        {
            throw new InvalidDataException(
                "The Start application catalog contains a Unicode replacement character.");
        }

        var candidates = new List<(string Name, string AppUserModelId, string Key)>();
        foreach (InstalledApplicationEntry entry in catalog)
        {
            if (!InstalledApplicationResolver.IsUsable(entry))
            {
                continue;
            }

            string name = entry.Name.Trim().Normalize(NormalizationForm.FormC);
            string key;
            try
            {
                key = ApplicationCatalogContract.NormalizeName(name);
            }
            catch (ArgumentException)
            {
                continue;
            }

            if (key.Length != 0)
            {
                candidates.Add((name, entry.AppUserModelId, key));
            }
        }

        string[] safelyResolvableNames = candidates
            .GroupBy(static candidate => candidate.Key, StringComparer.Ordinal)
            .Where(static group =>
                group.Select(static candidate => candidate.AppUserModelId)
                    .Distinct(StringComparer.Ordinal)
                    .Count() == 1)
            .Select(static group => group
                .OrderBy(static candidate => candidate.Name, StringComparer.OrdinalIgnoreCase)
                .ThenBy(static candidate => candidate.Name, StringComparer.Ordinal)
                .First()
                .Name)
            .OrderBy(static name => name, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static name => name, StringComparer.Ordinal)
            .ToArray();

        var names = new List<string>(
            Math.Min(safelyResolvableNames.Length, ApplicationCatalogContract.MaximumNames));
        int totalUtf8Bytes = 0;
        int totalEscapedUtf8Bytes = 0;
        bool complete = true;
        foreach (string name in safelyResolvableNames)
        {
            int utf8Bytes = Encoding.UTF8.GetByteCount(name);
            int escapedUtf8Bytes = JsonEncodedText.Encode(name).EncodedUtf8Bytes.Length;
            if (names.Count == ApplicationCatalogContract.MaximumNames)
            {
                complete = false;
                break;
            }

            if (utf8Bytes > ApplicationCatalogContract.MaximumNameUtf8Bytes
                || totalUtf8Bytes + utf8Bytes
                    > ApplicationCatalogContract.MaximumTotalNameUtf8Bytes
                || totalEscapedUtf8Bytes + escapedUtf8Bytes
                    > ApplicationCatalogContract.MaximumEscapedNamesUtf8Bytes)
            {
                complete = false;
                continue;
            }

            names.Add(name);
            totalUtf8Bytes += utf8Bytes;
            totalEscapedUtf8Bytes += escapedUtf8Bytes;
        }

        return new(true, complete, names);
    }

    private static string? TryReadInstalledVersion(string displayName)
    {
        string target = InstalledApplicationResolver.Normalize(displayName);
        if (target.Length < 2)
            return null;
        foreach ((RegistryHive hive, RegistryView view) in new[]
        {
            (RegistryHive.CurrentUser, RegistryView.Default),
            (RegistryHive.LocalMachine, RegistryView.Registry64),
            (RegistryHive.LocalMachine, RegistryView.Registry32),
        })
        {
            try
            {
                using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view);
                using RegistryKey? uninstall = baseKey.OpenSubKey(
                    @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    writable: false);
                if (uninstall is null)
                    continue;
                foreach (string subKeyName in uninstall.GetSubKeyNames())
                {
                    using RegistryKey? item = uninstall.OpenSubKey(subKeyName, writable: false);
                    string? candidateName = item?.GetValue("DisplayName") as string;
                    if (string.IsNullOrWhiteSpace(candidateName)
                        || InstalledApplicationResolver.Normalize(candidateName) != target)
                        continue;
                    string? version = item?.GetValue("DisplayVersion") as string;
                    if (!string.IsNullOrWhiteSpace(version) && version.Length <= 128)
                        return version.Trim();
                }
            }
            catch (Exception exception) when (exception is UnauthorizedAccessException
                or IOException
                or System.Security.SecurityException)
            {
            }
        }
        return null;
    }

    internal async ValueTask<(IReadOnlyList<InstalledApplicationObservation> Windows, string? ErrorCode)>
        ResolveWindowIdentitiesAsync(string applicationName, CancellationToken cancellationToken)
    {
        var (windows, errorCode, _) = await ResolveApplicationWindowsAsync(applicationName, cancellationToken)
            .ConfigureAwait(false);
        return (windows, errorCode);
    }

    // v3 r6 lectores: the windows of one installed application with the catalog identity that resolved them, so a
    // window issued from it keeps which application it is even when its frame belongs to a shared host process.
    internal async ValueTask<(IReadOnlyList<InstalledApplicationObservation> Windows, string? ErrorCode,
            string? AppUserModelId)>
        ResolveApplicationWindowsAsync(string applicationName, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!ApplicationIds.IsValidRequest(applicationName))
            return ([], ApplicationOpenErrorCodes.InvalidApplication, null);

        try
        {
            IReadOnlyList<InstalledApplicationEntry> catalog =
                await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
            // This effect prerequisite accepts only a complete installed name (the resolver's only rule).
            InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(
                applicationName, catalog);
            if (resolution.Ambiguous)
                return ([], ApplicationOpenErrorCodes.ApplicationAmbiguous, null);
            if (resolution.Entry is not { } entry)
                return ([], ApplicationOpenErrorCodes.ApplicationNotFound, null);
            if (!entry.AppUserModelId.Contains('!')
                && WindowsInstalledApplicationPlatform.StrongExecutablePath(entry) is null)
                return ([], "application_window_identity_unavailable", null);

            return (_platform.InventoryForWindowResolution(entry, cancellationToken), null, entry.AppUserModelId);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return ([], ApplicationOpenErrorCodes.InventoryFailed, null);
        }
    }

    public async ValueTask<ApplicationWindowStatusResult> GetWindowStatusAsync(
        string applicationName,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!ApplicationIds.IsValidRequest(applicationName))
        {
            return new(applicationName ?? string.Empty, null, false, false, 0, false,
                ApplicationOpenErrorCodes.InvalidApplication);
        }

        IReadOnlyList<InstalledApplicationEntry> catalog;
        try
        {
            catalog = await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return new(applicationName, null, false, false, 0, false,
                ApplicationOpenErrorCodes.InventoryFailed);
        }

        InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(applicationName, catalog);
        if (resolution.Ambiguous)
        {
            return new(applicationName, null, false, false, 0, false,
                ApplicationOpenErrorCodes.ApplicationAmbiguous);
        }
        if (resolution.Entry is null)
        {
            return new(applicationName, null, false, false, 0, true, null);
        }

        IReadOnlyList<InstalledApplicationObservation> observations;
        try
        {
            observations = _platform.Inventory(resolution.Entry);
        }
        catch (Exception exception) when (exception is ApplicationInventoryException
            or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return new(applicationName, resolution.Entry.Name, true, false, 0, false,
                ApplicationOpenErrorCodes.InventoryFailed);
        }

        int visibleWindowCount = observations.Count(static observation =>
            observation.Visible && observation.WindowHandle != 0);
        return new(
            applicationName,
            resolution.Entry.Name,
            Installed: true,
            HasVisibleWindow: visibleWindowCount > 0,
            VisibleWindowCount: visibleWindowCount,
            Verified: true,
            ErrorCode: null);
    }

    private async ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
        CancellationToken cancellationToken)
    {
        DateTimeOffset now = DateTimeOffset.UtcNow;
        Task<IReadOnlyList<InstalledApplicationEntry>> loadTask;
        lock (_catalogLock)
        {
            if (_catalog is not null && now - _catalogLoadedAt < CatalogLifetime)
            {
                return _catalog;
            }

            _catalogLoadTask ??= ReadCatalogWithinBudgetAsync();
            loadTask = _catalogLoadTask;
        }

        try
        {
            IReadOnlyList<InstalledApplicationEntry> loaded;
            try
            {
                loaded = await loadTask.WaitAsync(cancellationToken).ConfigureAwait(false);
            }
            catch (TimeoutException)
            {
                // M89: a refresh that did not answer in time leaves the last catalog read in force; with none, the
                // inventory fails as it does for an unreadable catalog.
                lock (_catalogLock)
                {
                    if (ReferenceEquals(_catalogLoadTask, loadTask))
                    {
                        _catalogLoadTask = null;
                    }

                    if (_catalog is not null)
                    {
                        return _catalog;
                    }
                }

                throw new InvalidOperationException("The installed application catalog did not answer in time.");
            }
            lock (_catalogLock)
            {
                _catalog = loaded;
                _catalogLoadedAt = DateTimeOffset.UtcNow;
                if (ReferenceEquals(_catalogLoadTask, loadTask))
                {
                    _catalogLoadTask = null;
                }
            }

            return loaded;
        }
        catch
        {
            lock (_catalogLock)
            {
                if (ReferenceEquals(_catalogLoadTask, loadTask))
                {
                    _catalogLoadTask = null;
                }
            }

            throw;
        }
    }

    private async Task<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogWithinBudgetAsync()
    {
        // The read is shared by every caller that joins it, so it runs on its own budget, not on the first caller's
        // token; the PowerShell read is killed when the budget ends.
        using var budget = new CancellationTokenSource(_catalogReadBudget);
        try
        {
            return await _platform.ReadCatalogAsync(budget.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (budget.IsCancellationRequested)
        {
            throw new TimeoutException("The installed application catalog did not answer in time.");
        }
    }

    private async ValueTask RequestForegroundWithinBudgetAsync(long windowHandle, CancellationToken cancellationToken)
    {
        // The handoff attaches to the foreground thread and moves the target window synchronously; a window whose
        // thread does not answer would hold this call without end. Focus is a courtesy (TryFocusAsync), so a
        // handoff still pending at the budget is left behind and the window is observed as it is.
        Task request = Task.Factory.StartNew(
            () => _platform.RequestForeground(windowHandle),
            CancellationToken.None,
            TaskCreationOptions.LongRunning,
            TaskScheduler.Default);
        try
        {
            await request.WaitAsync(ForegroundBudget, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
        }
    }

    // Windows gave the opened window the front the person did not ask for: it goes back to the window that had it.
    // Whether Windows activated it, and whether the front is back (read after the hand-back, never assumed).
    private async ValueTask<(bool Activated, bool Restored)> HandBackFrontAsync(
        long previousFront,
        InstalledApplicationObservation opened,
        CancellationToken cancellationToken)
    {
        if (previousFront == 0 || !opened.Foreground || opened.WindowHandle == previousFront)
            return (false, false);
        bool restored = await ReturnForegroundWithinBudgetAsync(previousFront, opened.WindowHandle, cancellationToken)
            .ConfigureAwait(false);
        return (true, restored);
    }

    // Some applications take the front a moment after their window shows (a splash replaced by the main window): for
    // a short while after the opening, a front taken by the opened application goes back to the person's window, as
    // many times as it takes it (cu-v3-foco-segunda: a packaged editor took it again 30 ms after its hand-back, from a
    // window of another process of the same program). A hand-back Windows refused ends the guard: never fought.
    internal static readonly TimeSpan FrontGuard = TimeSpan.FromSeconds(3);

    // The last guard started (what a test awaits).
    internal Task? LastFrontGuard { get; private set; }

    // The guard ends the moment BAXY takes the front on purpose (the next act of a mission brings its window up,
    // often well inside the guard) or the person does something that moves the front (a click on the opened window
    // is theirs to keep; r4a M2: typing in their own window is not, and does not end it): only a front the
    // application took by itself is handed back. r4a M4 (w1): each look reads and hands back under the front's gate,
    // which the foreground lease holds while it brings a window up, so the guard never undoes a burst's front.
    private async Task GuardFrontAsync(long previousFront, int processId, ForegroundHandBack.GuardStamp stamp)
    {
        try
        {
            var watch = Stopwatch.StartNew();
            while (watch.Elapsed < FrontGuard)
            {
                await Task.Delay(100).ConfigureAwait(false);
                await ForegroundHandBack.FrontGate.WaitAsync().ConfigureAwait(false);
                try
                {
                    if (_platform.FrontGuardInterrupted(stamp))
                        return;
                    long front = _platform.ForegroundWindow();
                    if (front == 0 || front == previousFront)
                        continue;
                    if (_platform.SameApplication(processId, _platform.WindowProcessId(front)))
                    {
                        bool restored = await ReturnForegroundWithinBudgetAsync(previousFront, front, CancellationToken.None)
                            .ConfigureAwait(false);
                        ForegroundHandBack.NoteGuardReturn(restored);
                        if (!restored)
                            return;
                    }
                }
                finally
                {
                    _ = ForegroundHandBack.FrontGate.Release();
                }
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.ComponentModel.Win32Exception or OverflowException)
        {
            // The guard is a courtesy: a window gone meanwhile ends it.
        }
    }

    // r4a M4 (w1): a hand-back still running at its budget is given up for real (the platform checks «late» before
    // each of its steps), so it never takes, afterwards, a front a burst of the lease took meanwhile.
    // Whether the front is back within the budget.
    private async ValueTask<bool> ReturnForegroundWithinBudgetAsync(long previous, long opened, CancellationToken cancellationToken)
    {
        // Not disposed: the hand-back may still read it after the budget.
        var late = new CancellationTokenSource();
        Task<bool> request = Task.Factory.StartNew(
            () => _platform.ReturnForeground(previous, opened, late.Token),
            CancellationToken.None,
            TaskCreationOptions.LongRunning,
            TaskScheduler.Default);
        try
        {
            return await request.WaitAsync(ForegroundBudget, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is TimeoutException or OperationCanceledException)
        {
            late.Cancel();
            if (exception is OperationCanceledException)
                throw;
            return false;
        }
    }

    /// <summary>
    /// cu-v3-documento-nuevo (uso real t4-c14: «pegame lo que copie en un bloc de notas nuevo» reused the open Notepad and
    /// pasted into the person's «*lista pan»; t4-c06 «crea un blank workbook» with Excel open made nothing). Auditoría
    /// D6: a new instance of the application is launched (behind, unless the front was asked for: v3 point 0) and only a
    /// window that was not there before counts; no key ever goes to a window the application already had, which may be
    /// the person's. An application that only shows the instance that runs opens no new window, and the opening ends
    /// <see cref="ApplicationOpenErrorCodes.NewDocumentNotCreated"/>. The launched window's own New command (Ctrl+N, the
    /// command document applications share) is given to it inside a burst of the foreground lease: after the person's
    /// pause with no modifier down, only while that window holds the front, and the front goes back to them right after
    /// (review of cu-v3-documento-nuevo, finding 4). The new document is seen, never assumed: a window of the application
    /// that was not there before the command, or the same window showing another document (its title changed: a new
    /// tab) when its title held still before the command and changed beyond a saved mark (finding 5: a page that ends
    /// loading, a song that changes, a «*» that goes). A dialog the command raised («¿Guardar cambios?») is never
    /// answered nor closed: it stays for the person, and the opening ends
    /// <see cref="ApplicationOpenErrorCodes.NewDocumentNotCreated"/>, so nothing after it writes anywhere.
    /// </summary>
    private async ValueTask<ApplicationOpenResult> OpenNewDocumentAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken)
    {
        // The windows the application already had (the person's): never the launch's, never sent a key.
        InstalledApplicationEntry? entry;
        HashSet<long> theirs;
        try
        {
            entry = InstalledApplicationResolver.Resolve(
                request.ApplicationId, await ReadCatalogAsync(cancellationToken).ConfigureAwait(false)).Entry;
            theirs = entry is null ? [] : [.. _platform.Inventory(entry).Select(static item => item.WindowHandle)];
        }
        catch (Exception exception) when (exception is ApplicationInventoryException
            or InvalidDataException
            or InvalidOperationException
            or JsonException
            or System.ComponentModel.Win32Exception)
        {
            return Failure(request, request.ApplicationId, ApplicationOpenErrorCodes.InventoryFailed);
        }

        ApplicationOpenResult opened = await OpenAsync(
            request with { NewDocument = false },
            launchAnew: true,
            cancellationToken).ConfigureAwait(false);
        ApplicationOpenResult NotCreated() => Failure(
            request,
            opened.DisplayName,
            ApplicationOpenErrorCodes.NewDocumentNotCreated,
            launchIssued: true);
        if (!opened.Succeeded || !opened.Verified
            || opened.WindowHandle is not long window || opened.ProcessId is not int process || entry is null)
        {
            // An application that only shows the instance that runs opened no new window: no new document was made.
            return opened.ErrorCode == ApplicationOpenErrorCodes.VerificationFailed ? NotCreated() : opened;
        }

        IReadOnlyList<InstalledApplicationObservation> before;
        string titleBefore;
        bool titleTells;
        HashSet<string> bareTitles;
        try
        {
            // Ronda 20 P4 (v3-01: a presentation program verified on its «Abriendo - …» start window; its main
            // window, still on the start screen, was born while the command waited and was taken for the new
            // document). The start is let settle first: the command goes to the window the start left, once no new
            // one has come for two looks. A title the start showed on another window (a splash), or the application's
            // bare name, is never a document; the settled main window's own title may be one (revisión 2 de P4).
            bareTitles = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { Bare(entry.Name), Bare(opened.DisplayName) };
            (long? settled, IReadOnlyList<string> startTitles) = await SettleStartAsync(entry, window, theirs, cancellationToken)
                .ConfigureAwait(false);
            if (settled is not long main)
            {
                return NotCreated();
            }

            window = main;
            bareTitles.UnionWith(startTitles.Select(Bare));
            bareTitles.Remove(string.Empty);
            // Finding 5: a title that changes by itself (a page loading, a player's song) tells no new tab; it is read
            // twice before the command and only a title that held still may tell one.
            string titleFirst = _platform.WindowTitle(window);
            await _platform.DelayAsync(ObservationDelay, cancellationToken).ConfigureAwait(false);
            titleBefore = _platform.WindowTitle(window);
            titleTells = string.Equals(titleFirst, titleBefore, StringComparison.Ordinal);
            // What was there is read right before the command (P4): a window born before it is never its document.
            before = _platform.Inventory(entry);
        }
        catch (Exception exception) when (exception is ApplicationInventoryException
            or InvalidDataException
            or InvalidOperationException
            or JsonException
            or System.ComponentModel.Win32Exception)
        {
            return NotCreated();
        }

        bool IsDocument(long handle) => !bareTitles.Contains(Bare(_platform.WindowTitle(handle)));

        // The window in front before the command (its burst hands the front back to it).
        long frontBeforeCommand = request.Foreground ? _platform.ForegroundWindow() : 0;

        // The command goes only to the application's own window, in a burst of the foreground lease (finding 4).
        if (!await _platform.IssueNewDocumentAsync(window, cancellationToken).ConfigureAwait(false))
        {
            return NotCreated();
        }

        Stopwatch verification = Stopwatch.StartNew();
        for (int look = 0;
            look * ObservationDelay < NewDocumentBudget && verification.Elapsed < NewDocumentBudget;
            look++)
        {
            await _platform.DelayAsync(ObservationDelay, cancellationToken).ConfigureAwait(false);
            InstalledApplicationObservation? made;
            List<long> dialogs;
            try
            {
                IReadOnlyList<InstalledApplicationObservation> current = _platform.Inventory(entry);
                List<InstalledApplicationObservation> appeared = current
                    .Where(item => item.Visible
                        && Path.IsPathFullyQualified(item.ExecutablePath)
                        && !before.Any(previous => previous.WindowHandle == item.WindowHandle))
                    .ToList();
                // A window another one owns is a dialog («¿Guardar cambios?» before a New in a one-document
                // application), never the new document.
                dialogs = appeared.Where(item => _platform.IsOwnedWindow(item.WindowHandle)).Select(static item => item.WindowHandle).ToList();
                // P4: a window titled with the application's bare name (its start screen) is no document either.
                made = appeared
                    .Where(item => !dialogs.Contains(item.WindowHandle) && IsDocument(item.WindowHandle))
                    .OrderByDescending(static item => item.Foreground)
                    .FirstOrDefault();
                if (made is null && titleTells && TitleShowsAnotherDocument(titleBefore, _platform.WindowTitle(window))
                    && IsDocument(window))
                {
                    made = current.FirstOrDefault(item => item.WindowHandle == window && item.ProcessId == process && item.Visible);
                }
            }
            catch (Exception exception) when (exception is ApplicationInventoryException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
                return NotCreated();
            }

            if (made is not null)
            {
                // Review of r20b palanca 4: the new document follows the rule of every opening (OpeningFront), read
                // now: a person working in their window keeps their keyboard (a front the new window took goes back)
                // and the document is shown above theirs; otherwise the front is taken as asked.
                long person = OpeningFront.PersonWindow(
                    _platform, request.Foreground, other => IsOpened(made, other), frontBeforeCommand);
                if (person == 0)
                {
                    if (request.Foreground)
                        _platform.RequestForeground(made.WindowHandle);
                    return Success(request, entry, made, reused: false, newDocument: true);
                }

                (bool activated, bool restored) = await HandBackFrontAsync(person, made, cancellationToken).ConfigureAwait(false);
                bool shown = await OpeningFront.ShowWithoutActivationAsync(
                    _platform, made.WindowHandle, person, other => IsOpened(made, other), cancellationToken)
                    .ConfigureAwait(false);
                return Success(request, entry, made, reused: false, activated, restored, newDocument: true,
                    shownWithoutFocus: shown);
            }

            if (dialogs.Count > 0)
            {
                // Auditoría D6: a dialog the command raised is never answered nor closed; the document was not made.
                return NotCreated();
            }
        }

        return NotCreated();
    }

    // A window title with a part besides the application's name («Nueva pestaña - …», «Sin título - …»): a dash
    // between spaces separates them.
    private static bool NamesADocument(string title) =>
        title.Contains(" - ", StringComparison.Ordinal) || title.Contains(" — ", StringComparison.Ordinal)
        || title.Contains(" – ", StringComparison.Ordinal);

    // A title as the bare name of an application is compared: its unsaved mark and its spaces left aside.
    private static string Bare(string? title) =>
        (title ?? string.Empty).Replace("*", string.Empty, StringComparison.Ordinal).Trim();

    // Ronda 20 P4 (v3-01): the windows a cold start shows (a splash, then the main window) settle before a command
    // goes to one: looks StartSettleDelay apart until two in a row bring no new window, within StartSettleBudget. The
    // window is the last one born that is still shown (the main window after a splash), else the one the opening
    // verified, else any shown; with the titles the start showed on its other windows (never the settled main
    // window's own title, which a new window of the command may repeat). A window the application had before the
    // launch («theirs», auditoría D6) is never one of the start's.
    private async ValueTask<(long? Window, IReadOnlyList<string> Titles)> SettleStartAsync(
        InstalledApplicationEntry entry,
        long started,
        HashSet<long> theirs,
        CancellationToken cancellationToken)
    {
        List<long> Shown() => _platform.Inventory(entry)
            .Where(item => item.Visible && Path.IsPathFullyQualified(item.ExecutablePath)
                && !theirs.Contains(item.WindowHandle) && !_platform.IsOwnedWindow(item.WindowHandle))
            .Select(static item => item.WindowHandle)
            .ToList();

        var titles = new List<string> { _platform.WindowTitle(started) };
        var seen = new HashSet<long> { started };
        var born = new List<long>();
        foreach (long handle in Shown())
        {
            if (seen.Add(handle))
            {
                born.Add(handle);
            }
        }

        int still = 0;
        Stopwatch clock = Stopwatch.StartNew();
        for (int look = 0;
            still < 2 && look * StartSettleDelay < StartSettleBudget && clock.Elapsed < StartSettleBudget;
            look++)
        {
            await _platform.DelayAsync(StartSettleDelay, cancellationToken).ConfigureAwait(false);
            List<long> fresh = Shown().Where(seen.Add).ToList();
            born.AddRange(fresh);
            still = fresh.Count == 0 ? still + 1 : 0;
        }

        List<long> shown = Shown();
        long? chosen = born.LastOrDefault(shown.Contains) is long last && last != 0 ? last
            : shown.Contains(started) ? started
            : shown.Count > 0 ? shown[0]
            : null;
        // Revisión 2 de P4 (a cold «abrí un chrome nuevo» left «Nueva pestaña - …» and the New command's window
        // repeated that title): only the start's other windows (a splash, «Abriendo - …») and the title the verified
        // window had before settling are start titles. The settled main window's own title names a document when it
        // has one besides the application («Nueva pestaña - …»), and a new window may repeat it; a title of one
        // segment («PowerPoint» on its start screen, the application's own name however the catalog writes it) stays.
        titles.AddRange(shown.Where(handle => handle != chosen).Select(_platform.WindowTitle));
        if (chosen is long main)
        {
            string settled = Bare(_platform.WindowTitle(main));
            if (NamesADocument(settled))
            {
                titles.RemoveAll(title => string.Equals(Bare(title), settled, StringComparison.OrdinalIgnoreCase));
            }
            else
            {
                titles.Add(settled);
            }
        }

        return (chosen, titles);
    }

    // The window shows another document: its title changed beyond the unsaved mark («*lista pan» → «lista pan» is the
    // same document saved).
    internal static bool TitleShowsAnotherDocument(string before, string now)
    {
        static string Document(string title) => title.Replace("*", string.Empty, StringComparison.Ordinal).Trim();
        return now.Length > 0 && !string.Equals(Document(before), Document(now), StringComparison.Ordinal);
    }

    // Whether «window» is the opened application's: its window, or a window of its process or of the same program.
    private bool IsOpened(InstalledApplicationObservation opened, long window) =>
        window == opened.WindowHandle || _platform.SameApplication(opened.ProcessId, _platform.WindowProcessId(window));

    private async ValueTask<InstalledApplicationObservation?> TryFocusAsync(
        InstalledApplicationEntry entry,
        InstalledApplicationObservation candidate,
        bool foreground,
        CancellationToken cancellationToken)
    {
        // The front is asked for only when the person asked for it (app.open «foreground»).
        if (foreground)
            await RequestForegroundWithinBudgetAsync(candidate.WindowHandle, cancellationToken).ConfigureAwait(false);
        InstalledApplicationObservation? Observe(bool requireForeground) =>
            _platform.Inventory(entry).FirstOrDefault(item =>
                item.ProcessId == candidate.ProcessId
                && item.ProcessCreationTimeUtcTicks == candidate.ProcessCreationTimeUtcTicks
                && item.WindowHandle == candidate.WindowHandle
                && item.Visible
                && (!requireForeground || item.Foreground));
        InstalledApplicationObservation? observed = Observe(requireForeground: foreground);
        if (observed is not null)
        {
            return observed;
        }

        await _platform.DelayAsync(ObservationDelay, cancellationToken).ConfigureAwait(false);
        // Bringing the window to the front is asked for, never required to prove the
        // app is open: Windows refuses the handoff while a system flyout owns the
        // foreground, and REPAIR1031 lost a whole batch that way with Steam, Discord
        // and Paint visible on screen. A visible window of the bound process is the
        // observation; focus is a courtesy.
        return Observe(requireForeground: true) ?? Observe(requireForeground: false);
    }

    private static InstalledApplicationObservation? Choose(
        IReadOnlyList<InstalledApplicationObservation> observations,
        IReadOnlyList<InstalledApplicationObservation>? baseline = null) =>
        observations
            .Where(static item => item.Visible && Path.IsPathFullyQualified(item.ExecutablePath))
            // File Explorer (APPS1231/005) opens its window inside the already running shell process: the launched
            // thing is a window, so a window absent from the baseline identifies the launch even when its process was
            // already observed. Auditoría D5: with a baseline, a window that was in it is never the launch's.
            .Where(item => baseline is null || !baseline.Any(previous =>
                previous.ProcessId == item.ProcessId
                && previous.ProcessCreationTimeUtcTicks == item.ProcessCreationTimeUtcTicks
                && previous.WindowHandle == item.WindowHandle))
            .OrderByDescending(static item => item.Foreground)
            .ThenByDescending(static item => item.ProcessCreationTimeUtcTicks)
            .FirstOrDefault();

    // cu-v3-elevacion: an opening for BAXY's control never reuses a raised window whose program opens again with the
    // person's rights.
    private IReadOnlyList<InstalledApplicationObservation> Reusable(
        ApplicationOpenRequest request,
        IReadOnlyList<InstalledApplicationObservation> observations) =>
        request.ForControl
            ? [.. observations.Where(item => !_platform.RaisedButReopensUnraised(item.ProcessId))]
            : observations;

    private static ApplicationOpenResult Success(
        ApplicationOpenRequest request,
        InstalledApplicationEntry entry,
        InstalledApplicationObservation observation,
        bool reused,
        bool windowsActivation = false,
        bool frontRestored = false,
        bool newDocument = false,
        bool shownWithoutFocus = false)
    {
        // M132: a click that follows this opening acts on the application opened (VisibleControlSurface).
        External.VisibleControlSurface.NoteOpened(observation.ProcessId, launched: !reused, observation.WindowHandle);
        var receipt = new ApplicationLaunchReceipt(
            request.InvocationId,
            request.ApplicationId,
            LaunchIssued: !reused,
            ReusedExisting: reused,
            observation.ProcessId,
            observation.ProcessCreationTimeUtcTicks,
            observation.ExecutablePath,
            PackageFamilyName: null,
            PackageFullName: null,
            observation.WindowHandle,
            ErrorCode: null);
        return new ApplicationOpenResult(
            Succeeded: true,
            Verified: true,
            entry.Name,
            AlreadyRunning: reused,
            observation.ProcessId,
            observation.WindowHandle,
            ErrorCode: null,
            receipt,
            windowsActivation,
            frontRestored,
            newDocument,
            shownWithoutFocus);
    }

    private static ApplicationOpenResult Failure(
        ApplicationOpenRequest request,
        string displayName,
        string errorCode,
        bool launchIssued = false,
        bool reusedExisting = false,
        IReadOnlyList<string>? candidates = null)
    {
        var receipt = new ApplicationLaunchReceipt(
            request.InvocationId,
            request.ApplicationId,
            launchIssued,
            reusedExisting,
            ProcessId: null,
            ProcessCreationTimeUtcTicks: null,
            ExecutablePath: null,
            PackageFamilyName: null,
            PackageFullName: null,
            WindowHandle: null,
            errorCode);
        return new ApplicationOpenResult(
            Succeeded: launchIssued || reusedExisting,
            Verified: false,
            displayName,
            AlreadyRunning: reusedExisting,
            ProcessId: null,
            WindowHandle: null,
            errorCode,
            receipt,
            Candidates: candidates);
    }
}

internal sealed record InstalledApplicationEntry(
    string Name,
    string AppUserModelId,
    string? TargetPath = null,
    string? TargetArguments = null);

internal sealed record InstalledApplicationObservation(
    int ProcessId,
    long ProcessCreationTimeUtcTicks,
    string ExecutablePath,
    long WindowHandle,
    bool Visible,
    bool Foreground,
    string? ProcessName = null);

internal interface IInstalledApplicationPlatform : IOpeningFront
{
    ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
        CancellationToken cancellationToken);

    IReadOnlyList<InstalledApplicationObservation> Inventory(InstalledApplicationEntry entry);

    IReadOnlyList<InstalledApplicationObservation> InventoryForWindowResolution(
        InstalledApplicationEntry entry,
        CancellationToken cancellationToken) =>
        throw new ApplicationInventoryException("Strong application window identity is unavailable.");

    bool Activate(InstalledApplicationEntry entry);

    // forControl: the application starts with the person's own rights (ApplicationOpenRequest.ForControl).
    bool Activate(InstalledApplicationEntry entry, bool forControl) => Activate(entry);

    // Whether the process runs as administrator (above BAXY) and its program would open again with the person's
    // rights (InvokerLaunch.ManifestElevation.ReopensUnraised).
    bool RaisedButReopensUnraised(int processId) => false;

    // cu-v3-abrir-archivo: the application opens the file at the full path, handed by the shell (NotListed: Windows
    // does not list it for that type; Refused: listed, and the shell did not hand it the file).
    FileActivation.Outcome ActivateForFile(InstalledApplicationEntry entry, string filePath) =>
        FileActivation.Outcome.NotListed;

    void RequestForeground(long windowHandle);

    // cu-v3-documento-nuevo: the application's New command (Ctrl+N) given to this window inside a burst of the foreground
    // lease (after the person's pause with no modifier down, while this window holds the front, the front handed back
    // right after); whether Windows took every key. False when the burst was refused or the person acted: nothing is
    // sent.
    ValueTask<bool> IssueNewDocumentAsync(long windowHandle, CancellationToken cancellationToken) =>
        ValueTask.FromResult(false);

    // The window's title as Windows has it (empty when it has none or is gone).
    string WindowTitle(long windowHandle) => string.Empty;

    // Whether another window owns this one (a dialog of the application).
    bool IsOwnedWindow(long windowHandle) => false;

    // The window in front now, whether the person works in a window, and the opened one shown above theirs without
    // the activation: IOpeningFront (r20b palanca 4).

    int WindowProcessId(long windowHandle) => 0;

    // Whether a window of «process» is the opened application's («opened»): its process, one it started, or another
    // process of the same program (a packaged application may show its window from another process of its own).
    bool SameApplication(int opened, int process) => opened > 0 && opened == process;

    // What the hand-back guard compares against: BAXY taking the front on purpose, the person's last input.
    ForegroundHandBack.GuardStamp FrontGuardStamp() => default;

    bool FrontGuardInterrupted(ForegroundHandBack.GuardStamp stamp) => false;

    // The opening left the person's window in front: the looks while the application starts keep it there.
    void NoteOpening(long previousFront, int processId)
    {
    }

    // A new opening: the previous one no longer hands back a front (v3 point 1 review).
    void ForgetOpening()
    {
    }

    // The front goes back to «previous» and the opened window right behind it, without activating it; whether the
    // front is back.
    bool ReturnForeground(long previous, long opened) => false;

    // As ReturnForeground, given up once «late» is cancelled (the hand-back ran past its budget: r4a M4).
    bool ReturnForeground(long previous, long opened, CancellationToken late) =>
        !late.IsCancellationRequested && ReturnForeground(previous, opened);

    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
}

// Candidates: with no entry of that name, the installed names closest to it (auditoría D1), for the model to name one
// exactly; nothing is opened for them.
internal sealed record InstalledApplicationResolution(
    InstalledApplicationEntry? Entry,
    bool Ambiguous,
    IReadOnlyList<string>? Candidates = null);

internal static class InstalledApplicationResolver
{
    // How many of the closest installed names a name that matches none gets back.
    private const int CandidateCount = 5;

    // Auditoría D1: the application is the catalog entry of exactly that name, folded (case, accents, punctuation);
    // «Motion» is never Notion. Without one, nothing is resolved and the closest names are only said.
    internal static InstalledApplicationResolution Resolve(
        string query,
        IReadOnlyList<InstalledApplicationEntry> catalog)
    {
        string normalizedQuery = Normalize(query);
        if (normalizedQuery.Length == 0)
        {
            return new InstalledApplicationResolution(null, false);
        }

        InstalledApplicationEntry[] entries = catalog
            .Where(static item => IsUsable(item))
            .DistinctBy(static item => (Normalize(item.Name), item.AppUserModelId),
                EqualityComparer<(string, string)>.Default)
            .ToArray();
        InstalledApplicationEntry[] exact = entries
            .Where(item => Normalize(item.Name) == normalizedQuery)
            .ToArray();
        if (exact.Length == 1)
        {
            return new InstalledApplicationResolution(exact[0], false);
        }

        if (exact.Length > 1)
        {
            return exact.Select(static item => item.AppUserModelId).Distinct(StringComparer.Ordinal).Count() == 1
                ? new InstalledApplicationResolution(exact[0], false)
                : new InstalledApplicationResolution(null, true);
        }

        // Closest first: the names that hold every word asked, then by edit distance.
        string[] words = normalizedQuery.Split(' ');
        string[] closest = [.. entries
            .Select(item => item.Name.Trim())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(name => words.All(Normalize(name).Split(' ').Contains) ? 0 : 1)
            .ThenBy(name => Levenshtein(normalizedQuery, Normalize(name)))
            .ThenBy(static name => name, StringComparer.OrdinalIgnoreCase)
            .Take(CandidateCount)];
        return new InstalledApplicationResolution(null, false, closest);
    }

    internal static string Normalize(string value)
    {
        var builder = new StringBuilder(value.Length);
        bool previousSpace = true;
        foreach (char character in value.Normalize(NormalizationForm.FormD))
        {
            UnicodeCategory category = CharUnicodeInfo.GetUnicodeCategory(character);
            if (category == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsLetterOrDigit(character))
            {
                builder.Append(char.ToLowerInvariant(character));
                previousSpace = false;
            }
            else if (!previousSpace)
            {
                builder.Append(' ');
                previousSpace = true;
            }
        }

        return builder.ToString().Trim();
    }

    internal static bool IsUsable(InstalledApplicationEntry entry) =>
        ApplicationIds.IsValidRequest(entry.Name)
        && !string.IsNullOrWhiteSpace(entry.AppUserModelId)
        && entry.AppUserModelId.Length <= 2_048
        && !entry.AppUserModelId.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
        && !entry.AppUserModelId.StartsWith("https://", StringComparison.OrdinalIgnoreCase)
        && !entry.AppUserModelId.Contains('\uFFFD', StringComparison.Ordinal)
        && !entry.AppUserModelId.Any(char.IsControl);

    // Only orders the names a failed resolution says; it never chooses an application.
    private static int Levenshtein(string left, string right)
    {
        int[] previous = Enumerable.Range(0, right.Length + 1).ToArray();
        int[] current = new int[right.Length + 1];
        for (int leftIndex = 1; leftIndex <= left.Length; leftIndex++)
        {
            current[0] = leftIndex;
            for (int rightIndex = 1; rightIndex <= right.Length; rightIndex++)
            {
                int substitution = previous[rightIndex - 1]
                    + (left[leftIndex - 1] == right[rightIndex - 1] ? 0 : 1);
                current[rightIndex] = Math.Min(
                    Math.Min(current[rightIndex - 1] + 1, previous[rightIndex] + 1),
                    substitution);
            }

            (previous, current) = (current, previous);
        }

        return previous[right.Length];
    }
}

internal sealed partial class WindowsInstalledApplicationPlatform : IInstalledApplicationPlatform
{
    private static readonly Encoding StrictUtf8 =
        new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true);
    private const string CatalogScript = """
        $ErrorActionPreference='Stop'
        $utf8=[System.Text.UTF8Encoding]::new($false)
        [Console]::OutputEncoding=$utf8; $OutputEncoding=$utf8
        $shell=$null; $folder=$null
        try {
            $shell=New-Object -ComObject Shell.Application
            $folder=$shell.NameSpace('shell:AppsFolder')
            if ($null -eq $folder) { throw 'The application namespace is unavailable.' }
            $apps=@(foreach ($item in $folder.Items()) {
                [pscustomobject]@{ Name=$item.Name; AppID=$item.Path; ShellItem=$item }
            })
            $duplicateIds=@{}
            $apps | Group-Object Name | Where-Object Count -GT 1 | ForEach-Object {
                $_.Group | ForEach-Object { $duplicateIds[$_.AppID]=$true }
            }
            $targets=@{}
            $arguments=@{}
            try {
                foreach ($app in $apps) {
                    # Classic entries need their Shell target to establish a strong
                    # executable identity (CLOSE1219: «Chrome» is an AppID, not a path).
                    if ($duplicateIds.ContainsKey($app.AppID) -or ($app.AppID -notmatch '!')) {
                        try {
                            $targets[$app.AppID]=$app.ShellItem.ExtendedProperty('System.Link.TargetParsingPath')
                            # v3 r5a M5: the shortcut's own arguments, for a program started without the shell.
                            if ($app.AppID -notmatch '!') {
                                $arguments[$app.AppID]=$app.ShellItem.ExtendedProperty('System.Link.Arguments')
                            }
                        } catch {
                            # One unreadable target must not erase the others.
                        }
                    }
                }
            } catch {
                # Missing Shell metadata preserves the original ambiguity.
                $targets=@{}
                $arguments=@{}
            }
            @($apps | ForEach-Object {
                [pscustomobject]@{ Name=$_.Name; AppID=$_.AppID; TargetPath=$targets[$_.AppID]; TargetArguments=$arguments[$_.AppID] }
            }) | ConvertTo-Json -Compress
        } finally {
            if ($null -ne $folder) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($folder) }
            if ($null -ne $shell) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell) }
        }
        """;

    public async ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
        CancellationToken cancellationToken)
    {
        string executable = Path.Combine(
            Environment.SystemDirectory,
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe");
        var startInfo = new ProcessStartInfo(executable)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = StrictUtf8,
            StandardErrorEncoding = StrictUtf8,
        };
        startInfo.ArgumentList.Add("-NoLogo");
        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-NonInteractive");
        startInfo.ArgumentList.Add("-Command");
        startInfo.ArgumentList.Add(CatalogScript);
        using Process process = Process.Start(startInfo)
            ?? throw new InvalidOperationException("PowerShell could not start.");
        Task<string> outputTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        Task<string> errorTask = process.StandardError.ReadToEndAsync(cancellationToken);
        try
        {
            await process.WaitForExitAsync(cancellationToken).ConfigureAwait(false);
        }
        catch
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                process.WaitForExit();
            }

            throw;
        }
        string[] streams;
        try
        {
            streams = await Task.WhenAll(outputTask, errorTask).ConfigureAwait(false);
        }
        catch (DecoderFallbackException exception)
        {
            throw new InvalidDataException(
                "The application catalog did not emit valid UTF-8.",
                exception);
        }

        string output = streams[0];
        string error = streams[1];
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(error) ? "The application catalog failed." : error.Trim());
        }

        if (string.IsNullOrWhiteSpace(output))
        {
            return [];
        }

        if (output.Contains('\uFFFD', StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "The application catalog emitted a Unicode replacement character.");
        }

        using JsonDocument document = JsonDocument.Parse(output);
        IEnumerable<JsonElement> items = document.RootElement.ValueKind == JsonValueKind.Array
            ? document.RootElement.EnumerateArray()
            : [document.RootElement];
        var entries = new List<InstalledApplicationEntry>();
        foreach (JsonElement item in items)
        {
            if (item.ValueKind != JsonValueKind.Object
                || !item.TryGetProperty("Name", out JsonElement nameElement)
                || !item.TryGetProperty("AppID", out JsonElement appIdElement)
                || nameElement.ValueKind != JsonValueKind.String
                || appIdElement.ValueKind != JsonValueKind.String)
            {
                continue;
            }

            string? name = nameElement.GetString();
            string? appId = appIdElement.GetString();
            if (name is not null && appId is not null)
            {
                string? targetPath = item.TryGetProperty("TargetPath", out JsonElement targetElement)
                    && targetElement.ValueKind == JsonValueKind.String
                    ? targetElement.GetString()
                    : null;
                string? targetArguments = item.TryGetProperty("TargetArguments", out JsonElement argumentsElement)
                    && argumentsElement.ValueKind == JsonValueKind.String
                    && !string.IsNullOrWhiteSpace(argumentsElement.GetString())
                    ? argumentsElement.GetString()
                    : null;
                entries.Add(new InstalledApplicationEntry(name, appId, targetPath, targetArguments));
            }
        }

        return ResolveMissingDuplicateTargets(entries, ReadLocalExecutableState);
    }

    internal static IReadOnlyList<InstalledApplicationEntry> ResolveMissingDuplicateTargets(
        IReadOnlyList<InstalledApplicationEntry> entries,
        Func<string?, bool?> targetExists)
    {
        var retained = new List<InstalledApplicationEntry>();
        foreach (IGrouping<string, InstalledApplicationEntry> group in entries
            .GroupBy(static entry => InstalledApplicationResolver.Normalize(entry.Name), StringComparer.Ordinal))
        {
            InstalledApplicationEntry[] candidates = group.ToArray();
            if (candidates.Select(static entry => entry.AppUserModelId)
                .Distinct(StringComparer.Ordinal).Count() <= 1)
            {
                retained.AddRange(candidates);
                continue;
            }

            var observed = candidates.Select(entry => (Entry: entry, Exists: targetExists(entry.TargetPath)))
                .ToArray();
            string[] existingIdentities = observed.Where(static item => item.Exists == true)
                .Select(static item => item.Entry.AppUserModelId).Distinct(StringComparer.Ordinal).ToArray();
            if (existingIdentities.Length == 1 && observed.All(item =>
                item.Entry.AppUserModelId == existingIdentities[0] || item.Exists == false))
            {
                retained.AddRange(candidates.Where(entry => entry.AppUserModelId == existingIdentities[0]));
            }
            else
            {
                retained.AddRange(candidates);
            }
        }

        return retained;
    }

    internal static bool? ReadLocalExecutableState(string? targetPath)
    {
        // A missing file is evidence; an unreadable, remote or unspecified target is not.
        try
        {
            if (string.IsNullOrWhiteSpace(targetPath)
                || !Path.IsPathFullyQualified(targetPath)
                || Path.GetPathRoot(targetPath)?.Length != 3
                || !string.Equals(Path.GetExtension(targetPath), ".exe", StringComparison.OrdinalIgnoreCase)
                || !Directory.Exists(Path.GetPathRoot(targetPath)))
            {
                return null;
            }

            FileAttributes attributes = File.GetAttributes(targetPath);
            return (attributes & FileAttributes.Directory) == 0 ? true : null;
        }
        catch (FileNotFoundException)
        {
            return false;
        }
        catch (DirectoryNotFoundException)
        {
            return false;
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or ArgumentException or NotSupportedException)
        {
            return null;
        }
    }

    public IReadOnlyList<InstalledApplicationObservation> Inventory(
        InstalledApplicationEntry entry) =>
        Inventory(entry, strongIdentityOnly: false, CancellationToken.None);

    public IReadOnlyList<InstalledApplicationObservation> InventoryForWindowResolution(
        InstalledApplicationEntry entry,
        CancellationToken cancellationToken) =>
        Inventory(entry, strongIdentityOnly: true, cancellationToken);

    private static bool ProcessHasExited(Process process)
    {
        try
        {
            return process.HasExited;
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
            // An unreadable state is not proof of exit; the inventory stays strict.
            return false;
        }
    }

    private static List<InstalledApplicationObservation> Inventory(
        InstalledApplicationEntry entry,
        bool strongIdentityOnly,
        CancellationToken cancellationToken)
    {
        bool packaged = entry.AppUserModelId.Contains('!');
        // The shell's own catalog entry: its windows live in explorer.exe, which
        // also owns the desktop and taskbar. Only file-browsing windows
        // (CabinetWClass) count as the application being open (APPS1231/005).
        bool shellExplorer = !packaged && string.Equals(
            entry.AppUserModelId, ShellExplorerAppUserModelId, StringComparison.Ordinal);
        string? expectedExecutable = strongIdentityOnly && !packaged
            ? StrongExecutablePath(entry) : null;
        if (strongIdentityOnly && !packaged && expectedExecutable is null)
            throw new ApplicationInventoryException("The installed executable identity is unavailable.");
        Process[] processes = Process.GetProcesses();
        var observations = new List<InstalledApplicationObservation>();
        Dictionary<uint, nint>? hostedFrames = null;
        try
        {
            foreach (Process process in processes)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    process.Refresh();
                    // A foreign window being destroyed (Chrome tearing down after a
                    // close, CLOSE1223/009) has no readable rectangle; only the
                    // candidate's enumeration must be complete.
                    nint[]? ownedWindows = strongIdentityOnly
                        ? VisibleTopLevelWindows(process.Id, requireComplete: false)
                        : shellExplorer
                            ? VisibleTopLevelWindows(process.Id, requireComplete: false, ExplorerWindowClass)
                            : null;
                    nint window = ownedWindows is null
                        ? process.MainWindowHandle : ownedWindows.FirstOrDefault();
                    // Computer use (CU1959, measured on Configuración): a packaged
                    // app suspended in the background keeps a «visible» CoreWindow
                    // that DWM cloaks; nobody sees it, so it is not a running window
                    // to reuse — the launch below activates the app and its frame.
                    bool usable = window != 0 && IsWindowVisible(window) && !IsCloaked(window);
                    nint frame = 0;
                    if (!usable && packaged && !strongIdentityOnly)
                    {
                        // Computer use (smoke run: app.open of a packaged app spent its whole
                        // 30 s budget with the app on screen): a UWP app has no top-level
                        // window of its own; the visible ApplicationFrameHost frame hosting
                        // its process is what the person sees, so opening is verified there.
                        hostedFrames ??= External.VisibleControlSurface.HostedFrames();
                        usable = hostedFrames.TryGetValue(unchecked((uint)process.Id), out frame);
                    }

                    if (!usable)
                    {
                        continue;
                    }

                    if (strongIdentityOnly && !packaged && !string.Equals(
                            process.ProcessName,
                            Path.GetFileNameWithoutExtension(expectedExecutable),
                            StringComparison.OrdinalIgnoreCase))
                    {
                        // A windowed process of another executable cannot be this
                        // classic application; reading its main module (elevated
                        // Task Manager, CLOSE1221) must not abort the inventory.
                        continue;
                    }

                    string? applicationId = null;
                    if (packaged && !TryReadPackagedIdentity(
                            () => ReadApplicationUserModelId(process.Id), strongIdentityOnly, out applicationId))
                    {
                        // An unreadable foreign process is not a candidate for
                        // this package; only candidates need a strong identity.
                        continue;
                    }
                    if (strongIdentityOnly
                        ? packaged && !string.Equals(entry.AppUserModelId, applicationId, StringComparison.Ordinal)
                        : !WindowProcessIdentifiesApplication(
                            entry, process.ProcessName, process.MainWindowTitle, applicationId))
                    {
                        continue;
                    }

                    string? executablePath = ExecutableImagePath(process.Id);
                    if (string.IsNullOrWhiteSpace(executablePath)
                        || !Path.IsPathFullyQualified(executablePath))
                    {
                        if (strongIdentityOnly)
                            throw new ApplicationInventoryException("A visible executable could not be verified.");
                        continue;
                    }
                    if (strongIdentityOnly)
                    {
                        // The candidate's own window set must be complete and stable.
                        ownedWindows = VisibleTopLevelWindows(process.Id, requireComplete: true);
                        if (ownedWindows.Length == 0)
                            continue;
                    }
                    if (strongIdentityOnly && !packaged
                        && !ExecutableIsLaunchedImage(Path.GetFullPath(executablePath), expectedExecutable!))
                        continue;

                    long creationTime = process.StartTime.ToUniversalTime().Ticks;
                    foreach (nint operated in ownedWindows ?? (frame != 0 ? [frame] : VisibleTopLevelWindows(process.Id)))
                    {
                        observations.Add(new InstalledApplicationObservation(
                            process.Id,
                            creationTime,
                            executablePath,
                            operated.ToInt64(),
                            Visible: true,
                            Foreground: GetForegroundWindow() == operated,
                            ProcessName: strongIdentityOnly ? process.ProcessName : null));
                    }
                    if (strongIdentityOnly && packaged
                        && !string.Equals(entry.AppUserModelId,
                            ReadApplicationUserModelId(process.Id), StringComparison.Ordinal))
                        throw new ApplicationInventoryException("The application identity changed during enumeration.");
                }
                catch (Exception exception) when (exception is InvalidOperationException
                    or System.ComponentModel.Win32Exception
                    or NotSupportedException)
                {
                    // A foreign process that exits between GetProcesses and its
                    // reads (WhatsApp's background task server respawning,
                    // CLOSE1649/001) owns no visible window any more; only a
                    // live process can leave the candidate's inventory incomplete.
                    if (strongIdentityOnly && !ProcessHasExited(process))
                        throw new ApplicationInventoryException("The visible application inventory was incomplete.");
                }
            }

            if (strongIdentityOnly)
            {
                // A UWP app's CoreWindow is not a visible top-level window: the
                // ApplicationFrameHost frame that hosts it is what the person sees
                // and what closing acts on (CLOSE1219: Calculadora → window_not_found).
                // The hosted process is identified by its AUMID through the frame's
                // child window; the observation carries the frame host's identity.
                KeepOwnWindows(
                    observations,
                    static window => GetWindow(checked((nint)window), 4) != 0,
                    packaged ? found => AddHostedFrameWindows(entry, processes, found, cancellationToken) : null);
            }
        }
        finally
        {
            foreach (Process process in processes)
            {
                process.Dispose();
            }
        }

        return observations;
    }

    /// <summary>
    /// r27u (tandas v3b1 y r23q, t2-c04 t5 «cierra configuracion porfa»: window.resolve gave only SystemSettings'
    /// 71×41 «Host de ventanas emergentes», app.close closed it and Configuración was told closed while its frame
    /// stayed): a window another window owns (GW_OWNER: a popup host, a tooltip, a dialog) is never the application's
    /// window; it goes with its owner. With none of its own left, a packaged application's hosting frames are looked
    /// for, and an application seen only through owned windows resolves no window (window_not_found).
    /// </summary>
    internal static void KeepOwnWindows(
        List<InstalledApplicationObservation> observations,
        Func<long, bool> ownedByAnotherWindow,
        Action<List<InstalledApplicationObservation>>? addHostingFrames)
    {
        observations.RemoveAll(item => ownedByAnotherWindow(item.WindowHandle));
        if (observations.Count == 0)
        {
            addHostingFrames?.Invoke(observations);
        }
    }

    /// <summary>
    /// The package identity of a visible process. M93 (DEV-D v3u D-s119 «Abrir la app de photos.», D-w11-t5 «¿Me abres
    /// el Spotify?»): both packaged apps ended in inventory_failed in about a second, while the Calculator (its own
    /// provider) and an unknown app were answered; one visible process whose identity could not be read aborted the
    /// whole open inventory. For opening, an unreadable process keeps no identity and is judged by its name and title
    /// like a classic one (false keeps the old skip of the strong inventory that closing and window resolution use).
    /// </summary>
    internal static bool TryReadPackagedIdentity(
        Func<string?> read, bool strongIdentityOnly, out string? applicationId)
    {
        try
        {
            applicationId = read();
            return true;
        }
        catch (ApplicationInventoryException)
        {
            applicationId = null;
            return !strongIdentityOnly;
        }
    }

    private static void AddHostedFrameWindows(
        InstalledApplicationEntry entry,
        Process[] processes,
        List<InstalledApplicationObservation> observations,
        CancellationToken cancellationToken)
    {
        foreach (Process host in processes)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                if (!string.Equals(host.ProcessName, "ApplicationFrameHost", StringComparison.OrdinalIgnoreCase))
                    continue;
                nint[] frames = VisibleTopLevelWindows(host.Id, requireComplete: false);
                if (frames.Length == 0)
                    continue;
                string? hostExecutable = host.MainModule?.FileName;
                if (string.IsNullOrWhiteSpace(hostExecutable) || !Path.IsPathFullyQualified(hostExecutable))
                    throw new ApplicationInventoryException("The frame host executable could not be verified.");
                long hostCreation = host.StartTime.ToUniversalTime().Ticks;
                foreach (nint frame in frames)
                {
                    int? hosted = HostedProcessId(frame, host.Id);
                    if (hosted is null)
                        continue;
                    string? hostedId;
                    try
                    {
                        hostedId = ReadApplicationUserModelId(hosted.Value);
                    }
                    catch (ApplicationInventoryException)
                    {
                        // A frame whose hosted process cannot be opened (it exited
                        // or is protected) hosts a foreign application, never this
                        // packaged candidate; the candidate's own frames stay strict.
                        continue;
                    }
                    if (!string.Equals(entry.AppUserModelId, hostedId, StringComparison.Ordinal))
                        continue;
                    observations.Add(new InstalledApplicationObservation(
                        host.Id,
                        hostCreation,
                        hostExecutable,
                        frame.ToInt64(),
                        Visible: true,
                        Foreground: GetForegroundWindow() == frame,
                        ProcessName: host.ProcessName));
                }
            }
            catch (Exception exception) when (exception is InvalidOperationException
                or System.ComponentModel.Win32Exception
                or NotSupportedException)
            {
                // CLOSE1649/CLOSE1651 «cierra whatsapp» (inventory_failed, reproduced
                // by the root probe in 4 of 12 rounds): a process from the snapshot
                // that exited before its name was read is not a frame host.
                if (!ProcessHasExited(host))
                    throw new ApplicationInventoryException("The hosted application inventory was incomplete.");
            }
        }
    }

    private static int? HostedProcessId(nint frame, int hostProcessId)
    {
        int? hosted = null;
        EnumWindowsProc callback = (child, _) =>
        {
            GetWindowThreadProcessId(child, out uint owner);
            if (owner != 0 && owner != unchecked((uint)hostProcessId))
            {
                hosted = checked((int)owner);
                return false;
            }
            return true;
        };
        _ = EnumChildWindows(frame, callback, nint.Zero);
        return hosted;
    }

    private static readonly System.Text.RegularExpressions.Regex VersionedFolder = new(
        @"^(?:[A-Za-z]+[-_])?v?\d+(?:\.\d+){1,3}$",
        System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    /// <summary>
    /// The running image is the shortcut's executable, or the same file name in a
    /// direct versioned subfolder of the shortcut's folder: self-updating
    /// installers put a launcher next to <c>app-1.0.9260\</c> and the window
    /// belongs to the copy inside (t4-r6: «cierra discord» → window_not_found).
    /// A same-named executable anywhere else is a different program.
    /// </summary>
    internal static bool ExecutableIsLaunchedImage(string actualPath, string expectedPath)
    {
        if (string.Equals(actualPath, expectedPath, StringComparison.OrdinalIgnoreCase))
            return true;
        if (!string.Equals(Path.GetFileName(actualPath), Path.GetFileName(expectedPath),
                StringComparison.OrdinalIgnoreCase))
            return false;
        string? versioned = Path.GetDirectoryName(actualPath);
        string? launcherFolder = Path.GetDirectoryName(expectedPath);
        if (versioned is null || launcherFolder is null)
            return false;
        return string.Equals(Path.GetDirectoryName(versioned), launcherFolder, StringComparison.OrdinalIgnoreCase)
            && VersionedFolder.IsMatch(Path.GetFileName(versioned));
    }

    internal static string? StrongExecutablePath(InstalledApplicationEntry entry)
    {
        // Shell-supplied executable paths only. No display-name/process-name
        // inference, prefix match, title fallback, shortcut or command line.
        foreach (string? value in new[] { entry.TargetPath, entry.AppUserModelId })
        {
            if (string.IsNullOrWhiteSpace(value) || !Path.IsPathFullyQualified(value)
                || !string.Equals(Path.GetExtension(value), ".exe", StringComparison.OrdinalIgnoreCase))
                continue;
            try
            {
                return Path.GetFullPath(value);
            }
            catch (Exception exception) when (exception is ArgumentException or NotSupportedException)
            {
                return null;
            }
        }
        return null;
    }

    internal static bool WindowProcessIdentifiesApplication(
        InstalledApplicationEntry entry,
        string processName,
        string windowTitle,
        string? observedApplicationId)
    {
        if (entry.AppUserModelId.Contains('!'))
        {
            // The OS identity is independent of the localized display name,
            // executable name and document title. A different package (or an
            // unidentified process) cannot satisfy this catalog application.
            return string.Equals(
                entry.AppUserModelId, observedApplicationId, StringComparison.Ordinal);
        }

        string normalizedProcessName = InstalledApplicationResolver.Normalize(processName);
        if (string.Equals(entry.AppUserModelId, ShellExplorerAppUserModelId, StringComparison.Ordinal))
        {
            // File Explorer windows are titled «<folder> - Explorador de archivos»:
            // the application name is a suffix, never the prefix the title rule
            // expects, and the catalog id carries no executable. The process is
            // the identity (APPS1235/000: verification_failed with the window
            // on screen).
            return string.Equals(normalizedProcessName, "explorer", StringComparison.Ordinal);
        }
        return BuildProcessIdentities(entry).Any(identity =>
                normalizedProcessName == identity
                || (identity.Length >= 4
                    && normalizedProcessName.StartsWith(identity, StringComparison.Ordinal)))
            || WindowTitleIdentifiesApplication(
                InstalledApplicationResolver.Normalize(windowTitle),
                InstalledApplicationResolver.Normalize(entry.Name));
    }

    private static string? ReadApplicationUserModelId(int processId)
    {
        using SafeProcessHandle handle = OpenProcess(0x1000, false, processId);
        if (handle.IsInvalid)
        {
            throw new ApplicationInventoryException(
                "The visible process application identity could not be opened.");
        }

        uint length = 0;
        int result = GetApplicationUserModelId(handle, ref length, 0);
        if (result == 15703) // APPMODEL_ERROR_NO_APPLICATION: classic desktop process.
            return null;
        if (result != 122 || length is 0 or > 1024)
        {
            throw new ApplicationInventoryException(
                "The visible process application identity could not be sized.");
        }

        nint buffer = Marshal.AllocHGlobal(checked((int)length * sizeof(char)));
        try
        {
            if (GetApplicationUserModelId(handle, ref length, buffer) != 0)
            {
                throw new ApplicationInventoryException(
                    "The visible process application identity could not be read.");
            }
            return Marshal.PtrToStringUni(buffer);
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    /// <summary>
    /// The executable of a process, read with the least access Windows grants on any process. Computer use v2-s06
    /// («en el Administrador de tareas andá a Rendimiento»): Task Manager runs elevated, so reading its main module
    /// was refused, its visible window never counted as the application and app.open polled its whole 30 s budget
    /// with the window on screen. The limited query answers for an elevated window too: found is opened, and what
    /// can be done there is the view's to say (VisibleControlSurface.RunsAboveUs).
    /// </summary>
    internal static unsafe string? ExecutableImagePath(int processId)
    {
        using SafeProcessHandle handle = OpenProcess(0x1000, false, processId);
        if (handle.IsInvalid)
            return null;
        const int capacity = 1024;
        char* buffer = stackalloc char[capacity];
        uint length = capacity;
        return QueryFullProcessImageName(handle, 0, buffer, ref length) && length is > 0 and < capacity
            ? new string(buffer, 0, (int)length)
            : null;
    }

    // Two processes of one program (the same executable image).
    private static bool SameProgram(int first, int second) =>
        ExecutableImagePath(first) is { } one && ExecutableImagePath(second) is { } other
        && string.Equals(one, other, StringComparison.OrdinalIgnoreCase);

    public bool Activate(InstalledApplicationEntry entry) => Activate(entry, forControl: false);

    public bool RaisedButReopensUnraised(int processId) =>
        External.VisibleControlSurface.RunsAboveUs(processId) && InvokerLaunch.WindowReopensUnraised(processId);

    public bool Activate(InstalledApplicationEntry entry, bool forControl)
    {
        // v3 r5a M5: a program Windows would raise to administrator unasked starts with the person's own rights
        // (forControl). cu-v3-elevacion: every opening carries it unless the person asked for administrator rights
        // (MindArgumentNormalization); measured live on r9 (v3-23, v3-65), a console opened through the shell came up
        // as administrator and the next turn could neither read nor press it. A start that fails (the job refuses the
        // breakaway) falls back to the shell's path: an elevated window is an honest limit.
        if (forControl
            && InvokerLaunch.Plan(entry, File.Exists, InvokerLaunch.AssociatedCommand, InvokerLaunch.ReadManifest)
                is { } invoker
            && InvokerLaunch.Start(invoker))
        {
            return true;
        }

        string explorer = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "explorer.exe");
        var startInfo = new ProcessStartInfo(explorer)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        startInfo.ArgumentList.Add($"shell:AppsFolder\\{entry.AppUserModelId}");
        using Process? process = Process.Start(startInfo);
        return process is not null;
    }

    // cu-v3-abrir-archivo: a packaged application gets the file through its «Abrir con» handler (the one the shell
    // itself invokes; cu-v3-archivo-empaquetado: the activation manager refused them all); any other through its own
    // executable with the path as its one argument. Neither sends a key. Only an application Windows lists to open
    // files of that type gets one (review, finding 1: an interpreter or an uninstaller from the Start catalog would run
    // a «.txt» as code or act on it).
    public FileActivation.Outcome ActivateForFile(InstalledApplicationEntry entry, string filePath)
    {
        string? executable = StrongExecutablePath(entry);
        (FileActivation.HandOff handOff, bool invoked) = FileActivation.HandTo(entry, executable, filePath);
        if (handOff == FileActivation.HandOff.Package)
            return invoked ? FileActivation.Outcome.Issued : FileActivation.Outcome.Refused;
        if (handOff != FileActivation.HandOff.Executable)
            return FileActivation.Outcome.NotListed;
        if (executable is null || !File.Exists(executable))
            return FileActivation.Outcome.Refused;
        var startInfo = new ProcessStartInfo(executable) { UseShellExecute = false };
        startInfo.ArgumentList.Add(filePath);
        using Process? process = Process.Start(startInfo);
        return process is not null ? FileActivation.Outcome.Issued : FileActivation.Outcome.Refused;
    }

    internal static bool WindowTitleIdentifiesApplication(string windowTitle, string applicationName)
    {
        if (string.IsNullOrWhiteSpace(windowTitle)
            || string.IsNullOrWhiteSpace(applicationName)
            || applicationName.Length < 3)
        {
            return false;
        }

        if (windowTitle == applicationName)
            return true;
        if (!windowTitle.StartsWith(applicationName, StringComparison.Ordinal))
            return false;
        if (windowTitle.Length == applicationName.Length)
            return true;
        char next = windowTitle[applicationName.Length];
        return next is ' ' or '-' or ':' or '|' or '(';
    }

    public long ForegroundWindow() => ForegroundHandBack.Foreground();

    public long PersonWorkingIn(long window) => ForegroundHandBack.PersonWorkingIn(window);

    public bool ShowAboveWithoutActivation(long window, long personWindow) =>
        ForegroundHandBack.ShowAboveWithoutActivation(window, personWindow);

    public int WindowProcessId(long windowHandle) => ForegroundHandBack.ProcessOf(windowHandle);

    public ForegroundHandBack.GuardStamp FrontGuardStamp() => ForegroundHandBack.Stamp();

    public bool FrontGuardInterrupted(ForegroundHandBack.GuardStamp stamp) => ForegroundHandBack.Interrupted(stamp);

    public void NoteOpening(long previousFront, int processId) => ForegroundHandBack.NoteOpening(previousFront, processId);

    public void ForgetOpening() => ForegroundHandBack.ForgetOpening();

    public bool SameApplication(int opened, int process) =>
        opened > 0 && process > 0
        && (opened == process
            || External.VisibleControlSurface.InApplicationFamily(unchecked((uint)opened), unchecked((uint)process))
            || SameProgram(opened, process));

    public bool ReturnForeground(long previous, long opened) => ForegroundHandBack.Return(previous, opened);

    public bool ReturnForeground(long previous, long opened, CancellationToken late) =>
        ForegroundHandBack.Return(previous, opened, late);

    public async ValueTask<bool> IssueNewDocumentAsync(long windowHandle, CancellationToken cancellationToken)
    {
        var keyboard = new External.WindowsDesktopKeyboard();
        nint handle = checked((nint)windowHandle);
        // Review of cu-v3-documento-nuevo (finding 4): as the adapter's keys, after the person's pause (no Shift held:
        // never Ctrl+Shift+N, a folder or a private window), only to this window in front, never once they acted, and
        // the front given back right after.
        External.IInputBurst burst = await keyboard.FrontAsync(handle, cancellationToken).ConfigureAwait(false);
        try
        {
            // Control + N, pressed in order and released in reverse: four events.
            return burst.MayAct && burst.HoldsWindow && keyboard.Holds(handle) && keyboard.PressChord([0x11, 0x4E]) == 4;
        }
        finally
        {
            _ = burst.Restore();
        }
    }

    public bool IsOwnedWindow(long windowHandle) => GetWindow(checked((nint)windowHandle), 4) != 0;

    public unsafe string WindowTitle(long windowHandle)
    {
        const int capacity = 512;
        char* buffer = stackalloc char[capacity];
        int length = GetWindowText(checked((nint)windowHandle), buffer, capacity);
        return length > 0 ? new string(buffer, 0, length) : string.Empty;
    }

    public void RequestForeground(long windowHandle)
    {
        nint handle = checked((nint)windowHandle);
        nint foreground = GetForegroundWindow();
        uint currentThread = GetCurrentThreadId();
        uint foregroundThread = foreground == 0
            ? 0
            : GetWindowThreadProcessId(foreground, out _);
        bool attached = foregroundThread != 0
            && foregroundThread != currentThread
            && AttachThreadInput(currentThread, foregroundThread, attach: true);
        try
        {
            _ = ShowWindowAsync(handle, 9);
            _ = BringWindowToTop(handle);
            _ = SetForegroundWindow(handle);
        }
        finally
        {
            if (attached)
            {
                _ = AttachThreadInput(currentThread, foregroundThread, attach: false);
            }
        }
    }

    public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    private static HashSet<string> BuildProcessIdentities(InstalledApplicationEntry entry)
    {
        var identities = new HashSet<string>(StringComparer.Ordinal);
        foreach (string token in InstalledApplicationResolver.Normalize(entry.Name)
                     .Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
            if (token.Length >= 3 && token is not ("microsoft" or "google" or "app"))
            {
                identities.Add(token);
            }
        }

        foreach (Match match in ExecutableIdentityPattern().Matches(entry.AppUserModelId))
        {
            string identity = InstalledApplicationResolver.Normalize(match.Groups["name"].Value);
            if (identity.Length >= 3)
            {
                identities.Add(identity);
            }
        }

        string simpleAppId = InstalledApplicationResolver.Normalize(entry.AppUserModelId);
        if (!simpleAppId.Contains(' ') && simpleAppId.Length is >= 3 and <= 32)
        {
            identities.Add(simpleAppId);
        }

        return identities;
    }

    private const string ShellExplorerAppUserModelId = "Microsoft.Windows.Explorer";
    private const string ExplorerWindowClass = "CabinetWClass";

    private static nint[] VisibleTopLevelWindows(
        int processId, bool requireComplete = false, string? windowClass = null)
    {
        var windows = new List<(nint Handle, long Area)>();
        bool complete = true;
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window) || IsCloaked(window))
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner != unchecked((uint)processId))
                return true;
            if (windowClass is not null
                && !string.Equals(ReadClassName(window), windowClass, StringComparison.Ordinal))
                return true;
            if (!GetWindowRect(window, out Rect rect))
            {
                complete = false;
                return true;
            }
            long area = (long)Math.Max(0, rect.Right - rect.Left)
                * Math.Max(0, rect.Bottom - rect.Top);
            if (area > 0)
                windows.Add((window, area));
            return true;
        };
        if (!EnumWindows(callback, nint.Zero) || (requireComplete && !complete))
            throw new ApplicationInventoryException("Visible windows could not be enumerated.");
        // Preserve the preferred large window for opening, without discarding
        // other observed handles from the status count or foreground choice.
        return windows.OrderByDescending(item => item.Area)
            .Select(item => item.Handle).ToArray();
    }

    private static unsafe string ReadClassName(nint window)
    {
        const int capacity = 256;
        char* buffer = stackalloc char[capacity];
        int length = GetClassName(window, buffer, capacity);
        return length > 0 ? new string(buffer, 0, length) : string.Empty;
    }

    // GW_OWNER (4): the window that owns this one, 0 for none.
    [LibraryImport("user32.dll")]
    private static partial nint GetWindow(nint window, uint command);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextW")]
    private static unsafe partial int GetWindowText(nint window, char* text, int capacity);

    [LibraryImport("user32.dll", EntryPoint = "GetClassNameW")]
    private static unsafe partial int GetClassName(nint window, char* buffer, int capacity);

    [GeneratedRegex(@"(?<name>[A-Za-z0-9_-]+)\.exe", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex ExecutableIdentityPattern();

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint window, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumChildWindows(nint parent, EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint window, out Rect rect);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial SafeProcessHandle OpenProcess(
        uint desiredAccess, [MarshalAs(UnmanagedType.Bool)] bool inheritHandle, int processId);

    [LibraryImport("kernel32.dll", EntryPoint = "QueryFullProcessImageNameW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static unsafe partial bool QueryFullProcessImageName(
        SafeProcessHandle process, uint flags, char* executablePath, ref uint length);

    [LibraryImport("kernel32.dll")]
    private static partial int GetApplicationUserModelId(
        SafeProcessHandle process, ref uint length, nint applicationUserModelId);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachThreadInput(uint idAttach, uint idAttachTo, [MarshalAs(UnmanagedType.Bool)] bool attach);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool BringWindowToTop(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    // DWMWA_CLOAKED (14): a window the shell hides (a suspended packaged app,
    // a window on another virtual desktop) reports visible and is not.
    private static bool IsCloaked(nint window) =>
        DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0;

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(nint window, int attribute, out int value, int size);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindowAsync(nint window, int command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint window);
}
