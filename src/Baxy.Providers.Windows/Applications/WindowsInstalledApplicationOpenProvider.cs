using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Microsoft.Win32;

namespace Baxy.Providers.Windows.Applications;

public sealed class WindowsInstalledApplicationOpenProvider :
    IApplicationOpenProvider,
    IApplicationInventoryProvider,
    IApplicationCatalogProvider
{
    private const int VerificationAttempts = 28;
    private static readonly TimeSpan ObservationDelay = TimeSpan.FromMilliseconds(100);
    private static readonly TimeSpan CatalogLifetime = TimeSpan.FromMinutes(5);

    private readonly IInstalledApplicationPlatform _platform;
    private readonly object _catalogLock = new();
    private IReadOnlyList<InstalledApplicationEntry>? _catalog;
    private Task<IReadOnlyList<InstalledApplicationEntry>>? _catalogLoadTask;
    private DateTimeOffset _catalogLoadedAt;

    public WindowsInstalledApplicationOpenProvider()
        : this(new WindowsInstalledApplicationPlatform())
    {
    }

    internal WindowsInstalledApplicationOpenProvider(IInstalledApplicationPlatform platform)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
    }

    public async ValueTask<ApplicationOpenResult> OpenAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        cancellationToken.ThrowIfCancellationRequested();
        if (!ApplicationIds.IsValidRequest(request.ApplicationId))
        {
            return Failure(request, string.Empty, ApplicationOpenErrorCodes.InvalidApplication);
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

        InstalledApplicationResolution resolution = request.ApplicationId switch
        {
            ApplicationIds.Notepad => InstalledApplicationResolver.ResolveAppId(
                "Microsoft.WindowsNotepad",
                catalog),
            ApplicationIds.Calculator => InstalledApplicationResolver.ResolveAppId(
                "Microsoft.WindowsCalculator",
                catalog),
            _ => InstalledApplicationResolver.ResolveForLaunch(request.ApplicationId, catalog),
        };
        if (resolution.Entry is null)
        {
            return Failure(
                request,
                request.ApplicationId,
                resolution.Ambiguous
                    ? ApplicationOpenErrorCodes.ApplicationAmbiguous
                    : ApplicationOpenErrorCodes.ApplicationNotFound);
        }

        InstalledApplicationEntry entry = resolution.Entry;
        IReadOnlyList<InstalledApplicationObservation> before;
        try
        {
            before = _platform.Inventory(entry);
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return Failure(request, entry.Name, ApplicationOpenErrorCodes.InventoryFailed);
        }

        InstalledApplicationObservation? existing = Choose(before);
        bool reused = existing is not null;
        if (existing is not null)
        {
            InstalledApplicationObservation? focused;
            try
            {
                focused = await TryFocusAsync(
                    entry,
                    existing,
                    cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is InvalidOperationException
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
                return Success(request, entry, focused, reused: true);
            }
        }

        bool activationIssued;
        try
        {
            activationIssued = _platform.Activate(entry);
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

        if (!activationIssued)
        {
            return Failure(
                request,
                entry.Name,
                ApplicationOpenErrorCodes.LaunchFailed,
                launchIssued: false,
                reusedExisting: reused);
        }

        for (int attempt = 0; attempt <= VerificationAttempts; attempt++)
        {
            InstalledApplicationObservation? candidate;
            try
            {
                IReadOnlyList<InstalledApplicationObservation> current = _platform.Inventory(entry);
                candidate = Choose(current, before);
            }
            catch (Exception exception) when (exception is InvalidOperationException
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

            InstalledApplicationObservation? focused;
            try
            {
                focused = await TryFocusAsync(
                    entry,
                    candidate,
                    cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is InvalidOperationException
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
                return Success(request, entry, focused, reused);
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

        InstalledApplicationResolution resolution = applicationName switch
        {
            ApplicationIds.Notepad => InstalledApplicationResolver.ResolveAppId(
                "Microsoft.WindowsNotepad", catalog),
            ApplicationIds.Calculator => InstalledApplicationResolver.ResolveAppId(
                "Microsoft.WindowsCalculator", catalog),
            _ => InstalledApplicationResolver.Resolve(applicationName, catalog),
        };
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

        // Keep a colliding Start name when the same non-path preference
        // ResolveForLaunch uses leaves exactly one identity (Steam's path
        // shortcut plus Valve.Steam.Client). Two non-path identities stay out.
        string[] safelyResolvableNames = candidates
            .GroupBy(static candidate => candidate.Key, StringComparer.Ordinal)
            .Select(SelectSnapshotName)
            .Where(static name => name is not null)
            .Select(static name => name!)
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

    private static string? SelectSnapshotName(
        IGrouping<string, (string Name, string AppUserModelId, string Key)> group)
    {
        (string Name, string AppUserModelId, string Key)[] entries = [.. group];
        IReadOnlyList<(string Name, string AppUserModelId, string Key)> chosen = entries;
        int identityCount = entries
            .Select(static item => item.AppUserModelId)
            .Distinct(StringComparer.Ordinal)
            .Count();
        if (identityCount > 1)
        {
            (string Name, string AppUserModelId, string Key)[] launchable = entries
                .Where(static item =>
                    !InstalledApplicationResolver.IsPathStyleAppUserModelId(item.AppUserModelId))
                .ToArray();
            if (launchable
                    .Select(static item => item.AppUserModelId)
                    .Distinct(StringComparer.Ordinal)
                    .Count() != 1)
            {
                return null;
            }

            chosen = launchable;
        }

        return chosen
            .OrderBy(static item => item.Name, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static item => item.Name, StringComparer.Ordinal)
            .First()
            .Name;
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

        InstalledApplicationEntry[] exactEntries = applicationName switch
        {
            ApplicationIds.Notepad or ApplicationIds.Calculator => [],
            _ => catalog
                .Where(InstalledApplicationResolver.IsUsable)
                .Where(entry => InstalledApplicationResolver.Normalize(entry.Name)
                    == InstalledApplicationResolver.Normalize(applicationName))
                .DistinctBy(
                    static entry => (
                        InstalledApplicationResolver.Normalize(entry.Name),
                        entry.AppUserModelId),
                    EqualityComparer<(string, string)>.Default)
                .ToArray(),
        };
        InstalledApplicationResolution resolution = applicationName switch
        {
            ApplicationIds.Notepad => InstalledApplicationResolver.ResolveAppId(
                "Microsoft.WindowsNotepad", catalog),
            ApplicationIds.Calculator => InstalledApplicationResolver.ResolveAppId(
                "Microsoft.WindowsCalculator", catalog),
            _ => InstalledApplicationResolver.Resolve(applicationName, catalog),
        };
        if (resolution.Ambiguous && exactEntries.Length == 0)
        {
            return new(applicationName, null, false, false, 0, false,
                ApplicationOpenErrorCodes.ApplicationAmbiguous);
        }
        if (resolution.Entry is null && exactEntries.Length == 0)
        {
            return new(applicationName, null, false, false, 0, true, null);
        }

        InstalledApplicationEntry[] entries = exactEntries.Length > 0
            ? exactEntries
            : [resolution.Entry!];
        var observations = new List<InstalledApplicationObservation>();
        try
        {
            foreach (InstalledApplicationEntry entry in entries)
            {
                observations.AddRange(_platform.Inventory(entry));
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return new(applicationName, entries[0].Name, true, false, 0, false,
                ApplicationOpenErrorCodes.InventoryFailed);
        }

        int visibleWindowCount = observations
            .Where(static observation => observation.Visible && observation.WindowHandle != 0)
            .Select(static observation => observation.WindowHandle)
            .Distinct()
            .Count();
        return new(
            applicationName,
            entries[0].Name,
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

            _catalogLoadTask ??= _platform.ReadCatalogAsync(cancellationToken).AsTask();
            loadTask = _catalogLoadTask;
        }

        try
        {
            IReadOnlyList<InstalledApplicationEntry> loaded = await loadTask
                .WaitAsync(cancellationToken)
                .ConfigureAwait(false);
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

    private async ValueTask<InstalledApplicationObservation?> TryFocusAsync(
        InstalledApplicationEntry entry,
        InstalledApplicationObservation candidate,
        CancellationToken cancellationToken)
    {
        _platform.RequestForeground(candidate.WindowHandle);
        InstalledApplicationObservation? Observe(bool requireForeground) =>
            _platform.Inventory(entry).FirstOrDefault(item =>
                item.ProcessId == candidate.ProcessId
                && item.ProcessCreationTimeUtcTicks == candidate.ProcessCreationTimeUtcTicks
                && item.WindowHandle == candidate.WindowHandle
                && item.Visible
                && (!requireForeground || item.Foreground));
        InstalledApplicationObservation? observed = Observe(requireForeground: true);
        if (observed is not null)
        {
            return observed;
        }

        await _platform.DelayAsync(ObservationDelay, cancellationToken).ConfigureAwait(false);
        return Observe(requireForeground: true) ?? Observe(requireForeground: false);
    }

    private static InstalledApplicationObservation? Choose(
        IReadOnlyList<InstalledApplicationObservation> observations,
        IReadOnlyList<InstalledApplicationObservation>? baseline = null)
    {
        IEnumerable<InstalledApplicationObservation> candidates = observations
            .Where(static item =>
                item.Visible
                && item.WindowHandle != 0
                && (item.ExecutablePath.Length == 0
                    || Path.IsPathFullyQualified(item.ExecutablePath)));
        if (baseline is not null)
        {
            InstalledApplicationObservation? created = candidates
                .Where(item => !baseline.Any(previous =>
                    previous.ProcessId == item.ProcessId
                    && previous.ProcessCreationTimeUtcTicks == item.ProcessCreationTimeUtcTicks))
                .OrderByDescending(static item => item.Foreground)
                .ThenByDescending(static item => item.ProcessCreationTimeUtcTicks)
                .FirstOrDefault();
            if (created is not null)
            {
                return created;
            }
        }

        return candidates
            .OrderByDescending(static item => item.Foreground)
            .ThenByDescending(static item => item.ProcessCreationTimeUtcTicks)
            .FirstOrDefault();
    }

    private static ApplicationOpenResult Success(
        ApplicationOpenRequest request,
        InstalledApplicationEntry entry,
        InstalledApplicationObservation observation,
        bool reused)
    {
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
            receipt);
    }

    private static ApplicationOpenResult Failure(
        ApplicationOpenRequest request,
        string displayName,
        string errorCode,
        bool launchIssued = false,
        bool reusedExisting = false)
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
            receipt);
    }
}

internal sealed record InstalledApplicationEntry(string Name, string AppUserModelId);

internal sealed record InstalledApplicationObservation(
    int ProcessId,
    long ProcessCreationTimeUtcTicks,
    string ExecutablePath,
    long WindowHandle,
    bool Visible,
    bool Foreground);

internal interface IInstalledApplicationPlatform
{
    ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
        CancellationToken cancellationToken);

    IReadOnlyList<InstalledApplicationObservation> Inventory(InstalledApplicationEntry entry);

    bool Activate(InstalledApplicationEntry entry);

    void RequestForeground(long windowHandle);

    ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
}

internal sealed record InstalledApplicationResolution(
    InstalledApplicationEntry? Entry,
    bool Ambiguous);

internal static class InstalledApplicationResolver
{
    internal static InstalledApplicationResolution ResolveAppId(
        string appIdFragment,
        IReadOnlyList<InstalledApplicationEntry> catalog)
    {
        InstalledApplicationEntry[] matches = catalog
            .Where(item => IsUsable(item)
                && item.AppUserModelId.Contains(appIdFragment, StringComparison.OrdinalIgnoreCase))
            .ToArray();
        return matches.Length switch
        {
            1 => new InstalledApplicationResolution(matches[0], false),
            > 1 => new InstalledApplicationResolution(null, true),
            _ => new InstalledApplicationResolution(null, false),
        };
    }

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

        (InstalledApplicationEntry Entry, int Score)[] ranked = entries
            .Select(item => (Entry: item, Score: Score(normalizedQuery, Normalize(item.Name))))
            .Where(static item => item.Score >= 82)
            .OrderByDescending(static item => item.Score)
            .ThenBy(static item => item.Entry.Name, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        if (ranked.Length == 0)
        {
            return new InstalledApplicationResolution(null, false);
        }

        if (ranked.Length > 1 && ranked[0].Score - ranked[1].Score < 8)
        {
            return new InstalledApplicationResolution(null, true);
        }

        return new InstalledApplicationResolution(ranked[0].Entry, false);
    }

    internal static InstalledApplicationResolution ResolveForLaunch(
        string query,
        IReadOnlyList<InstalledApplicationEntry> catalog)
    {
        InstalledApplicationResolution resolved = Resolve(query, catalog);
        if (!resolved.Ambiguous)
        {
            return resolved;
        }

        string normalizedQuery = Normalize(query);
        InstalledApplicationEntry[] exact = catalog
            .Where(static item => IsUsable(item))
            .Where(item => Normalize(item.Name) == normalizedQuery)
            .DistinctBy(static item => item.AppUserModelId, StringComparer.Ordinal)
            .OrderBy(static item => item.AppUserModelId, StringComparer.Ordinal)
            .ToArray();
        if (exact.Length == 0)
        {
            return resolved;
        }

        InstalledApplicationEntry[] notPath = exact
            .Where(static item => !IsPathStyleAppUserModelId(item.AppUserModelId))
            .ToArray();
        return new InstalledApplicationResolution(
            notPath.Length > 0 ? notPath[0] : exact[0],
            false);
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

    internal static bool IsPathStyleAppUserModelId(string appUserModelId) =>
        appUserModelId.Contains('\\')
        || appUserModelId.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)
        || appUserModelId.EndsWith(".lnk", StringComparison.OrdinalIgnoreCase);

    private static int Score(string query, string candidate)
    {
        string[] queryTokens = query.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        string[] candidateTokens = candidate.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (queryTokens.All(token => candidateTokens.Contains(token, StringComparer.Ordinal)))
        {
            return 90 - Math.Min(6, candidateTokens.Length - queryTokens.Length);
        }

        int distance = Levenshtein(query, candidate);
        int maximum = Math.Max(query.Length, candidate.Length);
        if (maximum == 0)
        {
            return 0;
        }

        int similarity = 100 - (distance * 100 / maximum);
        int permittedDistance = query.Length <= 8 ? 1 : 2;
        return distance <= permittedDistance ? Math.Max(82, similarity) : similarity;
    }

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
    private const string CatalogScript =
        "$ErrorActionPreference='Stop'; " +
        "$utf8=[System.Text.UTF8Encoding]::new($false); " +
        "[Console]::OutputEncoding=$utf8; $OutputEncoding=$utf8; " +
        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress";

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
                "Get-StartApps did not emit valid UTF-8.",
                exception);
        }

        string output = streams[0];
        string error = streams[1];
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(error) ? "Get-StartApps failed." : error.Trim());
        }

        if (string.IsNullOrWhiteSpace(output))
        {
            return [];
        }

        if (output.Contains('\uFFFD', StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "Get-StartApps emitted a Unicode replacement character.");
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
                entries.Add(new InstalledApplicationEntry(name, appId));
            }
        }

        return entries;
    }

    public IReadOnlyList<InstalledApplicationObservation> Inventory(
        InstalledApplicationEntry entry)
    {
        HashSet<string> identities = BuildProcessIdentities(entry);
        string normalizedDisplayName = InstalledApplicationResolver.Normalize(entry.Name);
        Process[] processes = Process.GetProcesses();
        var observations = new List<InstalledApplicationObservation>();
        try
        {
            foreach (Process process in processes)
            {
                try
                {
                    process.Refresh();
                    nint window = process.MainWindowHandle;
                    if (window == 0 || !IsWindowVisible(window))
                    {
                        continue;
                    }

                    string processName = InstalledApplicationResolver.Normalize(process.ProcessName);
                    string title = InstalledApplicationResolver.Normalize(process.MainWindowTitle);
                    bool identityMatch = identities.Any(identity =>
                        processName == identity
                        || (identity.Length >= 4 && processName.StartsWith(identity, StringComparison.Ordinal)));
                    bool titleMatch = WindowTitleIdentifiesApplication(
                        title,
                        normalizedDisplayName);
                    if (!identityMatch && !titleMatch)
                    {
                        continue;
                    }

                    nint operated = LargestTopLevelWindow(process.Id, includeHidden: false);
                    if (operated == 0)
                        operated = window;
                    if (operated == 0 || !IsWindowVisible(operated))
                    {
                        continue;
                    }

                    string executablePath = string.Empty;
                    try
                    {
                        executablePath = process.MainModule?.FileName ?? string.Empty;
                    }
                    catch (Exception exception) when (exception is InvalidOperationException
                        or System.ComponentModel.Win32Exception
                        or NotSupportedException)
                    {
                        executablePath = string.Empty;
                    }

                    if (executablePath.Length > 0
                        && !Path.IsPathFullyQualified(executablePath))
                    {
                        continue;
                    }

                    observations.Add(new InstalledApplicationObservation(
                        process.Id,
                        process.StartTime.ToUniversalTime().Ticks,
                        executablePath,
                        operated.ToInt64(),
                        Visible: true,
                        Foreground: GetForegroundWindow() == operated));
                }
                catch (Exception exception) when (exception is InvalidOperationException
                    or System.ComponentModel.Win32Exception
                    or NotSupportedException)
                {
                }
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

    public bool Activate(InstalledApplicationEntry entry)
    {
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

    public void RequestForeground(long windowHandle)
    {
        nint handle = checked((nint)windowHandle);
        _ = GetWindowThreadProcessId(handle, out uint processId);
        nint largest = LargestTopLevelWindow(unchecked((int)processId), includeHidden: true);
        if (largest != 0)
            handle = largest;
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

    private static nint LargestTopLevelWindow(int processId, bool includeHidden)
    {
        nint best = 0;
        long bestArea = 0;
        EnumWindowsProc callback = (window, _) =>
        {
            if (!includeHidden && !IsWindowVisible(window))
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner != unchecked((uint)processId))
                return true;
            if (!GetWindowRect(window, out Rect rect))
                return true;
            long area = (long)Math.Max(0, rect.Right - rect.Left)
                * Math.Max(0, rect.Bottom - rect.Top);
            if (area > bestArea)
            {
                bestArea = area;
                best = window;
            }
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return best;
    }

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
    private static partial bool GetWindowRect(nint window, out Rect rect);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

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

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindowAsync(nint window, int command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint window);
}
