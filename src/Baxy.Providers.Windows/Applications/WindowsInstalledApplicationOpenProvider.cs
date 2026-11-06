using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Microsoft.Win32;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Providers.Windows.Applications;

public sealed class WindowsInstalledApplicationOpenProvider :
    IApplicationOpenProvider,
    IApplicationInventoryProvider
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
    // Renew al máximo (velocidad, E014 in pc-lote: 30-32 s each, verification_failed): a packaged application whose
    // frame Windows shows with nothing of it inside (VisibleControlSurface.ShowsEmptyFrame) after this long is not
    // filling it: a splash is filled within it (Configuración opened verified in 1.5-3.8 s on this PC, place included).
    // In polls: the ObservationDelay ones that make it, for a platform whose delay takes no time.
    internal static readonly TimeSpan EmptyFrameGrace = TimeSpan.FromSeconds(10);
    private const int EmptyFrameGraceAttempts = 100;
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
    // BAXY Renew cu (C18): the time a dismissed start screen is given to show the document it leaves.
    internal static readonly TimeSpan DismissSettle = TimeSpan.FromSeconds(4);
    // Ronda 20 P4 (v3-01): how far apart the windows of a cold start are looked at while they settle, and for how long.
    internal static readonly TimeSpan StartSettleDelay = TimeSpan.FromMilliseconds(400);
    internal static readonly TimeSpan StartSettleBudget = TimeSpan.FromSeconds(10);
    // Renew al máximo (w6-settle): how long a start that already showed its main window goes without a window event of
    // the application before one confirming look may end its settle.
    internal static readonly TimeSpan StartEventQuiet = TimeSpan.FromMilliseconds(250);
    // Renew al máximo (nuevo4): the UI Automation part of a New command (a tab strip's reads and press) in all, and what
    // must be left of it to press the strip's add button and read the new tab back.
    internal static readonly TimeSpan TabStripBudget = TimeSpan.FromMilliseconds(1500);
    internal static readonly TimeSpan TabStripPressReserve = TimeSpan.FromMilliseconds(400);

    private readonly IInstalledApplicationPlatform _platform;
    private readonly TimeSpan _catalogReadBudget;
    private readonly TimeProvider _time;
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
        : this(platform, catalogReadBudget, TimeProvider.System)
    {
    }

    // Renew al máximo (6.6): the clock the catalog's age is read on.
    internal WindowsInstalledApplicationOpenProvider(
        IInstalledApplicationPlatform platform,
        TimeSpan catalogReadBudget,
        TimeProvider time)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _catalogReadBudget = catalogReadBudget;
        _time = time ?? throw new ArgumentNullException(nameof(time));
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
        if (!ApplicationIds.IsValidOpening(request.ApplicationId))
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
            catalog = await ReadCatalogAsync(cancellationToken, request.ApplicationId).ConfigureAwait(false);
        }
        // Renew al máximo (B-APP-9): any catalog read that fails (PowerShell blocked from starting, its output broken)
        // is the inventory failure, as for IsInstalledAsync; only a cancellation goes on.
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return Failure(request, request.ApplicationId, ApplicationOpenErrorCodes.InventoryFailed);
        }

        InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(
            request.ApplicationId, catalog, _platform.LocateExecutable);
        if (resolution.Entry is null)
        {
            return Failure(
                request,
                request.ApplicationId,
                resolution.Ambiguous
                    ? ApplicationOpenErrorCodes.ApplicationAmbiguous
                    : ApplicationOpenErrorCodes.ApplicationNotFound,
                candidates: resolution.Candidates,
                nameHolder: resolution.NameHolder);
        }

        InstalledApplicationEntry entry = resolution.Entry;
        // Auditoría final V1: a window is the application's only by the identity Windows gives it (its package, or the
        // executable its shortcut launches); without one nothing is launched, since no window could be verified.
        if (!_platform.IdentifiesWindows(entry))
        {
            return Failure(request, entry.Name, ApplicationOpenErrorCodes.WindowIdentityUnavailable);
        }

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

            // Renew al máximo (B-APP-11): the window to reuse is gone; what follows is a launch, and a window it shows
            // is said already running only when it was there before (the verification below reads it).
            reused = false;
        }

        // v3 point 0 (arreglo 4): an opening the person did not ask to see in front leaves the front where it is.
        // Windows activates some applications by itself (a packaged app through its activation manager, a browser
        // shell that ignores how it was asked to show): the window that had the front gets it back at once.
        // Asked in front, it is also read: a person working in it when the opening ends gets it back (OpeningFront).
        long previousFront = _platform.ForegroundWindow();
        using ILaunchWatch? launch = _platform.WatchLaunch(entry);
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
                // uso-108 C12 (agent-desktop launch.rs:44-68, launch_result.rs:7-14): a process of the launch that ended
                // on a crash code, with nothing of it left, shows no window: the opening ends here, unverified as at 30 s,
                // and says the code (a missing runtime or library reads there).
                if (launch?.CrashCode() is { } crash)
                {
                    return Failure(
                        request,
                        entry.Name,
                        ApplicationOpenErrorCodes.VerificationFailed,
                        launchIssued: !reused,
                        reusedExisting: reused) with { ExitedWithError = $"0x{crash:X8}" };
                }

                // Renew al máximo (velocidad): the application's frame shown empty past the grace is the frame of a
                // process that ended (forced to), which nothing fills: the opening ends here, unverified as at 30 s, and
                // says what it saw (emptyFrame), instead of waiting out the rest of the budget.
                if ((verification.Elapsed >= EmptyFrameGrace || attempt >= EmptyFrameGraceAttempts)
                    && _platform.ShowsEmptyFrame(entry))
                {
                    return Failure(
                        request,
                        entry.Name,
                        ApplicationOpenErrorCodes.VerificationFailed,
                        launchIssued: !reused,
                        reusedExisting: reused) with { EmptyFrame = true };
                }

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
                    _ = GuardFrontAsync(handBackTo, focused, _platform.FrontGuardStamp());
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

    // Renew al máximo (guarda msconfig): the catalog entry the opening would resolve, judged by the program its shortcut
    // runs (VisibleControlSurface.SystemToolLaunch), or a packaged one by its package's own name (Windows Security's).
    // A catalog that cannot be read tells nothing: the opening fails on it.
    public async ValueTask<bool> OpensSystemToolAsync(string applicationId, CancellationToken cancellationToken)
    {
        if (!ApplicationIds.IsValidOpening(applicationId))
        {
            return false;
        }

        IReadOnlyList<InstalledApplicationEntry> catalog;
        try
        {
            catalog = await ReadCatalogAsync(cancellationToken, applicationId).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return false;
        }

        return InstalledApplicationResolver.Resolve(applicationId, catalog, _platform.LocateExecutable).Entry is { } entry
            && OpensSystemTool(entry);
    }

    // Encargo 94: a browser is told by what Windows has registered as one (UserBrowserIdentityResolver), never by its name;
    // registry unread counts as one, since opening a person's session is the worse mistake. Windows unread stay unknown.
    public async ValueTask<InstalledApplicationFacts?> InstalledFactsAsync(string applicationId, CancellationToken cancellationToken)
    {
        if (!ApplicationIds.IsValidOpening(applicationId))
        {
            return null;
        }

        InstalledApplicationEntry? entry;
        try
        {
            entry = InstalledApplicationResolver.Resolve(
                applicationId,
                await ReadCatalogAsync(cancellationToken, applicationId).ConfigureAwait(false),
                _platform.LocateExecutable).Entry;
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return null;
        }

        if (entry is null)
        {
            return null;
        }

        IReadOnlyList<long>? windows;
        try
        {
            windows = _platform.IdentifiesWindows(entry)
                ? [.. _platform.Inventory(entry).Select(static item => item.WindowHandle)]
                : null;
        }
        catch (Exception exception) when (exception is ApplicationInventoryException
            or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            windows = null;
        }

        return new InstalledApplicationFacts(entry.Name.Trim(), _platform.IsBrowser(entry), windows);
    }

    // Encargo 94: Windows' own association for plain text (AssocQueryString) names the program, which may not be listed
    // by that name: a friendly name, then the file name, as any opening resolves them.
    public async ValueTask<string?> PlainTextEditorAsync(CancellationToken cancellationToken)
    {
        if (_platform.PlainTextHandler() is not { } handler)
        {
            return null;
        }

        IReadOnlyList<InstalledApplicationEntry> catalog;
        try
        {
            catalog = await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return null;
        }

        InstalledApplicationEntry? entry =
            InstalledApplicationResolver.Resolve(handler.Name, catalog, _platform.LocateExecutable).Entry
            ?? InstalledApplicationResolver.Resolve(Path.GetFileName(handler.Executable), catalog, _platform.LocateExecutable).Entry;
        return entry is null || OpensSystemTool(entry) || _platform.IsBrowser(entry) ? null : entry.Name.Trim();
    }

    // Ajuste c5 (a game with its own launcher, outside Steam): what the catalog holds for a name a game.launch said. A
    // tool that configures Windows is not a game's: it opens only by app.open, which asks (the guard above).
    public async ValueTask<ApplicationNameLook?> LookForAsync(string name, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return new(null, [], []);
        }

        IReadOnlyList<InstalledApplicationEntry> catalog;
        try
        {
            catalog = await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return null;
        }

        InstalledApplicationResolution found = InstalledApplicationResolver.ResolveBearing(
            name, catalog, _platform.LocateExecutable, OpensSystemTool);
        return found.Entry is { } entry
            ? new(entry.Name.Trim(), [], [])
            : found.Ambiguous
                ? new(null, found.Candidates ?? [name.Trim()], [])
                : new(null, [], InstalledApplicationResolver.WithWordBeginningAs(name, found.Candidates));
    }

    // The rule of the guard above for one catalog entry (also what the installed list leaves out, CreateCatalogSnapshot).
    internal static bool OpensSystemTool(InstalledApplicationEntry entry) =>
        entry.AppUserModelId.Contains('!')
            ? External.VisibleControlSurface.SystemTool(InstalledApplicationResolver.PackageName(entry))
            : External.VisibleControlSurface.SystemToolLaunch(entry.TargetPath, entry.TargetArguments)
                || External.VisibleControlSurface.SystemToolLaunch(entry.AppUserModelId, entry.TargetArguments);

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

        InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(
            applicationName, catalog, _platform.LocateExecutable);
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
            : new(applicationName, null, false, true, null, Candidates: resolution.Candidates);
    }

    public async ValueTask<InstalledApplicationCatalogSnapshot> GetCatalogSnapshotAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            IReadOnlyList<InstalledApplicationEntry> catalog =
                await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
            return CreateCatalogSnapshot(catalog, _platform.LocateExecutable);
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
        IReadOnlyList<InstalledApplicationEntry> catalog,
        Func<string, InstalledExecutable?>? locate = null)
    {
        ArgumentNullException.ThrowIfNull(catalog);
        if (catalog.Any(static entry =>
            entry.Name.Contains('\uFFFD', StringComparison.Ordinal)
            || entry.AppUserModelId.Contains('\uFFFD', StringComparison.Ordinal)))
        {
            throw new InvalidDataException(
                "The Start application catalog contains a Unicode replacement character.");
        }

        // Renew al máximo (w7, apps; aid «system_tools_unlisted»): a tool that configures Windows itself, by the guard's
        // rule (OpensSystemTool), is not listed to the model (E014 read «Configuración del sistema» for «la configuración
        // de sonido» and opened msconfig elevated); app.open still opens it by its name. Its name stays out after the
        // grouping below, so no other entry's name is listed in its place.
        HashSet<string> systemTools = ModelAids.On(ModelAids.SystemToolsUnlisted)
            ? new(catalog.Where(OpensSystemTool).Select(static entry => entry.AppUserModelId), StringComparer.Ordinal)
            : [];
        var candidates = new List<(string Name, string AppUserModelId, string Key, InstalledApplicationEntry Entry)>();
        foreach (InstalledApplicationEntry entry in catalog)
        {
            if (!InstalledApplicationResolver.IsUsable(entry))
            {
                continue;
            }

            // Ajuste c3 (humos del 31-10): a shortcut's localized name may hold another white space than the space
            // («Windows PowerShell ISE 5.1» with a no-break one), which the hello's contract refuses, and with it the
            // whole list. The model is shown it with a space; the resolver folds white space, so it still opens.
            string name = new([.. entry.Name.Trim().Normalize(NormalizationForm.FormC)
                .Select(static character => char.IsWhiteSpace(character) ? ' ' : character)]);
            string key;
            try
            {
                key = CatalogNames.Normalize(name);
            }
            catch (ArgumentException)
            {
                continue;
            }

            if (key.Length != 0)
            {
                candidates.Add((name, entry.AppUserModelId, key, entry));
            }
        }

        string[] safelyResolvableNames = candidates
            .GroupBy(static candidate => candidate.Key, StringComparer.Ordinal)
            .Where(group =>
                InstalledApplicationResolver.Applications(group.Select(static candidate => candidate.Entry), locate)
                    is { Length: 1 } one
                && !systemTools.Contains(one[0].AppUserModelId))
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

    // Revisión de calidad (nb-q-apps): any installer can write a DisplayName with a lone surrogate, on which the fold
    // (string.Normalize) throws ArgumentException; it left app.installed as an exception for every application looked up
    // once the scan reached that key. Such a name names no application here, as the catalog read already treats it.
    internal static bool NamesInstalledApplication(string? candidateName, string target)
    {
        if (string.IsNullOrWhiteSpace(candidateName))
            return false;
        try
        {
            return InstalledApplicationResolver.Normalize(candidateName) == target;
        }
        catch (ArgumentException)
        {
            return false;
        }
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
                    if (!NamesInstalledApplication(candidateName, target))
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
            // This effect prerequisite accepts only what the resolver resolves: a complete installed name, a package's own
            // name, or the file name of a program an installed application launches.
            InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(
                applicationName, catalog, _platform.LocateExecutable);
            if (resolution.Ambiguous)
                return ([], ApplicationOpenErrorCodes.ApplicationAmbiguous, null);
            if (resolution.Entry is not { } entry)
                return ([], ApplicationOpenErrorCodes.ApplicationNotFound, null);
            if (!_platform.IdentifiesWindows(entry))
                return ([], ApplicationOpenErrorCodes.WindowIdentityUnavailable, null);

            return (_platform.InventoryForWindowResolution(entry, cancellationToken), null, entry.AppUserModelId);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return ([], ApplicationOpenErrorCodes.InventoryFailed, null);
        }
    }

    /// <summary>
    /// Uso 86: whether <paramref name="applicationName"/> is an installed application's name as window.resolve resolves
    /// it (one application, or several that answer to it); false only when it resolves to none or is no valid name. A
    /// catalog that cannot be read says nothing is known, and counts as installed (nothing is offered in its place).
    /// </summary>
    internal async ValueTask<bool> NamesInstalledApplicationAsync(
        string applicationName,
        CancellationToken cancellationToken)
    {
        var resolution = await ResolveApplicationWindowsAsync(applicationName, cancellationToken).ConfigureAwait(false);
        return resolution.ErrorCode is not (ApplicationOpenErrorCodes.ApplicationNotFound
            or ApplicationOpenErrorCodes.InvalidApplication);
    }

    /// <summary>
    /// Ajuste c3 (smoke of 31-10): the executables running the visible windows of the installed application
    /// <paramref name="applicationName"/> resolves to, as window.resolve resolves it (a window that only declares the
    /// application's id runs another program and is left out); empty when the name resolves to none, ambiguously, or
    /// the catalog cannot be read. A look by that name learns them (WindowsVisibleControlAdapter.NamedWindowAsync).
    /// </summary>
    internal async ValueTask<IReadOnlyList<string>> RunningExecutablesAsync(
        string applicationName,
        CancellationToken cancellationToken)
    {
        var resolution = await ResolveApplicationWindowsAsync(applicationName, cancellationToken).ConfigureAwait(false);
        return resolution.ErrorCode is not null
            ? []
            : [.. resolution.Windows
                .Where(static window => window.Visible && !window.DeclaredByWindow
                    && Path.IsPathFullyQualified(window.ExecutablePath))
                .Select(static window => Path.GetFullPath(window.ExecutablePath))
                .Distinct(StringComparer.OrdinalIgnoreCase)];
    }

    // Renew al máximo (auditoría de flujos): the processes of an installed application that run with no visible window
    // (Steam in the notification area), told by the executable its windows are told by; empty when it resolves to none
    // or its catalog cannot be read.
    internal async ValueTask<IReadOnlyList<int>> ResolveBackgroundProcessesAsync(
        string applicationName,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!ApplicationIds.IsValidRequest(applicationName))
            return [];
        try
        {
            IReadOnlyList<InstalledApplicationEntry> catalog = await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
            return InstalledApplicationResolver.Resolve(applicationName, catalog, _platform.LocateExecutable).Entry
                is { } entry
                ? _platform.RunningProcesses(entry)
                : [];
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return [];
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

        InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(
            applicationName, catalog, _platform.LocateExecutable);
        if (resolution.Ambiguous)
        {
            return new(applicationName, null, false, false, 0, false,
                ApplicationOpenErrorCodes.ApplicationAmbiguous);
        }
        if (resolution.Entry is null)
        {
            return new(applicationName, null, false, false, 0, true, null);
        }

        if (!_platform.IdentifiesWindows(resolution.Entry))
        {
            return new(applicationName, resolution.Entry.Name, true, false, 0, false,
                ApplicationOpenErrorCodes.WindowIdentityUnavailable);
        }

        IReadOnlyList<InstalledApplicationObservation> observations;
        try
        {
            // Ronda final 9 (regla 3): a count of the application's windows comes from the strict inventory (as
            // window.resolve's): a live process of it that could not be read fails the read, never «no window».
            observations = _platform.InventoryForWindowResolution(resolution.Entry, cancellationToken);
        }
        catch (Exception exception) when (exception is ApplicationInventoryException
            or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return new(applicationName, resolution.Entry.Name, true, false, 0, false,
                ApplicationOpenErrorCodes.InventoryFailed);
        }

        (long, int, long)[] visibleWindows = observations
            .Where(static observation => observation.Visible && observation.WindowHandle != 0)
            .Select(static observation =>
                (observation.WindowHandle, observation.ProcessId, observation.ProcessCreationTimeUtcTicks))
            .ToArray();
        return new(
            applicationName,
            resolution.Entry.Name,
            Installed: true,
            HasVisibleWindow: visibleWindows.Length > 0,
            VisibleWindowCount: visibleWindows.Length,
            Verified: true,
            ErrorCode: null,
            VisibleWindows: visibleWindows);
    }

    // resolving: the application an opening resolves on the catalog (app.open), null for any other read.
    private async ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
        CancellationToken cancellationToken,
        string? resolving = null)
    {
        DateTimeOffset now = _time.GetUtcNow();
        Task<IReadOnlyList<InstalledApplicationEntry>> loadTask;
        lock (_catalogLock)
        {
            if (_catalog is not null && now - _catalogLoadedAt < CatalogLifetime)
            {
                return _catalog;
            }

            loadTask = _catalogLoadTask ?? StartCatalogRead();
            // Renew al máximo (6.6): the first app.open after a pause waited the catalog's PowerShell read. A catalog
            // past its lifetime that already names the application is opened on while the read refreshes it behind;
            // the opened window is verified as always. A name it does not resolve waits the fresh catalog.
            if (resolving is not null && !loadTask.IsCompletedSuccessfully && _catalog is { } stale
                && InstalledApplicationResolver.Resolve(resolving, stale).Entry is not null)
            {
                return stale;
            }
        }

        try
        {
            return await loadTask.WaitAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            // M89: a refresh that did not answer in time leaves the last catalog read in force; with none, the
            // inventory fails as it does for an unreadable catalog.
            lock (_catalogLock)
            {
                if (_catalog is not null)
                {
                    return _catalog;
                }
            }

            throw new InvalidOperationException("The installed application catalog did not answer in time.");
        }
    }

    // Renew al máximo (6.6): called under _catalogLock. The one catalog read in flight, whoever waits on it or none:
    // it keeps what it read and clears itself when it ends, so a refresh left behind lands for the next caller.
    private Task<IReadOnlyList<InstalledApplicationEntry>> StartCatalogRead()
    {
        Task<IReadOnlyList<InstalledApplicationEntry>> read = LoadCatalogAsync();
        // A read that ended at once has already kept its catalog and cleared itself.
        _catalogLoadTask = read.IsCompleted ? null : read;
        // A refresh nobody waits on fails quietly (its failure observed here); the next read tries again.
        _ = read.ContinueWith(
            static task => _ = task.Exception,
            CancellationToken.None,
            TaskContinuationOptions.OnlyOnFaulted | TaskContinuationOptions.ExecuteSynchronously,
            TaskScheduler.Default);
        return read;
    }

    private async Task<IReadOnlyList<InstalledApplicationEntry>> LoadCatalogAsync()
    {
        try
        {
            IReadOnlyList<InstalledApplicationEntry> loaded = await ReadCatalogWithinBudgetAsync().ConfigureAwait(false);
            lock (_catalogLock)
            {
                _catalog = loaded;
                _catalogLoadedAt = _time.GetUtcNow();
            }

            return loaded;
        }
        finally
        {
            lock (_catalogLock)
            {
                _catalogLoadTask = null;
            }
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

    // The guard ends the moment BAXY takes the front on purpose (its next act brings its window up, often well
    // inside the guard) or the person does something that moves the front (a click on the opened window
    // is theirs to keep; r4a M2: typing in their own window is not, and does not end it): only a front the
    // application took by itself is handed back. r4a M4 (w1): each look reads and hands back under the front's gate,
    // which the foreground lease holds while it brings a window up, so the guard never undoes a burst's front.
    private async Task GuardFrontAsync(
        long previousFront, InstalledApplicationObservation opened, ForegroundHandBack.GuardStamp stamp)
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
                    if (IsOpened(opened, front))
                    {
                        bool restored = await ReturnForegroundWithinBudgetAsync(previousFront, front, CancellationToken.None)
                            .ConfigureAwait(false);
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
                request.ApplicationId,
                await ReadCatalogAsync(cancellationToken, request.ApplicationId).ConfigureAwait(false),
                _platform.LocateExecutable).Entry;
            // An application without a window identity is refused by the opening below, before any launch.
            theirs = entry is null || !_platform.IdentifiesWindows(entry)
                ? [] : [.. _platform.Inventory(entry).Select(static item => item.WindowHandle)];
        }
        // Renew al máximo (B-APP-9): as in the opening, any failed read is the inventory failure.
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return Failure(request, request.ApplicationId, ApplicationOpenErrorCodes.InventoryFailed);
        }

        // Renew al máximo (nuevo4): the worker a tab strip is read with starts with the launch (once, then kept): its cold
        // start (about 2.5 s) would otherwise eat the strip's whole budget on the first «nuevo».
        _platform.PrewarmTabStrip();
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
            // BAXY Renew cu (C18): unless the launch's new window was handed to that instance (Windows 11's Notepad).
            return opened.ErrorCode == ApplicationOpenErrorCodes.VerificationFailed
                ? (entry is null ? null : await BornEmptyAsync(request, entry, theirs, opened.DisplayName, cancellationToken)
                    .ConfigureAwait(false)) ?? NotCreated()
                : opened;
        }

        // Renew al máximo (nuevo4): the application's own names, the part after «: » in a document's title.
        string[] names = [Bare(entry.Name), Bare(opened.DisplayName)];
        IReadOnlyList<InstalledApplicationObservation> before;
        IReadOnlyList<TextFieldObservation> fieldsBefore;
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
            (long? settled, IReadOnlyList<string> startTitles) = await SettleStartAsync(
                    entry, window, process, theirs, names, cancellationToken)
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
            // Renew al máximo (rendimiento): and the window's text fields, to see a new tab whose title repeats.
            fieldsBefore = _platform.TextFields(window);
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

        // Renew al máximo (w8): a window born after the command is the new document only when its title names one, or
        // repeats the title of the window the command went to (another window of the same kind: «Windows PowerShell»).
        // In w6-settle a cold Steam's «Iniciar sesión en Steam», born while the command waited, was told a new document.
        bool IsNewDocument(long handle)
        {
            string title = Bare(_platform.WindowTitle(handle));
            return !bareTitles.Contains(title)
                && (NamesADocument(title, names) || string.Equals(title, Bare(titleBefore), StringComparison.Ordinal));
        }

        // The window in front before the command (its burst hands the front back to it).
        long frontBeforeCommand = request.Foreground ? _platform.ForegroundWindow() : 0;

        async ValueTask<ApplicationOpenResult> MadeAsync(InstalledApplicationObservation made)
        {
            // Review of r20b palanca 4: the new document follows the rule of every opening (OpeningFront), read
            // now: a person working in their window keeps their keyboard (a front the new window took goes back)
            // and the document is shown above theirs; otherwise the front is taken as asked.
            long person = OpeningFront.PersonWindow(
                _platform, request.Foreground, other => IsOpened(made, other), frontBeforeCommand);
            if (person == 0)
            {
                // Renew al máximo (B-APP-11): within the front's budget (M89), as every window of an opening.
                if (request.Foreground)
                    await RequestForegroundWithinBudgetAsync(made.WindowHandle, cancellationToken).ConfigureAwait(false);
                return Success(request, entry, made, reused: false, newDocument: true);
            }

            (bool activated, bool restored) = await HandBackFrontAsync(person, made, cancellationToken).ConfigureAwait(false);
            bool shown = await OpeningFront.ShowWithoutActivationAsync(
                _platform, made.WindowHandle, person, other => IsOpened(made, other), cancellationToken)
                .ConfigureAwait(false);
            return Success(request, entry, made, reused: false, activated, restored, newDocument: true,
                shownWithoutFocus: shown);
        }

        // Encargo 94: a tab strip's add button comes first whatever the keys do: Ctrl+N reached a Notepad with no visible
        // toggle that takes it (a restored note, live: 2 of 3 new_document_not_created) and made nothing. A shortcut depends
        // on the language (Microsoft, Keyboard accelerators: «in the Spanish version of Windows, Ctrl+N is used for bold»).
        // Renew al máximo (nuevo2): Ctrl+N is not every window's New. Windows 11's Notepad in Spanish bolds with it
        // («Negrita (Ctrl+N)»): the shown tab, maybe restored with text, took the format and «un Bloc de notas nuevo»
        // ended new_document_not_created 10 of 10 after 8 s. A toggle that takes Ctrl+N gets no key: the tab strip's add
        // button makes the new tab or, with none, no New command is known and nothing is sent.
        // Renew al máximo (nuevo4): only a window titled as a document (never a start or welcome screen, nor a splash the
        // settle of 654ace67c passed by) is read, and only through its tab strip (TabStripCommandAsync). Measured live: a
        // cold Word settled on its «Abriendo - Word» splash (MsoSplash, the only window yet), titled as a document; only
        // a main window (IsMainWindow: never a splash) is read.
        TabStripCommand strip = IsDocument(window) && _platform.IsMainWindow(window) && NamesADocument(Bare(titleBefore), names)
            ? await TabStripCommandAsync(window, cancellationToken).ConfigureAwait(false)
            : TabStripCommand.ShortcutIsNew;
        if (strip == TabStripCommand.NoNewCommand)
        {
            // As a command the lease refused: only a window born empty with this launch is a new document.
            return await BornEmptyAsync(request, entry, theirs, opened.DisplayName, cancellationToken).ConfigureAwait(false)
                ?? NotCreated();
        }

        if (strip == TabStripCommand.NewEmptyTabShown && IsDocument(window))
        {
            InstalledApplicationObservation? tab;
            try
            {
                tab = _platform.Inventory(entry).FirstOrDefault(item =>
                    item.WindowHandle == window && item.ProcessId == process && item.Visible);
            }
            catch (Exception exception) when (exception is ApplicationInventoryException
                or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
                return NotCreated();
            }

            if (tab is not null)
            {
                return await MadeAsync(tab).ConfigureAwait(false);
            }
        }

        // The command goes only to the application's own window, in a burst of the foreground lease (finding 4).
        if (strip == TabStripCommand.ShortcutIsNew
            && !await _platform.IssueNewDocumentAsync(window, cancellationToken).ConfigureAwait(false))
        {
            return await BornEmptyAsync(request, entry, theirs, opened.DisplayName, cancellationToken).ConfigureAwait(false)
                ?? NotCreated();
        }

        Stopwatch verification = Stopwatch.StartNew();
        bool dismissed = false;
        IReadOnlyList<InstalledApplicationObservation> seen = [];
        // A start screen dismissed late (a cold start that showed it near the end) is given its own time to show the
        // document it leaves.
        TimeSpan budget = NewDocumentBudget;
        for (int look = 0;
            look * ObservationDelay < budget && verification.Elapsed < budget;
            look++)
        {
            await _platform.DelayAsync(ObservationDelay, cancellationToken).ConfigureAwait(false);
            // BAXY Renew cu (C18): halfway, a window of this launch still showing only the application's name is a start
            // screen the New command did not reach (sent while a splash showed, or a localized shortcut: Office in Spanish
            // takes Ctrl+N as bold): Esc, once, dismisses it (Office's leaves a blank document, told by its title then).
            // Never a window the application already had (the person's).
            if (!dismissed && (look * ObservationDelay >= NewDocumentBudget / 2 || verification.Elapsed >= NewDocumentBudget / 2)
                && seen.FirstOrDefault(item => item.Visible && !theirs.Contains(item.WindowHandle)
                    && !_platform.IsOwnedWindow(item.WindowHandle)
                    && bareTitles.Contains(Bare(_platform.WindowTitle(item.WindowHandle)))) is { } start)
            {
                dismissed = true;
                _ = await _platform.IssueDismissStartAsync(start.WindowHandle, cancellationToken).ConfigureAwait(false);
                budget = TimeSpan.FromTicks(Math.Max(
                    budget.Ticks, Math.Max(verification.Elapsed.Ticks, (look * ObservationDelay).Ticks) + DismissSettle.Ticks));
                await _platform.DelayAsync(ObservationDelay, cancellationToken).ConfigureAwait(false);
            }

            InstalledApplicationObservation? made;
            List<long> dialogs;
            try
            {
                IReadOnlyList<InstalledApplicationObservation> current = _platform.Inventory(entry);
                seen = current;
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
                    .Where(item => !dialogs.Contains(item.WindowHandle) && IsNewDocument(item.WindowHandle))
                    .OrderByDescending(static item => item.Foreground)
                    .FirstOrDefault();
                if (made is null && titleTells && TitleShowsAnotherDocument(titleBefore, _platform.WindowTitle(window))
                    && IsDocument(window))
                {
                    made = current.FirstOrDefault(item => item.WindowHandle == window && item.ProcessId == process && item.Visible);
                }

                // Renew al máximo (rendimiento): Windows 11's Notepad gives its new tab the title the launched one had
                // («Sin título - Bloc de notas»), so the title tells nothing and every «un Bloc de notas nuevo» waited
                // the whole budget. A text field born after the command, shown and empty, in place of a field shown
                // before (the document in view replaced by a new empty one), with no dialog, tells it as soon as it is
                // there. Without that (no fields, or one field for every document), the looks go on as before.
                if (made is null && dialogs.Count == 0 && IsDocument(window)
                    && ShowsANewEmptyField(fieldsBefore, _platform.TextFields(window)))
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
                return await MadeAsync(made).ConfigureAwait(false);
            }

            if (dialogs.Count > 0)
            {
                // Auditoría D6: a dialog is never answered, and the document was not made. Encargo 98: a shortcut is another
                // command in some languages, so a dialog it raised is said, and closed as its Cancel (WM_CLOSE): it is BAXY's
                // doing, and was left over the person's window. Where no key went, the dialog is not BAXY's: only said.
                long dialog = dialogs[0];
                return NotCreated() with
                {
                    DialogOpened = new ApplicationDialogMet(
                        _platform.WindowTitle(dialog),
                        strip == TabStripCommand.ShortcutIsNew && _platform.CloseOwnedDialog(dialog)),
                };
            }
        }

        return await BornEmptyAsync(request, entry, theirs, opened.DisplayName, cancellationToken).ConfigureAwait(false)
            ?? NotCreated();
    }

    /// <summary>
    /// BAXY Renew cu (C18): a window of the application born with this launch (never one it already had, «theirs»), shown,
    /// no dialog, titled as a document (not the application's bare name) and holding no text, already is a new document:
    /// Windows 11's Notepad hands the new window to the instance that runs, and its New then makes no second empty tab,
    /// so neither a launched process nor a title change tells it. Nothing of the person's is in an empty window born now.
    /// </summary>
    private async ValueTask<ApplicationOpenResult?> BornEmptyAsync(
        ApplicationOpenRequest request,
        InstalledApplicationEntry entry,
        HashSet<long> theirs,
        string? displayName,
        CancellationToken cancellationToken)
    {
        var bare = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { Bare(entry.Name), Bare(displayName) };
        bare.Remove(string.Empty);
        InstalledApplicationObservation? made;
        try
        {
            made = _platform.Inventory(entry).FirstOrDefault(item => item.Visible
                && !theirs.Contains(item.WindowHandle)
                && !_platform.IsOwnedWindow(item.WindowHandle)
                && _platform.WindowTitle(item.WindowHandle) is { Length: > 0 } title
                && !bare.Contains(Bare(title))
                // Renew al máximo (nuevo4): titled as a document: an empty start or welcome screen («Bienvenido»,
                // «Bloc de notas: Inicio») is no new document.
                && NamesADocument(Bare(title), bare)
                && _platform.HoldsNoText(item.WindowHandle));
        }
        catch (Exception exception) when (exception is ApplicationInventoryException
            or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return null;
        }

        if (made is null)
        {
            return null;
        }

        if (request.Foreground)
        {
            // Renew al máximo (B-APP-11): within the front's budget (M89).
            await RequestForegroundWithinBudgetAsync(made.WindowHandle, cancellationToken).ConfigureAwait(false);
        }

        return Success(request, entry, made, reused: false, newDocument: true);
    }

    /// <summary>
    /// Renew al máximo (nuevo4): what the window's tab strip says of its New command, in <see cref="TabStripBudget"/> at
    /// most for all of it, the worker's start included (1eb63ed58 read every toggle of any window for up to 10 s, about
    /// 4 s on the first «nuevo»). A window without a tab strip (a Tab with a TabItem) is asked only that, and gets Ctrl+N
    /// as before; one with a strip is scanned for the strip's add button, its New in any language, and a toggle that takes
    /// Ctrl+N. Up to there nothing is pressed, so any failure (any exception, a step left at its share of the budget) is Ctrl+N as before. The
    /// add button is pressed only with <see cref="TabStripPressReserve"/> left to read the new tab back; once it may have
    /// been pressed, a failure sends no key on top of it (Ctrl+N would bold the new tab): the looks tell what came.
    /// </summary>
    private async ValueTask<TabStripCommand> TabStripCommandAsync(long window, CancellationToken cancellationToken)
    {
        DateTimeOffset start = _time.GetUtcNow();
        TimeSpan Left() => TabStripBudget - (_time.GetUtcNow() - start);
        TabStripCommand read;
        try
        {
            if (!await _platform.ShowsTabStripAsync(window, Left(), cancellationToken).ConfigureAwait(false)
                || Left() <= TimeSpan.Zero)
            {
                return TabStripCommand.ShortcutIsNew;
            }

            read = await _platform.ReadTabStripCommandAsync(window, Left(), cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            return TabStripCommand.ShortcutIsNew;
        }

        if (read == TabStripCommand.NoNewCommand)
        {
            return TabStripCommand.NoNewCommand;
        }

        if (read != TabStripCommand.AddButtonShown || Left() < TabStripPressReserve)
        {
            return TabStripCommand.ShortcutIsNew;
        }

        try
        {
            TabStripCommand added = await _platform.NewTabFromStripAsync(window, Left(), cancellationToken).ConfigureAwait(false);
            return added is TabStripCommand.TabAdded or TabStripCommand.NewEmptyTabShown ? added : TabStripCommand.ShortcutIsNew;
        }
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            return TabStripCommand.TabAdded;
        }
    }

    // A window title with a part besides the application's name («Nueva pestaña - …», «Sin título - …»): a dash
    // between spaces separates them. Renew al máximo (nuevo2): or a colon before a space, as Windows 11's Notepad 11.2607
    // titles its tabs («Sin título: Bloc de notas»); read as one segment, its own document was a start title and no new
    // tab of that window was ever a document. Renew al máximo (nuevo4): read as the dash is, the document first and the
    // application after it: only the application's own names («names», the opening's, never a list here) after the last
    // «: » make it a document's title. A colon is common elsewhere, with the application first or absent («Steam: Iniciar
    // sesión», «Configuración: Sistema»), and such a start or welcome screen is never a document.
    internal static bool NamesADocument(string title, IReadOnlyCollection<string> names)
    {
        if (title.Contains(" - ", StringComparison.Ordinal) || title.Contains(" — ", StringComparison.Ordinal)
            || title.Contains(" – ", StringComparison.Ordinal))
        {
            return true;
        }

        int colon = title.LastIndexOf(": ", StringComparison.Ordinal);
        if (colon <= 0 || title[..colon].Trim().Length == 0)
        {
            return false;
        }

        string application = title[(colon + 2)..].Trim();
        return application.Length > 0
            && names.Any(name => string.Equals(name, application, StringComparison.OrdinalIgnoreCase));
    }

    // A title as the bare name of an application is compared: its unsaved mark and its spaces left aside.
    private static string Bare(string? title) =>
        (title ?? string.Empty).Replace("*", string.Empty, StringComparison.Ordinal).Trim();

    // Ronda 20 P4 (v3-01): the windows a cold start shows (a splash, then the main window) settle before a command
    // goes to one: looks StartSettleDelay apart until two in a row bring no new window, within StartSettleBudget. The
    // window is the last one born that is still shown (the main window after a splash), else the one the opening
    // verified, else any shown; with the titles the start showed on its other windows (never the settled main
    // window's own title, which a new window of the command may repeat). A window the application had before the
    // launch («theirs», auditoría D6) is never one of the start's.
    // Renew al máximo (w6-settle): two still looks cost at least 0.8 s per cold «un X nuevo». Once the start has shown a
    // window after the verified one (the main window after a splash), the application's window events (created, shown,
    // hidden, renamed) are watched: StartEventQuiet with none, then one confirming look that brings no new window and
    // finds that last-born window still shown and a main window (IsMainWindow: never a splash), end the settle there.
    // Anything else keeps the looks as they were: no window born after the verified one (it may be a splash while the
    // main window is built hidden: an earlier shorter quiet sent «Nuevo» to a splash and was rejected), no events to
    // watch, events that never stop (each look still StartSettleDelay apart), within StartSettleBudget.
    private async ValueTask<(long? Window, IReadOnlyList<string> Titles)> SettleStartAsync(
        InstalledApplicationEntry entry,
        long started,
        int process,
        HashSet<long> theirs,
        IReadOnlyCollection<string> names,
        CancellationToken cancellationToken)
    {
        // The processes the start's windows were seen in: the ones whose window events are watched.
        var processes = new HashSet<int> { process };
        List<long> Shown()
        {
            List<InstalledApplicationObservation> items = [.. _platform.Inventory(entry)
                .Where(item => item.Visible && Path.IsPathFullyQualified(item.ExecutablePath)
                    && !theirs.Contains(item.WindowHandle) && !_platform.IsOwnedWindow(item.WindowHandle))];
            processes.UnionWith(items.Select(static item => item.ProcessId));
            return [.. items.Select(static item => item.WindowHandle)];
        }

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

        // Watched only from the first window born after the verified one: before it, the events could end nothing.
        IWindowEventWatch? events = null;
        List<long>? confirmed = null;
        try
        {
            bool watching = false;
            int still = 0;
            Stopwatch clock = Stopwatch.StartNew();
            for (int look = 0;
                still < 2 && look * StartSettleDelay < StartSettleBudget && clock.Elapsed < StartSettleBudget;
                look++)
            {
                if (!watching && born.Count > 0)
                {
                    watching = true;
                    events = _platform.WatchWindowEvents(processes);
                }

                TimeSpan wait = StartSettleDelay;
                int bornAtConfirm = 0;
                if (events is not null)
                {
                    (bool quiet, TimeSpan waited) = await events
                        .QuietAsync(StartEventQuiet, StartSettleDelay, cancellationToken).ConfigureAwait(false);
                    wait = waited >= StartSettleDelay ? TimeSpan.Zero : StartSettleDelay - waited;
                    if (quiet)
                    {
                        List<long> confirming = Shown();
                        List<long> freshNow = confirming.Where(seen.Add).ToList();
                        born.AddRange(freshNow);
                        bornAtConfirm = freshNow.Count;
                        if (freshNow.Count == 0 && born.LastOrDefault(confirming.Contains) is long newest && newest != 0
                            && _platform.IsMainWindow(newest))
                        {
                            confirmed = confirming;
                            break;
                        }
                    }
                }

                if (wait > TimeSpan.Zero)
                {
                    await _platform.DelayAsync(wait, cancellationToken).ConfigureAwait(false);
                }

                // A window the confirming look found born counts as born in this look: two still looks stay 400 ms apart.
                List<long> fresh = Shown().Where(seen.Add).ToList();
                born.AddRange(fresh);
                still = fresh.Count + bornAtConfirm == 0 ? still + 1 : 0;
            }
        }
        finally
        {
            // The watch's hooks go with the settle, a cancelled or failed one included.
            events?.Dispose();
        }

        List<long> shown = confirmed ?? Shown();
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
            if (NamesADocument(settled, names))
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

    // Renew al máximo (rendimiento): the window shows a new empty document in place of the one it showed: a field shown
    // before the command is no longer shown (or is gone), and a field that was not there before is shown and empty.
    internal static bool ShowsANewEmptyField(IReadOnlyList<TextFieldObservation> before, IReadOnlyList<TextFieldObservation> now)
    {
        bool left = before.Any(earlier => earlier.Shown
            && !now.Any(field => field.Handle == earlier.Handle && field.Shown));
        bool born = now.Any(field => field.Shown && field.Empty
            && !before.Any(earlier => earlier.Handle == field.Handle));
        return left && born;
    }

    // Whether «window» is the opened application's: its window, or a window of its process or of the same program.
    // Review R6: an application told by the id its window declares runs in another program (a browser), whose other
    // windows are the person's, so only that window is the application's.
    private bool IsOpened(InstalledApplicationObservation opened, long window) =>
        window == opened.WindowHandle
        || (!opened.DeclaredByWindow
            && _platform.SameApplication(opened.ProcessId, _platform.WindowProcessId(window)));

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
    // FT/proveedores goal (review of E5): a console program a terminal shows is never reused: every tab's pseudo-console
    // window is owned by the terminal window, so a copy in a tab behind would be said open while another tab is shown.
    // Only the copy this opening started is verified by its terminal window (Choose against the baseline).
    private IReadOnlyList<InstalledApplicationObservation> Reusable(
        ApplicationOpenRequest request,
        IReadOnlyList<InstalledApplicationObservation> observations) =>
        [.. observations.Where(item => !item.HostedByTerminal
            && (!request.ForControl || !_platform.RaisedButReopensUnraised(item.ProcessId)))];

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
        // Banco de uso 03-11 (U45): a protected window this opening showed (Windows Terminal hosting «Command Prompt») is
        // the application's for both names it was asked by, and named; what is typed there still asks as in any terminal.
        External.VisibleControlSurface.NoteOpenedProtected((nint)observation.WindowHandle, entry.Name, request.ApplicationId);
        // PLAN_GENERAL B1: the executable this verified opening found is the application's, by both names it was asked
        // by, so a later look by name finds its window whatever its title says (a localized «Iniciador de Epic Games»).
        // A window told by the id it declares runs in another program, whose other windows are not the application.
        if (!observation.DeclaredByWindow)
        {
            External.VisibleControlSurface.NoteApplicationExecutable(entry.Name, observation.ExecutablePath);
            External.VisibleControlSurface.NoteApplicationExecutable(request.ApplicationId, observation.ExecutablePath);
            External.VisibleControlSurface.NoteVerifiedOpening(entry.Name, observation.ExecutablePath);
            External.VisibleControlSurface.NoteVerifiedOpening(request.ApplicationId, observation.ExecutablePath);
        }
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
        IReadOnlyList<string>? candidates = null,
        string? nameHolder = null)
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
            Candidates: candidates,
            NameHolder: nameHolder);
    }
}

/// <summary>uso-108 C12: what became of the processes a launch started.</summary>
internal interface ILaunchWatch : IDisposable
{
    /// <summary>The crash code of a process of the launch, once all of them have ended; null otherwise.</summary>
    uint? CrashCode();
}

/// <summary>
/// uso-108 C12. The shell's launch gives no process (<c>explorer shell:AppsFolder</c>), so a process is known by its executable,
/// new since the watch began, and held by a handle from first sight: its exit code lives as long as a handle does. Each read
/// is taken at the opening's polls, so one that ends before the first of them is not seen, and the opening waits as before.
/// Only a code with the high nibble 0xC (NTSTATUS error: <c>STATUS_DLL_NOT_FOUND</c>, an access violation) says it died
/// (agent-desktop <c>process_state.rs:18-19,40-56</c>, <c>lifecycle-launch-devbox.json</c>): a launcher that ends cleanly, or
/// with any other code (explorer.exe ends with 1), while another process owns the window is an ordinary start. The wait
/// decides that it ended, never the code: 259 (STILL_ACTIVE) can be a real one (<c>close.rs:265-273</c>). A process of it still
/// running says nothing yet, and a crash waits a moment for the window of a child that outlives it.
/// </summary>
internal sealed partial class LaunchWatch : ILaunchWatch
{
    private const uint QueryLimitedAndSynchronize = 0x1000 | 0x00100000;
    private const uint HighNibble = 0xF0000000;
    private const uint NtError = 0xC0000000;
    private static readonly TimeSpan ChildGrace = TimeSpan.FromSeconds(1);
    private readonly Func<IReadOnlyList<int>> _running;
    private readonly HashSet<int> _known;
    private readonly List<SafeProcessHandle> _launched = [];
    private long _crashSeen;

    internal LaunchWatch(Func<IReadOnlyList<int>> running)
    {
        _running = running;
        _known = [.. Safely(running)];
    }

    public uint? CrashCode()
    {
        foreach (int process in Safely(_running))
        {
            if (_known.Add(process) && OpenProcess(QueryLimitedAndSynchronize, false, process) is { IsInvalid: false } handle)
                _launched.Add(handle);
        }

        uint? crash = null;
        foreach (SafeProcessHandle handle in _launched)
        {
            if (WaitForSingleObject(handle, 0) != 0)
            {
                _crashSeen = 0;
                return null;
            }

            if (GetExitCodeProcess(handle, out uint code) && (code & HighNibble) == NtError)
                crash ??= code;
        }

        if (crash is null)
            return null;
        if (_crashSeen == 0)
            _crashSeen = System.Diagnostics.Stopwatch.GetTimestamp();
        return System.Diagnostics.Stopwatch.GetElapsedTime(_crashSeen) >= ChildGrace ? crash : null;
    }

    private static IReadOnlyList<int> Safely(Func<IReadOnlyList<int>> running)
    {
        try
        {
            return running();
        }
        catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return [];
        }
    }

    public void Dispose()
    {
        foreach (SafeProcessHandle handle in _launched)
            handle.Dispose();
    }

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial SafeProcessHandle OpenProcess(
        uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, int processId);

    [LibraryImport("kernel32.dll")]
    private static partial uint WaitForSingleObject(SafeProcessHandle process, uint milliseconds);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetExitCodeProcess(SafeProcessHandle process, out uint exitCode);
}

internal sealed record InstalledApplicationEntry(
    string Name,
    string AppUserModelId,
    string? TargetPath = null,
    string? TargetArguments = null);

// Ajuste c3: a program Windows itself finds by its file name (App Paths, the system folders), and what its file says it
// is; read, never run.
internal sealed record InstalledExecutable(string Path, string? Description);

internal sealed record InstalledApplicationObservation(
    int ProcessId,
    long ProcessCreationTimeUtcTicks,
    string ExecutablePath,
    long WindowHandle,
    bool Visible,
    bool Foreground,
    string? ProcessName = null,
    bool HostedByTerminal = false,
    // The window declares the application's id as its own and its process runs another program (a browser's).
    bool DeclaredByWindow = false);

// Renew al máximo (rendimiento): one text field of a window (an Edit or RichEdit child), whether it is shown, and
// whether it holds no text (asked only of a shown field; a hidden one is never said empty).
internal readonly record struct TextFieldObservation(long Handle, bool Shown, bool Empty);

// Renew al máximo (nuevo2): what the window's own controls say of its New command. Windows 11's Notepad in Spanish
// (11.2607) shows «Negrita (Ctrl+N)»: Ctrl+N bolds the shown tab and makes nothing; its new tab is the tab strip's «+».
internal enum TabStripCommand
{
    // Nothing in the window takes Ctrl+N for another command (or it could not be read): Ctrl+N is sent, as before.
    ShortcutIsNew,

    // A toggle (a format) takes Ctrl+N and the window has no tab strip button to add a tab: no New command is known.
    NoNewCommand,

    // Renew al máximo (nuevo4): a toggle takes Ctrl+N and the tab strip shows its add button, not pressed yet (the read).
    AddButtonShown,

    // The tab strip's add button was invoked; the new tab is looked for as any New command's document.
    TabAdded,

    // The tab strip's add button was invoked and UI Automation read it made: one tab more, the selected one new, and
    // every document shown empty.
    NewEmptyTabShown,
}

internal interface IInstalledApplicationPlatform : IOpeningFront
{
    ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
        CancellationToken cancellationToken);

    // Whether Windows gives the application an identity its windows can be told by: a package, or the executable its
    // shortcut launches (auditoría final V1). Without one, no window is ever said to be the application's.
    bool IdentifiesWindows(InstalledApplicationEntry entry) => true;

    // Ajuste c3: where Windows finds a program by its bare file name («calc.exe»), never running it; null if nowhere.
    InstalledExecutable? LocateExecutable(string fileName) => null;

    // Encargo 94: whether the program this entry launches is a web browser Windows knows.
    bool IsBrowser(InstalledApplicationEntry entry) => false;

    // Encargo 94: the program Windows opens plain text with (its friendly name and executable); null if none, or a browser.
    (string Name, string Executable)? PlainTextHandler() => null;

    IReadOnlyList<InstalledApplicationObservation> Inventory(InstalledApplicationEntry entry);

    IReadOnlyList<InstalledApplicationObservation> InventoryForWindowResolution(
        InstalledApplicationEntry entry,
        CancellationToken cancellationToken) =>
        throw new ApplicationInventoryException("Strong application window identity is unavailable.");

    // Renew al máximo (auditoría de flujos): the running processes of a classic application's own executable, windows
    // or not; none for a packaged application (suspended in the background by Windows itself) or the shell's entry.
    IReadOnlyList<int> RunningProcesses(InstalledApplicationEntry entry) => [];

    // Renew al máximo (velocidad): Windows shows a frame of this packaged application with nothing of it inside
    // (VisibleControlSurface.ShowsEmptyFrame); false for a classic application.
    bool ShowsEmptyFrame(InstalledApplicationEntry entry) => false;

    // uso-108 C12: asked right before the launch, the processes of this classic application's executable it starts from
    // here on; null for one whose processes cannot be told (a packaged application, the shell).
    ILaunchWatch? WatchLaunch(InstalledApplicationEntry entry) => null;

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

    // Renew al máximo (nuevo2, nuevo4): read by UI Automation, without a key, before the New command, each step within
    // «within» (its answer left behind past it): when a toggle (a format, never a New) takes Ctrl+N, the window's tab
    // strip add button is pressed instead and the new tab read back. PrewarmTabStrip starts the worker (no wait);
    // ShowsTabStripAsync only tells whether the window shows a tab strip (a Tab with a TabItem); ReadTabStripCommandAsync
    // reads its toggles and add button (ShortcutIsNew, NoNewCommand or AddButtonShown), pressing nothing;
    // NewTabFromStripAsync presses the add button (TabAdded, NewEmptyTabShown, or ShortcutIsNew: not pressed).
    void PrewarmTabStrip()
    {
    }

    ValueTask<bool> ShowsTabStripAsync(long windowHandle, TimeSpan within, CancellationToken cancellationToken) =>
        ValueTask.FromResult(false);

    ValueTask<TabStripCommand> ReadTabStripCommandAsync(long windowHandle, TimeSpan within, CancellationToken cancellationToken) =>
        ValueTask.FromResult(TabStripCommand.ShortcutIsNew);

    ValueTask<TabStripCommand> NewTabFromStripAsync(long windowHandle, TimeSpan within, CancellationToken cancellationToken) =>
        ValueTask.FromResult(TabStripCommand.ShortcutIsNew);

    // BAXY Renew cu (C18): Esc given to this window in the same burst of the foreground lease: a start screen dismissed
    // (Office's leaves a blank document); whether Windows took both events.
    ValueTask<bool> IssueDismissStartAsync(long windowHandle, CancellationToken cancellationToken) =>
        ValueTask.FromResult(false);

    // The window's title as Windows has it (empty when it has none or is gone).
    string WindowTitle(long windowHandle) => string.Empty;

    // BAXY Renew cu (C18): whether the window holds text fields (its Edit or RichEdit children) and every one of them is
    // empty; false when it has none or one holds text or does not answer.
    bool HoldsNoText(long windowHandle) => false;

    // Renew al máximo (rendimiento): the window's text fields (its Edit or RichEdit children), each shown or not and,
    // when shown, empty or not; none when it has none or they cannot be read.
    IReadOnlyList<TextFieldObservation> TextFields(long windowHandle) => [];

    // Whether another window owns this one (a dialog of the application).
    bool IsOwnedWindow(long windowHandle) => false;

    /// <summary>Encargo 98: asks a dialog the New command raised to close, as its Cancel; whether it is gone.</summary>
    bool CloseOwnedDialog(long windowHandle) => false;

    // Renew al máximo (w6-settle): the window events of these processes and of the helpers and frames they show windows
    // through (WindowEventWatch), from now until disposed; null when none can be watched (the settle then only looks).
    IWindowEventWatch? WatchWindowEvents(IReadOnlyCollection<int> processes) => null;

    // Renew al máximo (w6-settle): whether the window is one a person works in, not a splash: shown, uncloaked, owned by
    // no other, no tool window, with a title bar or a frame that resizes and minimizes. False when it cannot be told.
    bool IsMainWindow(long windowHandle) => false;

    // The window in front now, whether the person works in a window, and the opened one shown above theirs without
    // the activation: IOpeningFront (r20b palanca 4).

    int WindowProcessId(long windowHandle) => 0;

    // Whether a window of «process» is the opened application's («opened»): its process, one it started, or another
    // process of the same program (a packaged application may show its window from another process of its own).
    bool SameApplication(int opened, int process) => opened > 0 && opened == process;

    // What the hand-back guard compares against: BAXY taking the front on purpose, the person's last input.
    ForegroundHandBack.GuardStamp FrontGuardStamp() => default;

    bool FrontGuardInterrupted(ForegroundHandBack.GuardStamp stamp) => false;

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
// NameHolder: with no entry of that name, the one installed name that ends with the words asked, or begins with two or
// more of them (see InstalledApplicationResolver.HolderOf); nothing is opened for it either.
internal sealed record InstalledApplicationResolution(
    InstalledApplicationEntry? Entry,
    bool Ambiguous,
    IReadOnlyList<string>? Candidates = null,
    string? NameHolder = null);

internal static class InstalledApplicationResolver
{
    // How many of the closest installed names a name that matches none gets back.
    private const int CandidateCount = 5;

    // Encargo 10 (punto 3): the ambiguous candidates, one per application. A8: «one application» is one destination
    // (SameDestination), not one id: entries that lead to the same place count once. When more than one bears the same
    // name, each of those is told apart by a visible origin —its program's path (and arguments), else its application id—
    // so the list is never one name repeated; a single-named one stays its plain name, as app.open says a name.
    private static string[] Distinguished(
        IEnumerable<InstalledApplicationEntry> entries, Func<string, InstalledExecutable?>? locate = null)
    {
        InstalledApplicationEntry[] byDestination = Applications(entries, locate);
        ILookup<string, InstalledApplicationEntry> sharing =
            byDestination.ToLookup(static item => Normalize(item.Name), StringComparer.Ordinal);
        return [.. byDestination
            .Select(item => sharing[Normalize(item.Name)].Count() > 1
                ? $"{item.Name.Trim()} ({Origin(item)})"
                : item.Name.Trim())
            .Distinct(StringComparer.OrdinalIgnoreCase)];
    }

    // What tells two applications of the same name apart: the program it opens (with the arguments its shortcut gives it,
    // when it gives any: the same program with other arguments is another thing), else its application-user-model id.
    // Visible, never a name the person did not install. Encargo 18 (U08/U14/U15): both are identities app.open takes back
    // (Chosen), so a candidate said is one it opens.
    private static string Origin(InstalledApplicationEntry entry) =>
        !string.IsNullOrWhiteSpace(entry.TargetPath)
            ? string.IsNullOrWhiteSpace(entry.TargetArguments)
                ? entry.TargetPath!.Trim()
                : $"{entry.TargetPath!.Trim()} {entry.TargetArguments.Trim()}"
            : entry.AppUserModelId.Trim();

    /// <summary>
    /// Encargo A8 (diagnóstico de flota 315702667: «Hay dos calculadoras instaladas, ¿cuál abro?» on Azure VMs where the
    /// Calculator was listed twice). The entries that lead to one destination are one application; only different
    /// destinations are ambiguous. By form, never by name. Two entries are the same application when:
    /// their AppUserModelIDs are equal (the id is the application's identity and Windows compares it without case,
    /// learn.microsoft.com/windows/win32/shell/appids); or both are shortcuts to the same file with the same arguments
    /// (the .lnk of the common and of the person's Start menu, or a copy of one: <c>System.Link.TargetParsingPath</c> and
    /// <c>System.Link.Arguments</c> are all the shell uses to launch it, and the same program with other arguments is
    /// another thing); or one is a packaged application and the other a shortcut whose program lies in that package's
    /// folder (<c>WindowsApps\Family_version_arch__publisher</c>) or is the very system program Windows finds by that file
    /// name and that describes itself as that package (the alias <c>calc.exe</c> of the Calculator package).
    /// </summary>
    internal static bool SameDestination(
        InstalledApplicationEntry first, InstalledApplicationEntry second, Func<string, InstalledExecutable?>? locate = null)
    {
        if (string.Equals(first.AppUserModelId.Trim(), second.AppUserModelId.Trim(), StringComparison.OrdinalIgnoreCase))
            return true;
        bool firstPackaged = IsPackaged(first);
        bool secondPackaged = IsPackaged(second);
        if (firstPackaged && secondPackaged)
            return false;
        if (firstPackaged || secondPackaged)
        {
            (InstalledApplicationEntry packaged, InstalledApplicationEntry other) =
                firstPackaged ? (first, second) : (second, first);
            return ShortcutLeadsToPackage(other, packaged, locate);
        }

        return !string.IsNullOrWhiteSpace(first.TargetPath) && !string.IsNullOrWhiteSpace(second.TargetPath)
            && string.Equals(FullPath(first.TargetPath!), FullPath(second.TargetPath!), StringComparison.OrdinalIgnoreCase)
            && string.Equals(
                (first.TargetArguments ?? string.Empty).Trim(), (second.TargetArguments ?? string.Empty).Trim(),
                StringComparison.OrdinalIgnoreCase);
    }

    // One entry per destination: of the entries that lead to the same place, the packaged one (its id is the identity
    // Windows gives its windows), else the first by id; the order of first appearance is kept.
    internal static InstalledApplicationEntry[] Applications(
        IEnumerable<InstalledApplicationEntry> entries, Func<string, InstalledExecutable?>? locate = null)
    {
        var groups = new List<List<InstalledApplicationEntry>>();
        foreach (InstalledApplicationEntry entry in entries)
        {
            List<InstalledApplicationEntry>? group = groups.Find(
                candidate => candidate.Exists(member => SameDestination(member, entry, locate)));
            if (group is null)
                groups.Add([entry]);
            else
                group.Add(entry);
        }

        return [.. groups.Select(static group => group
            .OrderBy(static item => IsPackaged(item) ? 0 : 1)
            .ThenBy(static item => item.AppUserModelId, StringComparer.Ordinal)
            .First())];
    }

    private static bool IsPackaged(InstalledApplicationEntry entry) =>
        string.IsNullOrWhiteSpace(entry.TargetPath) && PackageSegment(entry.AppUserModelId) is not null;

    private static string FullPath(string path)
    {
        string trimmed = path.Trim().Trim('"');
        try
        {
            return Path.IsPathFullyQualified(trimmed) ? Path.GetFullPath(trimmed) : trimmed;
        }
        catch (ArgumentException)
        {
            return trimmed;
        }
    }

    private static bool ShortcutLeadsToPackage(
        InstalledApplicationEntry shortcut, InstalledApplicationEntry packaged, Func<string, InstalledExecutable?>? locate)
    {
        if (string.IsNullOrWhiteSpace(shortcut.TargetPath))
            return false;
        string target = FullPath(shortcut.TargetPath!);
        string family = packaged.AppUserModelId[..packaged.AppUserModelId.IndexOf('!', StringComparison.Ordinal)].Trim();
        if (PackageFamily(target) is { } inFolder && string.Equals(inFolder, family, StringComparison.OrdinalIgnoreCase))
            return true;
        if (locate?.Invoke(Path.GetFileName(target)) is not { } located)
            return false;
        if (PackageFamily(located.Path) is { } found && string.Equals(found, family, StringComparison.OrdinalIgnoreCase))
            return true;
        // The system program itself (not another file of that name) that describes itself as the package's own name.
        return string.Equals(FullPath(located.Path), target, StringComparison.OrdinalIgnoreCase)
            && located.Description is { } description
            && Joined(Normalize(description)) is { Length: > 0 } described
            && PackageSegment(packaged.AppUserModelId) is { } segment
            && described == Joined(Normalize(segment));
    }

    // Encargo 18: the candidate an ambiguous opening said, asked back: by its whole label as said («Name (origin)») or by
    // the identity in it (its program's path or its application id), compared as written, case aside. Only identities
    // the catalog holds; one that several applications share chooses none. A bare id is taken only where no name could be
    // it (a package's «family!app», or a path): a classic id like a word («Chrome») is never a name asked (auditoría D1).
    private static InstalledApplicationEntry[] Chosen(string query, InstalledApplicationEntry[] entries)
    {
        string asked = query.Trim();
        return [.. entries.Where(item =>
            (NoName(item.AppUserModelId) && string.Equals(asked, item.AppUserModelId.Trim(), StringComparison.OrdinalIgnoreCase))
            || (item.TargetPath is { } target && NoName(target)
                && string.Equals(asked, target.Trim(), StringComparison.OrdinalIgnoreCase))
            || string.Equals(asked, $"{item.Name.Trim()} ({Origin(item)})", StringComparison.OrdinalIgnoreCase))];
    }

    private static bool NoName(string identity) => identity.IndexOfAny(['!', '\\', '/']) >= 0;

    // Entries a step of the resolution found: one application when they all lead to one destination (A8), else ambiguous
    // with each candidate told by what distinguishes it.
    private static InstalledApplicationResolution Resolved(
        InstalledApplicationEntry[] found, Func<string, InstalledExecutable?>? locate) =>
        Applications(found, locate) is { Length: 1 } one
            ? new InstalledApplicationResolution(one[0], false)
            : new InstalledApplicationResolution(null, true, Distinguished(found, locate));

    // Auditoría D1: the application is the catalog entry of exactly that name, folded (case, accents, whitespace);
    // «Motion» is never Notion, and «Notepad» is never Notepad++ (auditoría final V2: punctuation is part of a name). Without one
    // (nor by package, other name, file name or stem, below), nothing is resolved and the closest names are only said.
    internal static InstalledApplicationResolution Resolve(
        string query,
        IReadOnlyList<InstalledApplicationEntry> catalog,
        Func<string, InstalledExecutable?>? locateExecutable = null)
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
        InstalledApplicationEntry[] chosen = Chosen(query, entries);
        if (chosen.Length > 0)
        {
            return Resolved(chosen, locateExecutable);
        }

        InstalledApplicationEntry[] exact = entries
            .Where(item => Normalize(item.Name) == normalizedQuery)
            .ToArray();
        if (exact.Length == 1)
        {
            return new InstalledApplicationResolution(exact[0], false);
        }

        if (exact.Length > 1)
        {
            return Resolved(exact, locateExecutable);
        }

        // BAXY Renew cu (C18): a name that is no catalog name may be a packaged application's own identity, which no
        // language translates («Microsoft.WindowsNotepad» is Notepad, the catalog naming it «Bloc de notas»). Only one
        // entry bearing it resolves, and «Notepad» is still never Notepad++.
        InstalledApplicationEntry[] byIdentity = entries
            .Where(item => PackageName(item) is { } package && Normalize(package) == normalizedQuery)
            .ToArray();
        if (Applications(byIdentity, locateExecutable) is { Length: 1 } identified)
        {
            return new InstalledApplicationResolution(identified[0], false);
        }

        // Ajuste c3 (humo del NB, 31-10: «Settings» on a Spanish Windows, whose Start catalog says «Configuración»): a name
        // the application places' data give the same application in another display language is its installed entry,
        // as the place it is asked with already is (ApplicationPlaces.SameApplication). Only one entry resolves.
        InstalledApplicationEntry[] declared = entries
            .Where(item => ApplicationPlaces.SameApplication(query, item.Name))
            .ToArray();
        if (Applications(declared, locateExecutable) is { Length: 1 } declaredOne)
        {
            return new InstalledApplicationResolution(declaredOne[0], false);
        }

        // Ajuste c3 (e2e del NB: app.open «calc.exe» said the Calculadora was not in the start menu): a program's bare
        // file name, with or without «.exe», is the installed application that launches that program. Several are said,
        // none chosen; the program itself is never launched, only the catalog entry is opened as by its name.
        if (ExecutableFileName(query) is { } fileName
            && Launching(fileName, locateExecutable?.Invoke(fileName), entries) is { Length: > 0 } launching)
        {
            return Resolved(launching, locateExecutable);
        }

        // Ajuste c4 (banco ciego c3, causa 1: C3-058/059 «IrfanView» and C3-062/084/147 «Sumatra PDF» said app_not_found
        // and opened nothing): with none of those, the program one of whose stems (CatalogNames.Stems) is what was asked,
        // both without their spaces («IrfanView» is IrfanView 64 4.76, «Sumatra PDF» is SumatraPDF). An entry that opens
        // a document (a help file, a manual) is no program. Several are said, none chosen.
        string joinedQuery = Joined(normalizedQuery);
        InstalledApplicationEntry[] stemmed = [.. entries.Where(item => !OpensADocument(item)
            && CatalogNames.Stems(item.Name).Any(stem => Joined(stem) == joinedQuery))];
        if (stemmed.Length > 0)
        {
            return Resolved(stemmed, locateExecutable);
        }

        // Closest first: the names that hold every word asked, then those with a word that begins with the start of one
        // asked, then by edit distance.
        string[] words = normalizedQuery.Split(' ');
        string[] starts = [.. words.Select(Start).Where(static start => start.Length >= MinimumStart)];
        string[] closest = [.. entries
            .Select(item => item.Name.Trim())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(name => words.All(Normalize(name).Split(' ').Contains) ? 0 : 1)
            .ThenBy(name => Normalize(name).Split(' ')
                .Any(word => starts.Any(start => word.StartsWith(start, StringComparison.Ordinal))) ? 0 : 1)
            .ThenBy(name => Levenshtein(normalizedQuery, Normalize(name)))
            .ThenBy(static name => name, StringComparer.OrdinalIgnoreCase)
            .Take(CandidateCount)];
        string? holder = HolderOf(query, entries, locateExecutable);
        return new InstalledApplicationResolution(null, false,
            holder is null ? closest : [holder, .. closest.Where(name => name != holder).Take(CandidateCount - 1)],
            holder);
    }

    /// <summary>
    /// Banco de entorno del NB (2026-11-03, R17 3 of 3: «Opera GX» said, «Navegador Opera GX» installed; two runs of three
    /// gave up at app_not_found though the name was among the candidates). A Start entry's name is the shortcut's own,
    /// which an installer writes in the language of the PC (the shell shows a localized name, SHSetLocalizedName), so a
    /// product comes with words of kind or vendor around its own name: «Navegador Opera GX», «Opera GX Browser»,
    /// «Microsoft Edge». The one installed name whose words end with the words asked, or begin with them when two or
    /// more were asked, is said back for the model to name exactly; nothing is opened by it (auditoría D1: app.open asks
    /// for the name). Whole words only («Notepad» is no word of «Notepad++»), at least three letters asked, never a
    /// document, an installer or an uninstaller, and only when one application holds it so (two holders: none).
    /// </summary>
    internal static string? HolderOf(
        string query, IReadOnlyList<InstalledApplicationEntry> entries, Func<string, InstalledExecutable?>? locate = null)
    {
        string[] asked = Words(query);
        if (asked.Length == 0 || asked.Sum(static word => word.Length) < MinimumStart)
        {
            return null;
        }

        InstalledApplicationEntry[] holders = Applications(entries
            .Where(item => IsUsable(item) && !OpensADocument(item) && !SetsUpOrRemoves(item)
                && Words(item.Name) is { } words && words.Length > asked.Length
                && (words.AsSpan().EndsWith(asked) || (asked.Length >= 2 && words.AsSpan().StartsWith(asked)))),
            locate);
        return holders.Length == 1 ? holders[0].Name.Trim() : null;
    }

    // Ajuste c5 (un juego fuera de Steam, con su lanzador: «X» es «X Launcher» o «X for Windows» en el menú Inicio): lo que
    // resuelve Resolve y, si no resuelve nada, la aplicación cuyo nombre lleva enteras y seguidas las palabras pedidas.
    // Sólo para un título de juego que la biblioteca no tiene: app.open sigue pidiendo el nombre (auditoría D1). Lo que
    // no es el programa (un documento, un desinstalador o un instalador) no cuenta, ni una herramienta de Windows; varias
    // se dicen, sin elegir.
    internal static InstalledApplicationResolution ResolveBearing(
        string query,
        IReadOnlyList<InstalledApplicationEntry> catalog,
        Func<string, InstalledExecutable?>? locateExecutable,
        Func<InstalledApplicationEntry, bool> systemTool)
    {
        InstalledApplicationResolution resolved = Resolve(query, catalog, locateExecutable);
        if (resolved.Entry is { } entry)
        {
            return systemTool(entry) ? new InstalledApplicationResolution(null, false) : resolved;
        }

        string[] asked = Words(query);
        if (resolved.Ambiguous || asked.Sum(static word => word.Length) < MinimumStart)
        {
            return resolved;
        }

        InstalledApplicationEntry[] bearing = Applications(catalog
            .Where(item => IsUsable(item) && !OpensADocument(item) && !SetsUpOrRemoves(item) && !systemTool(item)
                && HoldsInARow(Words(item.Name), asked)),
            locateExecutable);
        // Revisión 02-11 (D1): only a name that begins with the title («X Launcher», «X for Windows»), or does after one
        // short first word («The X»), is the title's own and opens; one that holds it further in («Vendor X Panel» for
        // «X») is said as a candidate, never opened unasked.
        return bearing.Length switch
        {
            0 => resolved,
            1 when BeginsWith(Words(bearing[0].Name), asked) => new InstalledApplicationResolution(bearing[0], false),
            _ => new InstalledApplicationResolution(null, true, Distinguished(bearing, locateExecutable)),
        };
    }

    // Of the closest names a failed resolution says, those with a word that begins as a word asked begins; the others
    // are only the least far of the catalog (Levenshtein), no near name of a game.
    internal static IReadOnlyList<string> WithWordBeginningAs(string query, IReadOnlyList<string>? closest)
    {
        string[] starts = [.. Words(query).Select(Start).Where(static start => start.Length >= MinimumStart)];
        return [.. (closest ?? []).Where(name => Words(name)
            .Any(word => starts.Any(start => word.StartsWith(start, StringComparison.Ordinal))))];
    }

    // The words of a name, folded, without the signs at their edges («Quest:», «Zarvok®»); «notepad++» stays itself. The
    // trade mark is taken out first: folded it would become the letters «tm» of its word.
    private static string[] Words(string name) =>
    [
        .. Normalize(name.Replace('\u2122', ' ')).Split(' ')
            .Select(static word => word.Trim(EdgeSigns))
            .Where(static word => word.Length > 0),
    ];

    private static readonly char[] EdgeSigns =
        [':', ',', ';', '.', '!', '?', '-', '\u2013', '\u2014', '_', '\'', '"', '(', ')', '[', ']', '\u00AE', '\u00A9'];

    private static bool BeginsWith(string[] words, string[] asked) =>
        words.AsSpan().StartsWith(asked) || (words.Length > asked.Length && words[0].Length <= 3
            && words.AsSpan(1).StartsWith(asked));

    private static bool HoldsInARow(string[] words, string[] asked)
    {
        for (int start = 0; start + asked.Length <= words.Length; start++)
        {
            if (words.AsSpan(start, asked.Length).SequenceEqual(asked))
            {
                return true;
            }
        }

        return false;
    }

    // A Start entry that installs or removes something and is no program to play: by a word of its name, or by the file
    // its shortcut starts («unins000.exe»). No application's name is in this rule.
    private static bool SetsUpOrRemoves(InstalledApplicationEntry entry) =>
        Words(entry.Name).Any(static word => word is "uninstall" or "uninstaller" or "desinstalar" or "desinstalador"
                or "install" or "installer" or "instalar" or "instalador" or "setup")
        || Path.GetFileName(string.IsNullOrWhiteSpace(entry.TargetPath) ? entry.AppUserModelId : entry.TargetPath)
            .StartsWith("unins", StringComparison.OrdinalIgnoreCase);

    internal static string Normalize(string value) => CatalogNames.Normalize(value);

    private static string Joined(string folded) => folded.Replace(" ", string.Empty, StringComparison.Ordinal);

    // Ajuste c4: a Start entry that opens a document and not a program: its shortcut's target, or else a classic id that
    // is a path, is a file of another type than «.exe». A packaged application, or an id Windows registers for a program
    // («Chrome»), opens a program.
    private static bool OpensADocument(InstalledApplicationEntry entry)
    {
        string target = string.IsNullOrWhiteSpace(entry.TargetPath) ? entry.AppUserModelId : entry.TargetPath;
        return target.IndexOfAny(['\\', '/']) >= 0
            && Path.GetExtension(target) is { Length: > 0 } extension
            && !extension.Equals(".exe", StringComparison.OrdinalIgnoreCase);
    }

    // Ajuste c3 (e2e del PC, E010: «calc.exe» said Access, Calendar, CapCut, Claude and CODEX, not the Calculadora
    // installed): a word's start, its letters and digits up to the first other sign («calc» of «calc.exe»). Only from
    // three on does a name that begins with it come first: shorter ones begin too many names.
    private const int MinimumStart = 3;

    private static string Start(string word) => new([.. word.TakeWhile(char.IsLetterOrDigit)]);

    // A packaged application's own name: its package's, without the publisher and without the «Windows» every inbox
    // application's package carries («Microsoft.WindowsCalculator_8wekyb3d8bbwe!App»: Calculator); null for a classic
    // program (no «family_publisher!app» identity).
    internal static string? PackageName(InstalledApplicationEntry entry)
    {
        if (!string.IsNullOrWhiteSpace(entry.TargetPath) || PackageSegment(entry.AppUserModelId) is not { } name)
            return null;
        return name.StartsWith("Windows", StringComparison.Ordinal) && name.Length > "Windows".Length
            ? name["Windows".Length..]
            : name;
    }

    // The last part of a packaged application's family, its publisher left out («WindowsCalculator» of
    // «Microsoft.WindowsCalculator_8wekyb3d8bbwe!App»); null for a classic program (no «family_publisher!app» identity).
    private static string? PackageSegment(string id)
    {
        int bang = id.IndexOf('!', StringComparison.Ordinal);
        int underscore = id.IndexOf('_', StringComparison.Ordinal);
        if (bang <= 0 || underscore <= 0 || underscore > bang)
            return null;
        string family = id[..underscore];
        return family[(family.LastIndexOf('.') + 1)..];
    }

    // Ajuste c3: a program's bare file name, «.exe» added when it has no extension; null for a path, another extension
    // or several words.
    private static string? ExecutableFileName(string query)
    {
        string name = query.Trim();
        if (name.Length == 0 || name.Any(char.IsWhiteSpace) || name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
            return null;
        string extension = Path.GetExtension(name);
        return extension.Length == 0 ? name + ".exe"
            : extension.Equals(".exe", StringComparison.OrdinalIgnoreCase) ? name : null;
    }

    // The entries that launch that program: a shortcut that targets a file of that name or the very file Windows finds
    // by it, or the package that file lies in (App Paths names a packaged program inside its WindowsApps folder). A
    // system program none of them launches, which only starts another one (calc.exe starts the Calculator package), is
    // the entry it describes itself as: by its installed name, or by its package's full own name («Windows Calculator»
    // is Microsoft.WindowsCalculator).
    private static InstalledApplicationEntry[] Launching(
        string fileName,
        InstalledExecutable? located,
        InstalledApplicationEntry[] entries)
    {
        string? family = located is null ? null : PackageFamily(located.Path);
        InstalledApplicationEntry[] launching = [.. entries.Where(item =>
            (item.TargetPath is { Length: > 0 } target
                && (string.Equals(Path.GetFileName(target), fileName, StringComparison.OrdinalIgnoreCase)
                    || string.Equals(target, located?.Path, StringComparison.OrdinalIgnoreCase)))
            || (family is not null && item.AppUserModelId.StartsWith(family + "!", StringComparison.OrdinalIgnoreCase)))];
        if (launching.Length > 0 || located?.Description is not { } description || Normalize(description).Length == 0)
            return launching;

        string described = Normalize(description);
        string joined = described.Replace(" ", string.Empty, StringComparison.Ordinal);
        return [.. entries.Where(item => Normalize(item.Name) == described
            || (PackageSegment(item.AppUserModelId) is { } segment && Normalize(segment) == joined))];
    }

    // The package a file of a WindowsApps folder lies in («…\WindowsApps\Microsoft.Paint_11.2605.81.0_x64__8wekyb3d8bbwe\
    // PaintApp\mspaint.exe»: name, version, architecture, resource and publisher, so Microsoft.Paint_8wekyb3d8bbwe); null
    // for a file anywhere else.
    private static string? PackageFamily(string path)
    {
        string[] parts = path.Split(['\\', '/'], StringSplitOptions.RemoveEmptyEntries);
        int at = Array.FindIndex(parts, static part => part.Equals("WindowsApps", StringComparison.OrdinalIgnoreCase));
        if (at < 0 || at + 2 >= parts.Length)
            return null;
        string[] package = parts[at + 1].Split('_');
        return package.Length == 5 && package[0].Length > 0 && package[4].Length > 0
            ? $"{package[0]}_{package[4]}"
            : null;
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
    // Ajuste c3: where Windows finds a program by its bare file name, as its Run box does: App Paths (the person's, then
    // the machine's), then the system folders. The file is read for what it says it is, never run.
    public InstalledExecutable? LocateExecutable(string fileName)
    {
        if (string.IsNullOrWhiteSpace(fileName) || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
            return null;
        string? path = AppPath(RegistryHive.CurrentUser, fileName)
            ?? AppPath(RegistryHive.LocalMachine, fileName)
            ?? new[] { Environment.SystemDirectory, Environment.GetFolderPath(Environment.SpecialFolder.Windows) }
                .Select(folder => Path.Combine(folder, fileName))
                .FirstOrDefault(File.Exists);
        if (path is null)
            return null;

        string? description = null;
        try
        {
            description = FileVersionInfo.GetVersionInfo(path).FileDescription;
        }
        // A packaged program's folder may not be readable; its package still tells it.
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException)
        {
        }

        return new InstalledExecutable(path, string.IsNullOrWhiteSpace(description) ? null : description.Trim());
    }

    private static string? AppPath(RegistryHive hive, string fileName)
    {
        try
        {
            using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, RegistryView.Default);
            using RegistryKey? key = baseKey.OpenSubKey(
                $@"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{fileName}",
                writable: false);
            return key?.GetValue(null) is string value
                && value.Trim().Trim('"') is { Length: > 0 } path
                && Path.IsPathFullyQualified(path)
                ? path
                : null;
        }
        catch (Exception exception) when (exception is UnauthorizedAccessException
            or IOException
            or System.Security.SecurityException)
        {
            return null;
        }
    }

    public bool ShowsEmptyFrame(InstalledApplicationEntry entry) =>
        entry.AppUserModelId.Contains('!') && External.VisibleControlSurface.ShowsEmptyFrame(entry.AppUserModelId);

    public ILaunchWatch? WatchLaunch(InstalledApplicationEntry entry) =>
        entry.AppUserModelId.Contains('!')
        || string.Equals(entry.AppUserModelId, ShellExplorerAppUserModelId, StringComparison.Ordinal)
        || ExpectedExecutable(entry) is null
            ? null
            : new LaunchWatch(() => RunningProcesses(entry));

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
        External.HelperProcessJob.Assign(process);
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

    public bool IdentifiesWindows(InstalledApplicationEntry entry) =>
        entry.AppUserModelId.Contains('!') || ExpectedExecutable(entry) is not null;

    public bool IsBrowser(InstalledApplicationEntry entry) =>
        !entry.AppUserModelId.Contains('!') && ExpectedExecutable(entry) is { } executable
        && External.UserBrowserIdentityResolver.IsRegisteredBrowser(executable) != false;

    public (string Name, string Executable)? PlainTextHandler() =>
        PlainTextAssociation.Read() is { } handler
        && External.UserBrowserIdentityResolver.IsRegisteredBrowser(handler.Executable) == false
            ? handler
            : null;

    public IReadOnlyList<InstalledApplicationObservation> Inventory(
        InstalledApplicationEntry entry) =>
        Inventory(entry, strongIdentityOnly: false, CancellationToken.None);

    public IReadOnlyList<InstalledApplicationObservation> InventoryForWindowResolution(
        InstalledApplicationEntry entry,
        CancellationToken cancellationToken) =>
        Inventory(entry, strongIdentityOnly: true, cancellationToken);

    public IReadOnlyList<int> RunningProcesses(InstalledApplicationEntry entry)
    {
        if (entry.AppUserModelId.Contains('!')
            || string.Equals(entry.AppUserModelId, ShellExplorerAppUserModelId, StringComparison.Ordinal)
            || ExpectedExecutable(entry) is not { } expected)
            return [];
        Process[] processes = Process.GetProcessesByName(Path.GetFileNameWithoutExtension(expected));
        try
        {
            return [.. processes
                .Where(process => ExecutableImagePath(process.Id) is { } image && Path.IsPathFullyQualified(image)
                    && ExecutableIsLaunchedImage(Path.GetFullPath(image), expected))
                .Select(static process => process.Id)
                .Order()];
        }
        finally
        {
            foreach (Process process in processes)
                process.Dispose();
        }
    }

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
        CancellationToken cancellationToken) =>
        Inventory(entry, strongIdentityOnly, MainWindowsByProcess, cancellationToken);

    // Renew al máximo (rendimiento): the main window of every process, read in one pass over the top-level windows. Each
    // process's MainWindowHandle was one such pass of its own (an EnumWindows per process: about 300 per inventory of a
    // packaged application, one inventory every 100 ms while an opening is verified); this pass applies the same rule
    // (.NET's MainWindowFinder): the first window in Z order of the process that no window owns (GW_OWNER) and that is
    // visible.
    internal static Dictionary<uint, nint> MainWindowsByProcess()
    {
        var found = new Dictionary<uint, nint>();
        EnumWindowsProc callback = (window, _) =>
        {
            GetWindowThreadProcessId(window, out uint process);
            if (!found.ContainsKey(process) && GetWindow(window, 4) == 0 && IsWindowVisible(window))
                found[process] = window;
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        GC.KeepAlive(callback);
        return found;
    }

    internal static List<InstalledApplicationObservation> Inventory(
        InstalledApplicationEntry entry,
        bool strongIdentityOnly,
        Func<Dictionary<uint, nint>> readMainWindows,
        CancellationToken cancellationToken)
    {
        bool packaged = entry.AppUserModelId.Contains('!');
        // The shell's own catalog entry: its windows live in explorer.exe, which
        // also owns the desktop and taskbar. Only file-browsing windows
        // (CabinetWClass) count as the application being open (APPS1231/005).
        bool shellExplorer = !packaged && string.Equals(
            entry.AppUserModelId, ShellExplorerAppUserModelId, StringComparison.Ordinal);
        string? windowClass = shellExplorer ? ExplorerWindowClass : null;
        // Auditoría final V1: a window is the application's by its package identity (AUMID) or by the executable its
        // shortcut launches, for opening as for closing; never by words of its name, its process name or its title
        // («Notepad++» was taken for «Bloc de notas»). Strict (strongIdentityOnly) only adds that the inventory is
        // complete.
        string? expectedExecutable = packaged ? null : ExpectedExecutable(entry);
        if (!packaged && expectedExecutable is null)
            throw new ApplicationInventoryException("The installed executable identity is unavailable.");
        Process[] processes = Process.GetProcesses();
        var observations = new List<InstalledApplicationObservation>();
        Dictionary<uint, nint>? hostedFrames = null;
        // Renew al máximo (rendimiento): read once, the first time a process's main window is asked for.
        Dictionary<uint, nint>? mainWindows = null;
        // The processes running the launched image's name, and who started whom: a helper they started may draw the
        // application's windows (steamwebhelper.exe under steam.exe); its ancestor's image is verified below.
        HashSet<uint> launchers = packaged ? [] : [.. processes
            .Where(process => string.Equals(process.ProcessName, Path.GetFileNameWithoutExtension(expectedExecutable),
                StringComparison.OrdinalIgnoreCase))
            .Select(static process => unchecked((uint)process.Id))];
        Dictionary<uint, uint> parents = launchers.Count > 0 ? External.VisibleControlSurface.ParentByProcess() : [];
        // The windows that declare the application's id as their own, by the process that draws them (DeclaresApplication).
        Dictionary<uint, HashSet<nint>> declaring = packaged ? [] : WindowsDeclaring(entry);
        try
        {
            foreach (Process process in processes)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    process.Refresh();
                    declaring.TryGetValue(unchecked((uint)process.Id), out HashSet<nint>? declared);
                    if (!packaged && declared is null && !launchers.Contains(unchecked((uint)process.Id))
                        && !HasAncestorAmong(unchecked((uint)process.Id), launchers, parents))
                    {
                        // A process of another executable cannot be this
                        // classic application; reading its main module (elevated
                        // Task Manager, CLOSE1221) must not abort the inventory.
                        continue;
                    }

                    // A foreign window being destroyed (Chrome tearing down after a
                    // close, CLOSE1223/009) has no readable rectangle; only the
                    // candidate's enumeration must be complete.
                    nint[]? ownedWindows = strongIdentityOnly || shellExplorer
                        ? VisibleTopLevelWindows(process.Id, requireComplete: false, windowClass)
                        : null;
                    nint window = ownedWindows is null
                        ? (mainWindows ??= readMainWindows()).GetValueOrDefault(unchecked((uint)process.Id))
                        : ownedWindows.FirstOrDefault();
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

                    bool hostedByTerminal = false;
                    if (!usable && !packaged && !strongIdentityOnly)
                    {
                        // FT/proveedores goal (E5): a console program Windows Terminal shows has no window of its own
                        // (cmd opened, and every check spent its 30 s): the Terminal window that owns its pseudo-console
                        // window is what the person sees.
                        frame = TerminalHosting(process.Id);
                        usable = hostedByTerminal = frame != 0;
                    }

                    if (!usable)
                    {
                        continue;
                    }

                    // An unreadable foreign process is not a candidate for this package; only candidates need a
                    // strong identity.
                    if (packaged
                        && (!TryReadPackagedIdentity(() => ReadApplicationUserModelId(process.Id), out string? applicationId)
                            || !string.Equals(entry.AppUserModelId, applicationId, StringComparison.Ordinal)))
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
                    bool launchedImage = packaged
                        || ExecutableIsLaunchedImage(Path.GetFullPath(executablePath), expectedExecutable!)
                        || DescendsFromLaunchedImage(process, expectedExecutable!, parents);
                    if (!launchedImage && declared is null)
                        continue;
                    if (strongIdentityOnly)
                    {
                        // The candidate's own window set must be complete and stable; another program's other windows
                        // (a browser's, one being torn down) are not the application's.
                        ownedWindows = VisibleTopLevelWindows(process.Id, requireComplete: launchedImage, windowClass);
                        if (ownedWindows.Length == 0)
                            continue;
                    }

                    long creationTime = process.StartTime.ToUniversalTime().Ticks;
                    foreach (nint operated in ownedWindows ?? (frame != 0 ? [frame] : VisibleTopLevelWindows(process.Id)))
                    {
                        // Another program's process: only its windows that declare the application are the application.
                        if (!launchedImage && !declared!.Contains(operated))
                            continue;
                        observations.Add(new InstalledApplicationObservation(
                            process.Id,
                            creationTime,
                            executablePath,
                            operated.ToInt64(),
                            Visible: true,
                            Foreground: GetForegroundWindow() == operated,
                            ProcessName: strongIdentityOnly ? process.ProcessName : null,
                            HostedByTerminal: hostedByTerminal,
                            DeclaredByWindow: !launchedImage));
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
    /// whole open inventory. A process whose identity cannot be read is skipped: it is no candidate of the package.
    /// </summary>
    internal static bool TryReadPackagedIdentity(Func<string?> read, out string? applicationId)
    {
        try
        {
            applicationId = read();
            return true;
        }
        catch (ApplicationInventoryException)
        {
            applicationId = null;
            return false;
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

    // Whether one of the processes running the launched image's name is an ancestor of this one, within three
    // generations (the cheap filter; DescendsFromLaunchedImage proves it).
    private static bool HasAncestorAmong(uint process, HashSet<uint> ancestors, Dictionary<uint, uint> parents)
    {
        for (int generation = 0; generation < 3 && parents.TryGetValue(process, out uint parent) && parent != 0;
             generation++)
        {
            if (ancestors.Contains(parent))
                return true;
            process = parent;
        }

        return false;
    }

    /// <summary>
    /// A window drawn by a helper the application itself ships (Steam's windows belong to steamwebhelper.exe, a child
    /// of steam.exe in Steam's own folder): the window's process descends, within three generations, from a process
    /// running the launched image, each parent older than its child so a reused process id never passes for a parent;
    /// and the helper's executable lies under the launched executable's folder and names the same company. A program the
    /// application only started (a game Steam launches, a page a chat opens) is a different program (re-audit of the
    /// second round, 2026-10-15: «cierra steam» would have closed the game).
    /// </summary>
    internal static bool DescendsFromLaunchedImage(
        Process process, string expectedPath, IReadOnlyDictionary<uint, uint> parents)
    {
        if (!ShippedWith(ExecutableImagePath(process.Id), expectedPath))
            return false;
        try
        {
            uint id = unchecked((uint)process.Id);
            DateTime childStart = process.StartTime;
            for (int generation = 0; generation < 3 && parents.TryGetValue(id, out uint parentId) && parentId != 0;
                 generation++)
            {
                using Process parent = Process.GetProcessById(unchecked((int)parentId));
                if (parent.StartTime > childStart)
                    return false;
                if (ExecutableImagePath(parent.Id) is { } path && Path.IsPathFullyQualified(path)
                    && ExecutableIsLaunchedImage(Path.GetFullPath(path), expectedPath))
                    return true;
                id = parentId;
                childStart = parent.StartTime;
            }
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            // A parent that exited or cannot be read proves nothing.
        }

        return false;
    }

    private static bool ShippedWith(string? helperPath, string expectedPath)
    {
        if (string.IsNullOrWhiteSpace(helperPath) || !Path.IsPathFullyQualified(helperPath))
            return false;
        string? folder = Path.GetDirectoryName(Path.GetFullPath(expectedPath));
        string helper = Path.GetFullPath(helperPath);
        if (folder is null || !helper.StartsWith(folder + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            return false;
        try
        {
            string? company = FileVersionInfo.GetVersionInfo(expectedPath).CompanyName?.Trim();
            string? helperCompany = FileVersionInfo.GetVersionInfo(helper).CompanyName?.Trim();
            return !string.IsNullOrEmpty(company) && string.Equals(company, helperCompany, StringComparison.Ordinal);
        }
        catch (Exception exception) when (exception is FileNotFoundException or ArgumentException)
        {
            return false;
        }
    }

    /// <summary>
    /// The running image is the shortcut's executable, or the same file name in a
    /// direct versioned subfolder of the shortcut's folder: self-updating
    /// installers put a launcher next to <c>app-1.0.9260\</c> and the window
    /// belongs to the copy inside (t4-r6: «cierra discord» → window_not_found).
    /// A same-named executable anywhere else is a different program.
    /// Uso real 2026-10-20, generalized by PLAN_GENERAL B1: a launcher in an architecture folder starts the same file
    /// in a sibling architecture folder and exits, and that copy owns the window (Epic: <c>Binaries\Win32\</c> starts
    /// <c>Binaries\Win64\</c>); the same file in a sibling architecture folder is the launched image too. Any other
    /// sibling folder is another program.
    /// </summary>
    // The folder names that hold one build of a program per processor architecture.
    private static readonly HashSet<string> ArchitectureFolders = new(StringComparer.OrdinalIgnoreCase)
    {
        "Win32", "Win64", "x86", "x64", "x86_64", "amd64", "arm64", "bin32", "bin64",
    };

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
        if (ArchitectureFolders.Contains(Path.GetFileName(launcherFolder))
            && ArchitectureFolders.Contains(Path.GetFileName(versioned))
            && string.Equals(Path.GetDirectoryName(versioned), Path.GetDirectoryName(launcherFolder),
                StringComparison.OrdinalIgnoreCase))
            return true;
        return string.Equals(Path.GetDirectoryName(versioned), launcherFolder, StringComparison.OrdinalIgnoreCase)
            && VersionedFolder.IsMatch(Path.GetFileName(versioned));
    }

    /// <summary>
    /// Feria (caso 16: an application installed from a web browser waited out its 30 s with its window on screen): such
    /// an application is a shortcut to the browser's launcher, which hands the page to the browser's own process, so its
    /// window belongs to another program. That window carries the application's id as its own (its property store's
    /// AppUserModelID, what the taskbar groups it by), the id the catalog lists the shortcut by (read 2026-10-27 on this
    /// PC: every one of 587 classic entries' System.AppUserModel.ID is its id). A window declaring a classic entry's id
    /// is that application's, whatever process draws it; a packaged application's frame declares its id even empty
    /// (VisibleControlSurface.ShowsEmptyFrame), so a package keeps its process identity.
    /// </summary>
    internal static bool DeclaresApplication(InstalledApplicationEntry entry, string? windowApplicationId) =>
        !entry.AppUserModelId.Contains('!')
        && string.Equals(windowApplicationId, entry.AppUserModelId, StringComparison.Ordinal);

    private static Dictionary<uint, HashSet<nint>> WindowsDeclaring(InstalledApplicationEntry entry)
    {
        var found = new Dictionary<uint, HashSet<nint>>();
        EnumWindowsProc callback = (window, _) =>
        {
            if (IsWindowVisible(window)
                && DeclaresApplication(entry, External.VisibleControlSurface.WindowApplicationId(window)))
            {
                GetWindowThreadProcessId(window, out uint process);
                if (!found.TryGetValue(process, out HashSet<nint>? windows))
                    found[process] = windows = [];
                windows.Add(window);
            }
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        GC.KeepAlive(callback);
        return found;
    }

    // The executable a classic application's windows run: File Explorer's own image for the shell's catalog entry (its
    // id carries no path), else the shortcut's executable; null when Windows gives none.
    internal static string? ExpectedExecutable(InstalledApplicationEntry entry) =>
        string.Equals(entry.AppUserModelId, ShellExplorerAppUserModelId, StringComparison.Ordinal)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "explorer.exe")
            : StrongExecutablePath(entry);

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
        // v3 r5a M5: a program Windows would raise to administrator unasked starts with the person's own rights when
        // app.open says forControl. cu-v3-elevacion: measured live on r9 (v3-23, v3-65), a console opened through the
        // shell came up as administrator and the next turn could neither read nor press it. A start that fails (the job refuses the
        // breakaway) falls back to the shell's path: an elevated window is an honest limit.
        if (forControl
            && InvokerLaunch.Plan(entry, File.Exists, InvokerLaunch.AssociatedCommand, InvokerLaunch.ReadManifest)
                is { } invoker
            && InvokerLaunch.Start(invoker))
        {
            return true;
        }

        // A Chrome that shows UI Automation only its frame (External.ChromeUiaFlag), which the shell's path could not start
        // with its flag. If it cannot be started this way, the shell's path opens it as ever.
        if (External.ChromeUiaFlag.For(entry.TargetPath) is { } flag
            && InvokerLaunch.StartOutsideBaxy(new InvokerLaunch.LaunchPlan(
                entry.TargetPath!,
                string.IsNullOrWhiteSpace(entry.TargetArguments) ? flag : flag + " " + entry.TargetArguments.Trim(),
                Path.GetDirectoryName(entry.TargetPath!) ?? Environment.SystemDirectory)) > 0)
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
        return InvokerLaunch.StartOutsideBaxy(FileLaunchPlan(executable, filePath)) > 0
            ? FileActivation.Outcome.Issued
            : FileActivation.Outcome.Refused;
    }

    // Revisión nb-q-apps2: Process.Start from the core handed the application every inheritable handle of the core (its
    // stdio pipes among them) and left it in the core's kill-on-close job. It starts as InvokerLaunch starts the
    // person's programs: nothing inherited, out of the job, in its own folder, the file its one quoted argument.
    internal static InvokerLaunch.LaunchPlan FileLaunchPlan(string executable, string filePath) =>
        new(executable, "\"" + filePath + "\"", Path.GetDirectoryName(executable) ?? Environment.SystemDirectory);

    public long ForegroundWindow() => ForegroundHandBack.Foreground();

    public long PersonWorkingIn(long window) => ForegroundHandBack.PersonWorkingIn(window);

    public bool ShowAboveWithoutActivation(long window, long personWindow) =>
        ForegroundHandBack.ShowAboveWithoutActivation(window, personWindow);

    public int WindowProcessId(long windowHandle) => ForegroundHandBack.ProcessOf(windowHandle);

    public ForegroundHandBack.GuardStamp FrontGuardStamp() => ForegroundHandBack.Stamp();

    public bool FrontGuardInterrupted(ForegroundHandBack.GuardStamp stamp) => ForegroundHandBack.Interrupted(stamp);

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
            return burst.MayAct && burst.HoldsWindow && keyboard.Holds(handle)
                && keyboard.PressChord([0x11, 0x4E], () => burst.MayAct && keyboard.Holds(handle)) == 4;
        }
        finally
        {
            _ = burst.Restore();
        }
    }

    public async ValueTask<bool> IssueDismissStartAsync(long windowHandle, CancellationToken cancellationToken)
    {
        var keyboard = new External.WindowsDesktopKeyboard();
        nint handle = checked((nint)windowHandle);
        External.IInputBurst burst = await keyboard.FrontAsync(handle, cancellationToken).ConfigureAwait(false);
        try
        {
            // Escape, pressed and released: two events.
            return burst.MayAct && burst.HoldsWindow && keyboard.Holds(handle)
                && keyboard.PressChord([0x1B], () => burst.MayAct && keyboard.Holds(handle)) == 2;
        }
        finally
        {
            _ = burst.Restore();
        }
    }

    // Renew al máximo (nuevo2, nuevo4): the UI Automation worker that reads a window's tab strip, started with the launch
    // of a «nuevo» (PrewarmTabStrip) and kept; a read the opening left behind past its budget frees it within
    // TabStripWorkerHang (a worker that never answers is replaced).
    private static readonly Lazy<External.UiaWorkerHost> TabStripWorker = new(static () => new External.UiaWorkerHost());
    private static readonly object TabStripWarmLock = new();
    private static Task? s_tabStripWarm;
    internal static readonly TimeSpan TabStripWorkerHang = TimeSpan.FromSeconds(10);

    // $args[0]: the window; $args[1]: the step, «strip» (whether a Tab holds a TabItem), «count» (the most TabItems
    // one strip holds, PC-F8 cierre), «command» (whether a toggle
    // takes Ctrl+N and the strip shows its add button) or «add» (the press); $args[2]: the press's deadline, in UTC
    // ticks. Only reads, and in «add» one Invoke of the add button, never past its deadline less 200 ms; never a key, never
    // a tab of the window selected or closed. The add button: an enabled, shown, invokable Button child of the strip (no
    // scroll RepeatButton) on the tabs' row, right after the last shown tab (before the first in a right-to-left strip),
    // within three rows of it; a ribbon's «File» before its tabs, or a button far from them, never is. Its last JSON line
    // is the answer; any failure before the press is «shortcut» (Ctrl+N, as before), after it «added».
    internal const string TabStripScript = """
        $ErrorActionPreference='Stop'
        $mode=[string]$args[1]
        $phase='read'
        try {
          Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
          $AE=[System.Windows.Automation.AutomationElement]
          $CT=[System.Windows.Automation.ControlType]
          $scope=[System.Windows.Automation.TreeScope]
          function Kind($type){ New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty,$type) }
          $root=$AE::FromHandle([IntPtr][long]$args[0])
          $strips=@()
          foreach($tab in $root.FindAll($scope::Descendants,(Kind $CT::Tab))){
            if($null -ne $tab.FindFirst($scope::Descendants,(Kind $CT::TabItem))){ $strips+=$tab }
          }
          if($mode -eq 'strip'){ if($strips.Count -gt 0){ '{"strip":true}' } else { '{"strip":false}' }; return }
          if($mode -eq 'count'){ $n=0; foreach($s in $strips){ $c=@($s.FindAll($scope::Descendants,(Kind $CT::TabItem))).Count; if($c -gt $n){ $n=$c } }; '{"tabs":'+$n+'}'; return }
          if($strips.Count -eq 0){ '{"outcome":"shortcut"}'; return }
          function CommandOutcome([bool]$hasAdd,[bool]$shortcutTaken){
            if($hasAdd){ '{"outcome":"add"}' } elseif($shortcutTaken){ '{"outcome":"none"}' } else { '{"outcome":"shortcut"}' }
          }
          function AddButton($strip){
            $items=@($strip.FindAll($scope::Descendants,(Kind $CT::TabItem)) | Where-Object { -not $_.Current.IsOffscreen -and -not $_.Current.BoundingRectangle.IsEmpty })
            if($items.Count -eq 0){ return $null }
            $top=[double]::MaxValue; $bottom=[double]::MinValue; $left=[double]::MaxValue; $right=[double]::MinValue
            foreach($item in $items){
              $r=$item.Current.BoundingRectangle
              $top=[Math]::Min($top,$r.Top); $bottom=[Math]::Max($bottom,$r.Bottom); $left=[Math]::Min($left,$r.Left); $right=[Math]::Max($right,$r.Right)
            }
            if($bottom -le $top){ return $null }
            $rtl=$items.Count -gt 1 -and $items[$items.Count-1].Current.BoundingRectangle.Left -lt $items[0].Current.BoundingRectangle.Left
            $reach=3*($bottom-$top)
            foreach($button in $strip.FindAll($scope::Children,(Kind $CT::Button))){
              $current=$button.Current
              if(-not $current.IsEnabled -or $current.IsOffscreen -or [string]$current.ClassName -match 'RepeatButton' -or -not [bool]$button.GetCurrentPropertyValue($AE::IsInvokePatternAvailableProperty)){ continue }
              $r=$current.BoundingRectangle
              if($r.IsEmpty){ continue }
              $middle=($r.Top+$r.Bottom)/2
              if($middle -lt $top -or $middle -gt $bottom){ continue }
              if($rtl){ $gap=$left-$r.Right } else { $gap=$r.Left-$right }
              if($gap -ge -2 -and $gap -le $reach){ return $button }
            }
            return $null
          }
          if($mode -eq 'command'){
            $toggle=New-Object System.Windows.Automation.PropertyCondition($AE::IsTogglePatternAvailableProperty,$true)
            $taken=$false
            foreach($button in $root.FindAll($scope::Descendants,(New-Object System.Windows.Automation.AndCondition((Kind $CT::Button),$toggle)))){
              $current=$button.Current
              $shown=[regex]::Match([string]$current.Name,'\(([^()]*)\)\s*$').Groups[1].Value
              foreach($key in @([string]$current.AcceleratorKey,$shown)){ if($key -match '^\s*(Ctrl|Control|Strg)\s*\+\s*N\s*$'){ $taken=$true } }
            }
          }
          $add=$null; $strip=$null
          foreach($candidate in $strips){
            $found=AddButton $candidate
            if($null -ne $found){ $add=$found; $strip=$candidate; break }
          }
          if($mode -eq 'command'){ CommandOutcome ($null -ne $add) $taken; return }
          if($mode -ne 'add' -or $null -eq $add){ '{"outcome":"shortcut"}'; return }
          $deadline=[long]$args[2]
          function Items(){ @($strip.FindAll($scope::Descendants,(Kind $CT::TabItem)) | ForEach-Object {
            $selected=$false; try { $selected=$_.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected } catch {}
            [pscustomobject]@{ id=[string]::Join('.',$_.GetRuntimeId()); selected=$selected } }) }
          $before=@(Items)
          if([DateTime]::UtcNow.Ticks -ge $deadline-2000000){ '{"outcome":"shortcut"}'; return }
          $phase='press'
          $add.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
          while([DateTime]::UtcNow.Ticks -lt $deadline-600000){
            Start-Sleep -Milliseconds 50
            $now=@(Items); $picked=@($now | Where-Object { $_.selected })
            if($now.Count -eq $before.Count+1 -and $picked.Count -eq 1 -and @($before | ForEach-Object { $_.id }) -notcontains $picked[0].id){
              $documents=@($root.FindAll($scope::Descendants,(Kind $CT::Document)) | Where-Object { -not $_.Current.IsOffscreen })
              $empty=$documents.Count -gt 0
              foreach($document in $documents){
                $length=-1; try { $length=$document.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern).DocumentRange.GetText(1).Length } catch {}
                if($length -ne 0){ $empty=$false }
              }
              if($empty){ '{"outcome":"added","newEmpty":true}'; return }
            }
          }
          '{"outcome":"added","newEmpty":false}'
        } catch {
          if($phase -eq 'press'){ '{"outcome":"added","newEmpty":false}' } else { '{"outcome":"shortcut"}' }
        }
        """;

    public void PrewarmTabStrip() => _ = TabStripWarm();

    // PC-F8 cierre: the Core starts the reader with the window provider, so a close finds it ready.
    internal static void PrewarmTabStripWorker() => _ = TabStripWarm();

    private static Task TabStripWarm()
    {
        lock (TabStripWarmLock)
        {
            if (s_tabStripWarm is null || s_tabStripWarm.IsFaulted || s_tabStripWarm.IsCanceled)
            {
                s_tabStripWarm = Task.Run(static async () =>
                    await TabStripWorker.Value.PrewarmAsync(CancellationToken.None).ConfigureAwait(false));
            }

            return s_tabStripWarm;
        }
    }

    // One step of the tab strip's script within «within», its start included: its last JSON line, or null when nothing was
    // sent (the worker did not start in time). A step sent and not answered in time throws TimeoutException: it is left
    // behind (observed, never rethrown), and a press so left never comes after its deadline.
    private static async ValueTask<string?> RunTabStripAsync(
        long windowHandle,
        string step,
        TimeSpan within,
        CancellationToken cancellationToken)
    {
        if (within <= TimeSpan.Zero)
        {
            return null;
        }

        long deadline = DateTime.UtcNow.Ticks + within.Ticks;
        long started = Stopwatch.GetTimestamp();
        try
        {
            await TabStripWarm().WaitAsync(within, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            return null;
        }

        TimeSpan left = within - Stopwatch.GetElapsedTime(started);
        if (left <= TimeSpan.Zero)
        {
            return null;
        }

        Task<External.ExternalProcessResult> run = External.UiaWorkerScript.RunAsync(
            TabStripWorker.Value,
            TabStripScript,
            [
                windowHandle.ToString(CultureInfo.InvariantCulture),
                step,
                deadline.ToString(CultureInfo.InvariantCulture),
            ],
            TabStripWorkerHang,
            cancellationToken).AsTask();
        _ = run.ContinueWith(
            static task => _ = task.Exception,
            CancellationToken.None,
            TaskContinuationOptions.OnlyOnFaulted | TaskContinuationOptions.ExecuteSynchronously,
            TaskScheduler.Default);
        return (await run.WaitAsync(left, cancellationToken).ConfigureAwait(false)).Output;
    }

    public async ValueTask<bool> ShowsTabStripAsync(long windowHandle, TimeSpan within, CancellationToken cancellationToken) =>
        await RunTabStripAsync(windowHandle, "strip", within, cancellationToken).ConfigureAwait(false) is { } line
        && ReadTabStripShown(line);

    public async ValueTask<TabStripCommand> ReadTabStripCommandAsync(
        long windowHandle,
        TimeSpan within,
        CancellationToken cancellationToken)
    {
        TabStripCommand answer = await RunTabStripAsync(windowHandle, "command", within, cancellationToken)
            .ConfigureAwait(false) is { } line ? ReadTabStripAnswer(line) : TabStripCommand.ShortcutIsNew;
        return answer is TabStripCommand.NoNewCommand or TabStripCommand.AddButtonShown ? answer : TabStripCommand.ShortcutIsNew;
    }

    public async ValueTask<TabStripCommand> NewTabFromStripAsync(
        long windowHandle,
        TimeSpan within,
        CancellationToken cancellationToken)
    {
        TabStripCommand answer = await RunTabStripAsync(windowHandle, "add", within, cancellationToken)
            .ConfigureAwait(false) is { } line ? ReadTabStripAnswer(line) : TabStripCommand.ShortcutIsNew;
        return answer is TabStripCommand.TabAdded or TabStripCommand.NewEmptyTabShown ? answer : TabStripCommand.ShortcutIsNew;
    }

    // The probe's answer: only «strip: true» is a tab strip shown.
    // PC-F8 cierre (acotado): how many tabs (or documents) the window's widest tab strip holds, 0 with none; null when
    // it cannot be read within «within» (app.close then keeps the yes).
    internal static int? CountTabs(long windowHandle, TimeSpan within)
    {
        try
        {
            return RunTabStripAsync(windowHandle, "count", within, CancellationToken.None).AsTask().GetAwaiter().GetResult()
                is { } line ? ReadTabCount(line) : null;
        }
        catch (Exception exception) when (exception is TimeoutException or InvalidOperationException
            or System.ComponentModel.Win32Exception or IOException)
        {
            return null;
        }
    }

    internal static int? ReadTabCount(string line)
    {
        try
        {
            using JsonDocument answer = JsonDocument.Parse(line.Length > 0 ? line : "{}");
            return answer.RootElement.ValueKind == JsonValueKind.Object
                && answer.RootElement.TryGetProperty("tabs", out JsonElement tabs)
                && tabs.ValueKind == JsonValueKind.Number && tabs.TryGetInt32(out int count) && count >= 0
                    ? count
                    : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    internal static bool ReadTabStripShown(string line)
    {
        try
        {
            using JsonDocument answer = JsonDocument.Parse(line.Length > 0 ? line : "{}");
            return answer.RootElement.ValueKind == JsonValueKind.Object
                && answer.RootElement.TryGetProperty("strip", out JsonElement strip) && strip.ValueKind == JsonValueKind.True;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    // The script's answer; anything else is no answer (Ctrl+N, as before).
    internal static TabStripCommand ReadTabStripAnswer(string line)
    {
        try
        {
            using JsonDocument answer = JsonDocument.Parse(line.Length > 0 ? line : "{}");
            JsonElement root = answer.RootElement;
            string? outcome = root.ValueKind == JsonValueKind.Object
                && root.TryGetProperty("outcome", out JsonElement value) && value.ValueKind == JsonValueKind.String
                    ? value.GetString() : null;
            bool newEmpty = root.ValueKind == JsonValueKind.Object
                && root.TryGetProperty("newEmpty", out JsonElement empty) && empty.ValueKind == JsonValueKind.True;
            return outcome switch
            {
                "none" => TabStripCommand.NoNewCommand,
                "add" => TabStripCommand.AddButtonShown,
                "added" => newEmpty ? TabStripCommand.NewEmptyTabShown : TabStripCommand.TabAdded,
                _ => TabStripCommand.ShortcutIsNew,
            };
        }
        catch (JsonException)
        {
            return TabStripCommand.ShortcutIsNew;
        }
    }

    public bool IsOwnedWindow(long windowHandle) => GetWindow(checked((nint)windowHandle), 4) != 0;

    public bool CloseOwnedDialog(long windowHandle) => External.WindowWitness.Close(checked((nint)windowHandle));

    public IWindowEventWatch? WatchWindowEvents(IReadOnlyCollection<int> processes) => WindowEventWatch.Start(processes);

    // WS_CAPTION (0x00C00000, both bits), or WS_THICKFRAME (0x00040000) with WS_MINIMIZEBOX (0x00020000): a window a
    // person moves, resizes or minimizes; a splash has neither. WS_EX_TOOLWINDOW (0x80) is never one.
    public bool IsMainWindow(long windowHandle)
    {
        nint window = checked((nint)windowHandle);
        if (window == 0 || !IsWindowVisible(window) || IsCloaked(window) || GetWindow(window, 4) != 0)
            return false;
        long style = GetWindowLongPtr(window, -16).ToInt64();
        long extended = GetWindowLongPtr(window, -20).ToInt64();
        return (extended & 0x80) == 0
            && ((style & 0x00C00000) == 0x00C00000 || (style & 0x00060000) == 0x00060000);
    }

    // BAXY Renew cu (C18): the window's text fields (children whose class is an Edit or a RichEdit), each asked its
    // length (WM_GETTEXTLENGTH, 500 ms at most, never a hung window's wait): true only with one at least and all empty.
    public bool HoldsNoText(long windowHandle)
    {
        int fields = 0;
        bool holdsText = false;
        EnumWindowsProc callback = (child, _) =>
        {
            if (!ReadClassName(child).Contains("Edit", StringComparison.OrdinalIgnoreCase))
                return true;
            fields++;
            if (SendMessageTimeout(child, 0x000E, 0, 0, 0x0002, 500, out nint length) == 0 || length != 0)
            {
                holdsText = true;
                return false;
            }

            return true;
        };
        _ = EnumChildWindows(checked((nint)windowHandle), callback, nint.Zero);
        GC.KeepAlive(callback);
        return fields > 0 && !holdsText;
    }

    // Renew al máximo (rendimiento): the same text fields as HoldsNoText, each with whether Windows shows it (it and
    // its parents visible) and, only when shown, whether it answered an empty length (WM_GETTEXTLENGTH, 500 ms at most).
    public IReadOnlyList<TextFieldObservation> TextFields(long windowHandle)
    {
        var fields = new List<TextFieldObservation>();
        EnumWindowsProc callback = (child, _) =>
        {
            if (!ReadClassName(child).Contains("Edit", StringComparison.OrdinalIgnoreCase))
                return true;
            bool shown = IsWindowVisible(child);
            bool empty = shown && SendMessageTimeout(child, 0x000E, 0, 0, 0x0002, 500, out nint length) != 0
                && length == 0;
            fields.Add(new TextFieldObservation(child, shown, empty));
            return true;
        };
        _ = EnumChildWindows(checked((nint)windowHandle), callback, nint.Zero);
        GC.KeepAlive(callback);
        return fields;
    }

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
            if (IsIconic(handle))
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

        // e2e 2026-10-19: with an invisible window of a service in front (GameInputSvc's, after Steam) the attached
        // request is refused and every app.open in front ended behind it; the front is then won as a hand-back is.
        if (GetForegroundWindow() != handle)
            _ = External.ForegroundRight.Give(handle);
    }

    public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

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

    // The window that shows a console program hosted by a terminal (Windows Terminal, the default terminal of Windows 11):
    // Windows gives the program's own process a pseudo-console window (class PseudoConsoleWindow) owned (GW_OWNER) by the
    // terminal's window, when that window is on screen. 0 for a program with no hosted console. Nothing is guessed from
    // names or times: the link is Windows' own owner relation (measured 2026-10-18: cmd.exe's PseudoConsoleWindow owned by
    // the CASCADIA_HOSTING_WINDOW_CLASS window of WindowsTerminal.exe).
    private static nint TerminalHosting(int processId)
    {
        nint hosting = 0;
        EnumWindowsProc callback = (window, _) =>
        {
            GetWindowThreadProcessId(window, out uint owner);
            if (owner != unchecked((uint)processId)
                || !string.Equals(ReadClassName(window), PseudoConsoleWindowClass, StringComparison.Ordinal))
                return true;
            nint shown = GetWindow(window, 4);
            if (shown == 0 || !IsWindowVisible(shown) || IsCloaked(shown))
                return true;
            hosting = shown;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        GC.KeepAlive(callback);
        return hosting;
    }

    private const string PseudoConsoleWindowClass = "PseudoConsoleWindow";

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

    [LibraryImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
    private static partial nint GetWindowLongPtr(nint window, int index);

    [LibraryImport("user32.dll", EntryPoint = "SendMessageTimeoutW")]
    private static partial nint SendMessageTimeout(
        nint window, uint message, nint wParam, nint lParam, uint flags, uint timeout, out nint result);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextW")]
    private static unsafe partial int GetWindowText(nint window, char* text, int capacity);

    [LibraryImport("user32.dll", EntryPoint = "GetClassNameW")]
    private static unsafe partial int GetClassName(nint window, char* buffer, int capacity);

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

    // Ronda final 25: a window is restored only when minimized (SW_RESTORE on a maximized one un-maximizes it).
    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint window);
}
