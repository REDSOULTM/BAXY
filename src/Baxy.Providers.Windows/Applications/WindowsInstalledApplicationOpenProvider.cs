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
            _ => InstalledApplicationResolver.Resolve(request.ApplicationId, catalog),
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
        catch (Exception exception) when (exception is ApplicationInventoryException
            or InvalidOperationException
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

            InstalledApplicationObservation? focused;
            try
            {
                focused = await TryFocusAsync(
                    entry,
                    candidate,
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
        cancellationToken.ThrowIfCancellationRequested();
        if (!ApplicationIds.IsValidRequest(applicationName))
            return ([], ApplicationOpenErrorCodes.InvalidApplication);

        try
        {
            IReadOnlyList<InstalledApplicationEntry> catalog =
                await ReadCatalogAsync(cancellationToken).ConfigureAwait(false);
            // This effect prerequisite accepts only a complete installed name.
            // Do not inherit open's fuzzy ranking or application aliases.
            InstalledApplicationResolution resolution = InstalledApplicationResolver.Resolve(
                applicationName, catalog);
            if (resolution.Ambiguous)
                return ([], ApplicationOpenErrorCodes.ApplicationAmbiguous);
            if (resolution.Entry is not { } entry
                || !string.Equals(InstalledApplicationResolver.Normalize(entry.Name),
                    InstalledApplicationResolver.Normalize(applicationName), StringComparison.Ordinal))
                return ([], ApplicationOpenErrorCodes.ApplicationNotFound);
            if (!entry.AppUserModelId.Contains('!')
                && WindowsInstalledApplicationPlatform.StrongExecutablePath(entry) is null)
                return ([], "application_window_identity_unavailable");

            return (_platform.InventoryForWindowResolution(entry, cancellationToken), null);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return ([], ApplicationOpenErrorCodes.InventoryFailed);
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
        // Bringing the window to the front is asked for, never required to prove the
        // app is open: Windows refuses the handoff while a system flyout owns the
        // foreground, and REPAIR1031 lost a whole batch that way with Steam, Discord
        // and Paint visible on screen. A visible window of the bound process is the
        // observation; focus is a courtesy.
        return Observe(requireForeground: true) ?? Observe(requireForeground: false);
    }

    private static InstalledApplicationObservation? Choose(
        IReadOnlyList<InstalledApplicationObservation> observations,
        IReadOnlyList<InstalledApplicationObservation>? baseline = null)
    {
        IEnumerable<InstalledApplicationObservation> candidates = observations
            .Where(static item => item.Visible && Path.IsPathFullyQualified(item.ExecutablePath));
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

internal sealed record InstalledApplicationEntry(
    string Name,
    string AppUserModelId,
    string? TargetPath = null);

internal sealed record InstalledApplicationObservation(
    int ProcessId,
    long ProcessCreationTimeUtcTicks,
    string ExecutablePath,
    long WindowHandle,
    bool Visible,
    bool Foreground,
    string? ProcessName = null);

internal interface IInstalledApplicationPlatform
{
    ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
        CancellationToken cancellationToken);

    IReadOnlyList<InstalledApplicationObservation> Inventory(InstalledApplicationEntry entry);

    IReadOnlyList<InstalledApplicationObservation> InventoryForWindowResolution(
        InstalledApplicationEntry entry,
        CancellationToken cancellationToken) =>
        throw new ApplicationInventoryException("Strong application window identity is unavailable.");

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
            try {
                foreach ($app in $apps) {
                    if ($duplicateIds.ContainsKey($app.AppID)) {
                        $targets[$app.AppID]=$app.ShellItem.ExtendedProperty('System.Link.TargetParsingPath')
                    }
                }
            } catch {
                # Missing Shell metadata preserves the original ambiguity.
                $targets=@{}
            }
            @($apps | ForEach-Object {
                [pscustomobject]@{ Name=$_.Name; AppID=$_.AppID; TargetPath=$targets[$_.AppID] }
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
                entries.Add(new InstalledApplicationEntry(name, appId, targetPath));
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

    private IReadOnlyList<InstalledApplicationObservation> Inventory(
        InstalledApplicationEntry entry,
        bool strongIdentityOnly,
        CancellationToken cancellationToken)
    {
        bool packaged = entry.AppUserModelId.Contains('!');
        string? expectedExecutable = strongIdentityOnly && !packaged
            ? StrongExecutablePath(entry) : null;
        if (strongIdentityOnly && !packaged && expectedExecutable is null)
            throw new ApplicationInventoryException("The installed executable identity is unavailable.");
        Process[] processes = Process.GetProcesses();
        var observations = new List<InstalledApplicationObservation>();
        try
        {
            foreach (Process process in processes)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    process.Refresh();
                    nint[]? ownedWindows = strongIdentityOnly
                        ? VisibleTopLevelWindows(process.Id, requireComplete: true) : null;
                    nint window = ownedWindows is null
                        ? process.MainWindowHandle : ownedWindows.FirstOrDefault();
                    if (window == 0 || !IsWindowVisible(window))
                    {
                        continue;
                    }

                    string? applicationId = packaged
                        ? ReadApplicationUserModelId(process.Id)
                        : null;
                    if (strongIdentityOnly
                        ? packaged && !string.Equals(entry.AppUserModelId, applicationId, StringComparison.Ordinal)
                        : !WindowProcessIdentifiesApplication(
                            entry, process.ProcessName, process.MainWindowTitle, applicationId))
                    {
                        continue;
                    }

                    string? executablePath = process.MainModule?.FileName;
                    if (string.IsNullOrWhiteSpace(executablePath)
                        || !Path.IsPathFullyQualified(executablePath))
                    {
                        if (strongIdentityOnly)
                            throw new ApplicationInventoryException("A visible executable could not be verified.");
                        continue;
                    }
                    if (strongIdentityOnly && !packaged
                        && !string.Equals(Path.GetFullPath(executablePath), expectedExecutable,
                            StringComparison.OrdinalIgnoreCase))
                        continue;

                    long creationTime = process.StartTime.ToUniversalTime().Ticks;
                    foreach (nint operated in ownedWindows ?? VisibleTopLevelWindows(process.Id))
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
                    if (strongIdentityOnly)
                        throw new ApplicationInventoryException("The visible application inventory was incomplete.");
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

    private static nint[] VisibleTopLevelWindows(int processId, bool requireComplete = false)
    {
        var windows = new List<(nint Handle, long Area)>();
        bool complete = true;
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window))
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner != unchecked((uint)processId))
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

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial SafeProcessHandle OpenProcess(
        uint desiredAccess, [MarshalAs(UnmanagedType.Bool)] bool inheritHandle, int processId);

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

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindowAsync(nint window, int command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint window);
}
