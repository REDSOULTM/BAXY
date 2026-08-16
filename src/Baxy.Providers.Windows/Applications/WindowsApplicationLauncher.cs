using System.ComponentModel;
using System.Globalization;
using System.Security;
using System.Text;

namespace Baxy.Providers.Windows.Applications;

public sealed class WindowsApplicationLauncher : IApplicationLauncher
{
    internal const uint CreateBreakawayFromJob = 0x01000000;
    private const int ObservationAttempts = 20;
    private const int MaximumInvocationIdUtf8Bytes = 256;
    private static readonly TimeSpan ObservationDelay = TimeSpan.FromMilliseconds(100);
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    private readonly IWindowsApplicationPlatform _platform;
    private readonly ApplicationInvocationStore _store;
    private readonly Action? _afterProcessCreatedBeforeReceiptPersisted;

    public WindowsApplicationLauncher(string stateDirectory)
        : this(
            new WindowsApplicationPlatform(),
            new ApplicationInvocationStore(stateDirectory),
            afterProcessCreatedBeforeReceiptPersisted: null)
    {
    }

    internal WindowsApplicationLauncher(
        IWindowsApplicationPlatform platform,
        ApplicationInvocationStore store,
        Action? afterProcessCreatedBeforeReceiptPersisted = null)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _store = store ?? throw new ArgumentNullException(nameof(store));
        _afterProcessCreatedBeforeReceiptPersisted =
            afterProcessCreatedBeforeReceiptPersisted;
    }

    public async ValueTask<ApplicationLaunchReceipt> LaunchAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        cancellationToken.ThrowIfCancellationRequested();

        if (!string.Equals(
                request.ApplicationId,
                ApplicationIds.Notepad,
                StringComparison.Ordinal))
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.InvalidApplication);
        }

        if (!IsValidInvocationId(request.InvocationId))
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.InvalidInvocation);
        }

        IDisposable coordinator;
        try
        {
            coordinator = await _store.AcquireAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (ApplicationStateCorruptException)
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.StateCorrupt);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException)
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.StateUnavailable);
        }

        using (coordinator)
        {
            return await LaunchCoordinatedAsync(request, cancellationToken)
                .ConfigureAwait(false);
        }
    }

    private async ValueTask<ApplicationLaunchReceipt> LaunchCoordinatedAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken)
    {
        ApplicationInvocationState? state;
        try
        {
            state = _store.Load(request.InvocationId);
        }
        catch (ApplicationStateCorruptException)
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.StateCorrupt);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException)
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.StateUnavailable);
        }

        if (state is not null
            && !string.Equals(state.ApplicationId, request.ApplicationId, StringComparison.Ordinal))
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.StateCorrupt);
        }

        NotepadLaunchTarget target;
        try
        {
            target = _platform.ResolveNotepadLaunchTarget();
        }
        catch (Exception exception) when (IsTargetResolutionFailure(exception))
        {
            return FailureWithPriorEffectAwareness(
                request,
                state,
                ApplicationOpenErrorCodes.ApplicationNotFound);
        }

        List<ApplicationProcessObservation> initialInventory;
        try
        {
            initialInventory = ReadAllowedInventory(target);
        }
        catch (ApplicationInventoryException)
        {
            return FailureWithPriorEffectAwareness(
                request,
                state,
                ApplicationOpenErrorCodes.InventoryFailed);
        }

        if (state?.Receipt is { ProcessId: not null } previousReceipt)
        {
            ApplicationProcessObservation? exactProcess = initialInventory.FirstOrDefault(
                observation => NotepadIdentityPolicy.MatchesReceipt(
                    observation,
                    previousReceipt));
            if (exactProcess is not null)
            {
                return await ReuseAndPersistAsync(
                    request,
                    state,
                    exactProcess,
                    previousReceipt.LaunchIssued,
                    previousReceipt.ReusedExisting,
                    target,
                    cancellationToken).ConfigureAwait(false);
            }

            if (previousReceipt.LaunchIssued || previousReceipt.ReusedExisting)
            {
                return FailureWithPriorEffectAwareness(
                    request,
                    state,
                    ApplicationOpenErrorCodes.VerificationFailed);
            }
        }

        if (state is not null
            && (state.Receipt is null
                || state.Receipt is { LaunchIssued: true, ProcessId: null }))
        {
            ApplicationProcessObservation? reconciled;
            try
            {
                reconciled = await WaitForPriorIntentAsync(
                    state,
                    initialInventory,
                    target,
                    cancellationToken).ConfigureAwait(false);
            }
            catch (ApplicationInventoryException)
            {
                return FailureWithPriorEffectAwareness(
                    request,
                    state,
                    ApplicationOpenErrorCodes.InventoryFailed);
            }

            if (reconciled is not null)
            {
                return await ReuseAndPersistAsync(
                    request,
                    state,
                    reconciled,
                    launchIssued: true,
                    reusedExisting: false,
                    target,
                    cancellationToken).ConfigureAwait(false);
            }

            // Once an intent is durable, a crash may have happened immediately after
            // CreateProcess. Absence from a bounded inventory cannot prove that the
            // effect never occurred (packaged activation may materialize later).
            // Conservatively terminate this invocation instead of risking a duplicate.
            return FailureWithPriorEffectAwareness(
                request,
                state,
                ApplicationOpenErrorCodes.VerificationFailed);
        }

        ApplicationProcessObservation? existing = ChooseCandidate(initialInventory);
        if (existing is not null)
        {
            ApplicationInvocationState durableState = state ?? NewIntentState(
                request,
                initialInventory);
            return await ReuseAndPersistAsync(
                request,
                durableState,
                existing,
                launchIssued: false,
                reusedExisting: true,
                target,
                cancellationToken).ConfigureAwait(false);
        }

        ApplicationInvocationState intent = state is not null && state.Receipt is null
            ? state
            : NewIntentState(request, initialInventory);
        try
        {
            _store.EnsureCompletionCapacity(intent);
            _store.Save(intent);
        }
        catch (ApplicationStateCapacityException)
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.StateCapacityReached);
        }
        catch (ApplicationStateCorruptException)
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.StateCorrupt);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException)
        {
            return ErrorReceipt(request, ApplicationOpenErrorCodes.StateUnavailable);
        }

        IWindowsApplicationProcess launchedProcess;
        try
        {
            launchedProcess = _platform.CreateProcess(
                target.BootstrapExecutablePath,
                CreateBreakawayFromJob,
                inheritHandles: false,
                commandLine: null);
        }
        catch (ApplicationInventoryException)
        {
            ApplicationLaunchReceipt partial = EffectOnlyReceipt(
                request,
                ApplicationOpenErrorCodes.InventoryFailed);
            return PersistAfterEffectSafely(intent, partial);
        }
        catch (ApplicationProcessExitedException)
        {
            ApplicationLaunchReceipt partial = EffectOnlyReceipt(
                request,
                ApplicationOpenErrorCodes.VerificationFailed);
            return PersistAfterEffectSafely(intent, partial);
        }
        catch (Exception exception) when (IsLaunchFailure(exception))
        {
            ApplicationLaunchReceipt failed = ErrorReceipt(
                request,
                ApplicationOpenErrorCodes.LaunchFailed);
            return PersistAfterEffectSafely(intent, failed);
        }

        using (launchedProcess)
        {
            _afterProcessCreatedBeforeReceiptPersisted?.Invoke();

            ApplicationProcessObservation? firstObservation = null;
            try
            {
                ApplicationProcessObservation observed = launchedProcess.Observe();
                if (NotepadIdentityPolicy.IsAllowed(observed, target))
                {
                    firstObservation = observed;
                }
            }
            catch (ApplicationProcessExitedException)
            {
            }
            catch (ApplicationInventoryException)
            {
                ApplicationLaunchReceipt partial = firstObservation is null
                    ? EffectOnlyReceipt(request, ApplicationOpenErrorCodes.InventoryFailed)
                    : FromObservation(
                        request,
                        firstObservation,
                        launchIssued: true,
                        reusedExisting: false,
                    ApplicationOpenErrorCodes.InventoryFailed);
                return PersistAfterEffectSafely(intent, partial);
            }
            ApplicationProcessObservation? launchedObservation;
            try
            {
                launchedObservation = await WaitForLaunchedProcessAsync(
                    intent,
                    firstObservation,
                    target,
                    cancellationToken).ConfigureAwait(false);
            }
            catch (ApplicationInventoryException)
            {
                ApplicationLaunchReceipt partial = firstObservation is null
                    ? EffectOnlyReceipt(request, ApplicationOpenErrorCodes.InventoryFailed)
                    : FromObservation(
                        request,
                        firstObservation,
                        launchIssued: true,
                        reusedExisting: false,
                        ApplicationOpenErrorCodes.InventoryFailed);
                return PersistAfterEffectSafely(intent, partial);
            }
            catch (ApplicationProcessExitedException)
            {
                ApplicationLaunchReceipt partial = firstObservation is null
                    ? EffectOnlyReceipt(request, ApplicationOpenErrorCodes.VerificationFailed)
                    : FromObservation(
                        request,
                        firstObservation,
                        launchIssued: true,
                        reusedExisting: false,
                        ApplicationOpenErrorCodes.VerificationFailed);
                return PersistAfterEffectSafely(intent, partial);
            }

            ApplicationLaunchReceipt receipt = launchedObservation is null
                ? firstObservation is null
                    ? EffectOnlyReceipt(request, errorCode: null)
                    : FromObservation(
                        request,
                        firstObservation,
                        launchIssued: true,
                        reusedExisting: false,
                        errorCode: null)
                : FromObservation(
                    request,
                    launchedObservation,
                    launchIssued: true,
                    reusedExisting: false,
                    errorCode: null);

            return PersistAfterEffectSafely(intent, receipt);
        }
    }

    private async ValueTask<ApplicationLaunchReceipt> ReuseAndPersistAsync(
        ApplicationOpenRequest request,
        ApplicationInvocationState state,
        ApplicationProcessObservation candidate,
        bool launchIssued,
        bool reusedExisting,
        NotepadLaunchTarget target,
        CancellationToken cancellationToken)
    {
        ApplicationProcessObservation observed = candidate;
        try
        {
            observed = await WaitForWindowAsync(
                candidate,
                target,
                cancellationToken).ConfigureAwait(false);
            RequestFocusIfPossible(observed, target);
        }
        catch (ApplicationInventoryException)
        {
            ApplicationLaunchReceipt inventoryFailure = FromObservation(
                request,
                observed,
                launchIssued,
                reusedExisting,
                ApplicationOpenErrorCodes.InventoryFailed);
            return PersistAfterEffectSafely(state, inventoryFailure);
        }
        catch (ApplicationProcessExitedException)
        {
            ApplicationLaunchReceipt exited = FromObservation(
                request,
                observed,
                launchIssued,
                reusedExisting,
                ApplicationOpenErrorCodes.VerificationFailed);
            return PersistAfterEffectSafely(state, exited);
        }

        ApplicationLaunchReceipt receipt = FromObservation(
            request,
            observed,
            launchIssued,
            reusedExisting,
            errorCode: null);
        return PersistAfterEffectSafely(state, receipt);
    }

    private async ValueTask<ApplicationProcessObservation> WaitForWindowAsync(
        ApplicationProcessObservation candidate,
        NotepadLaunchTarget target,
        CancellationToken cancellationToken)
    {
        ApplicationProcessObservation last = candidate;
        for (int attempt = 0; attempt < ObservationAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (last.WindowHandle != 0 && last.WindowVisible)
            {
                return last;
            }

            if (attempt + 1 < ObservationAttempts)
            {
                await _platform.DelayAsync(ObservationDelay, cancellationToken)
                    .ConfigureAwait(false);
                List<ApplicationProcessObservation> inventory = ReadAllowedInventory(target);
                ApplicationProcessObservation? refreshed = inventory.FirstOrDefault(
                    observation => observation.ProcessId == candidate.ProcessId
                        && observation.CreationTimeUtcTicks == candidate.CreationTimeUtcTicks);
                if (refreshed is null)
                {
                    continue;
                }

                last = refreshed;
            }
        }

        return last;
    }

    private async ValueTask<ApplicationProcessObservation?> WaitForPriorIntentAsync(
        ApplicationInvocationState state,
        IReadOnlyList<ApplicationProcessObservation> initialInventory,
        NotepadLaunchTarget target,
        CancellationToken cancellationToken)
    {
        HashSet<string> baseline = new(
            state.BaselineProcessKeys,
            StringComparer.Ordinal);
        IReadOnlyList<ApplicationProcessObservation> inventory = initialInventory;

        for (int attempt = 0; attempt < ObservationAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ApplicationProcessObservation? candidate = ChooseCandidate(
                inventory.Where(observation => !baseline.Contains(ProcessKey(observation))));
            if (candidate is not null)
            {
                return await WaitForWindowAsync(candidate, target, cancellationToken)
                    .ConfigureAwait(false);
            }

            if (attempt + 1 < ObservationAttempts)
            {
                await _platform.DelayAsync(ObservationDelay, cancellationToken)
                    .ConfigureAwait(false);
                inventory = ReadAllowedInventory(target);
            }
        }

        return null;
    }

    private async ValueTask<ApplicationProcessObservation?> WaitForLaunchedProcessAsync(
        ApplicationInvocationState intent,
        ApplicationProcessObservation? firstObservation,
        NotepadLaunchTarget target,
        CancellationToken cancellationToken)
    {
        HashSet<string> baseline = new(intent.BaselineProcessKeys, StringComparer.Ordinal);
        ApplicationProcessObservation? best = firstObservation;

        for (int attempt = 0; attempt < ObservationAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            List<ApplicationProcessObservation> inventory = ReadAllowedInventory(target);
            ApplicationProcessObservation? candidate = ChooseCandidate(
                inventory.Where(observation => !baseline.Contains(ProcessKey(observation))));
            if (candidate is not null)
            {
                best = candidate;
                if (candidate.WindowHandle != 0 && candidate.WindowVisible)
                {
                    RequestFocusIfPossible(candidate, target);
                    return candidate;
                }
            }

            if (attempt + 1 < ObservationAttempts)
            {
                await _platform.DelayAsync(ObservationDelay, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return best;
    }

    private List<ApplicationProcessObservation> ReadAllowedInventory(
        NotepadLaunchTarget target)
    {
        IReadOnlyList<IWindowsApplicationProcess> processes =
            _platform.EnumerateNotepadProcesses();
        List<ApplicationProcessObservation> inventory = new(processes.Count);
        try
        {
            foreach (IWindowsApplicationProcess process in processes)
            {
                try
                {
                    ApplicationProcessObservation observation = process.Observe();
                    if (NotepadIdentityPolicy.IsAllowed(observation, target))
                    {
                        inventory.Add(observation);
                    }
                }
                catch (ApplicationProcessExitedException)
                {
                }
            }
        }
        finally
        {
            foreach (IWindowsApplicationProcess process in processes)
            {
                process.Dispose();
            }
        }

        return inventory;
    }

    private void RequestFocusIfPossible(
        ApplicationProcessObservation observation,
        NotepadLaunchTarget target)
    {
        if (observation.WindowHandle == 0 || !observation.WindowVisible)
        {
            return;
        }

        using IWindowsApplicationProcess? reopened =
            _platform.OpenProcess(observation.ProcessId);
        if (reopened is null)
        {
            return;
        }

        ApplicationProcessObservation reobserved = reopened.Observe();
        if (reobserved.CreationTimeUtcTicks != observation.CreationTimeUtcTicks
            || !NotepadIdentityPolicy.IsAllowed(reobserved, target)
            || reobserved.WindowHandle != observation.WindowHandle
            || !reobserved.WindowVisible)
        {
            return;
        }

        reopened.RequestForeground(reobserved.WindowHandle);
    }

    private ApplicationInvocationState NewIntentState(
        ApplicationOpenRequest request,
        IEnumerable<ApplicationProcessObservation> inventory) =>
        new(
            request.InvocationId,
            request.ApplicationId,
            _platform.UtcNow.UtcTicks,
            inventory.Select(ProcessKey).Distinct(StringComparer.Ordinal).ToArray(),
            Receipt: null);

    private ApplicationLaunchReceipt PersistAfterEffectSafely(
        ApplicationInvocationState state,
        ApplicationLaunchReceipt receipt)
    {
        try
        {
            _store.Save(state with { Receipt = receipt });
            return receipt;
        }
        catch (ApplicationStateCapacityException)
        {
            return receipt with { ErrorCode = ApplicationOpenErrorCodes.StateCapacityReached };
        }
        catch (ApplicationStateCorruptException)
        {
            return receipt with { ErrorCode = ApplicationOpenErrorCodes.StateCorrupt };
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException)
        {
            return receipt with { ErrorCode = ApplicationOpenErrorCodes.StateUnavailable };
        }
    }

    private ApplicationLaunchReceipt FailureWithPriorEffectAwareness(
        ApplicationOpenRequest request,
        ApplicationInvocationState? state,
        string errorCode)
    {
        if (state is null
            || state.Receipt is { LaunchIssued: false, ReusedExisting: false })
        {
            return ErrorReceipt(request, errorCode);
        }

        ApplicationLaunchReceipt uncertain = state.Receipt is { } priorReceipt
            ? priorReceipt with { ErrorCode = errorCode }
            : EffectOnlyReceipt(request, errorCode);
        return PersistAfterEffectSafely(state, uncertain);
    }

    private static ApplicationLaunchReceipt FromObservation(
        ApplicationOpenRequest request,
        ApplicationProcessObservation observation,
        bool launchIssued,
        bool reusedExisting,
        string? errorCode) =>
        new(
            request.InvocationId,
            request.ApplicationId,
            launchIssued,
            reusedExisting,
            observation.ProcessId,
            observation.CreationTimeUtcTicks,
            observation.ExecutablePath,
            observation.PackageFamilyName,
            observation.PackageFullName,
            observation.WindowHandle == 0 ? null : observation.WindowHandle.ToInt64(),
            errorCode);

    private static ApplicationLaunchReceipt EffectOnlyReceipt(
        ApplicationOpenRequest request,
        string? errorCode) =>
        new(
            request.InvocationId,
            request.ApplicationId,
            LaunchIssued: true,
            ReusedExisting: false,
            ProcessId: null,
            ProcessCreationTimeUtcTicks: null,
            ExecutablePath: null,
            PackageFamilyName: null,
            PackageFullName: null,
            WindowHandle: null,
            errorCode);

    private static ApplicationLaunchReceipt ErrorReceipt(
        ApplicationOpenRequest request,
        string errorCode) =>
        new(
            request.InvocationId,
            request.ApplicationId,
            LaunchIssued: false,
            ReusedExisting: false,
            ProcessId: null,
            ProcessCreationTimeUtcTicks: null,
            ExecutablePath: null,
            PackageFamilyName: null,
            PackageFullName: null,
            WindowHandle: null,
            errorCode);

    private static ApplicationProcessObservation? ChooseCandidate(
        IEnumerable<ApplicationProcessObservation> observations) =>
        observations
            .OrderByDescending(static observation => observation.Foreground)
            .ThenByDescending(static observation =>
                observation.WindowHandle != 0 && observation.WindowVisible)
            .ThenBy(static observation => observation.CreationTimeUtcTicks)
            .ThenBy(static observation => observation.ProcessId)
            .FirstOrDefault();

    private static string ProcessKey(ApplicationProcessObservation observation) =>
        string.Create(
            CultureInfo.InvariantCulture,
            $"{observation.ProcessId}:{observation.CreationTimeUtcTicks}");

    private static bool IsValidInvocationId(string invocationId) =>
        !string.IsNullOrWhiteSpace(invocationId)
        && Guid.TryParseExact(invocationId, "D", out Guid parsed)
        && string.Equals(parsed.ToString("D"), invocationId, StringComparison.Ordinal)
        && StrictUtf8.GetByteCount(invocationId) <= MaximumInvocationIdUtf8Bytes
        && !invocationId.Any(char.IsControl);

    private static bool IsTargetResolutionFailure(Exception exception) =>
        exception is IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException
            or SecurityException;

    private static bool IsLaunchFailure(Exception exception) =>
        exception is Win32Exception
            or InvalidOperationException
            or IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException
            or SecurityException;
}
