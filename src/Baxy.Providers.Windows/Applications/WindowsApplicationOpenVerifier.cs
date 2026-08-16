namespace Baxy.Providers.Windows.Applications;

public sealed class WindowsApplicationOpenVerifier : IApplicationOpenVerifier
{
    private const int VerificationAttempts = 20;
    private static readonly TimeSpan VerificationDelay = TimeSpan.FromMilliseconds(100);

    private readonly IWindowsApplicationPlatform _platform;

    public WindowsApplicationOpenVerifier()
        : this(new WindowsApplicationPlatform())
    {
    }

    internal WindowsApplicationOpenVerifier(IWindowsApplicationPlatform platform)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
    }

    public async ValueTask<ApplicationVerificationResult> VerifyAsync(
        ApplicationOpenRequest request,
        ApplicationLaunchReceipt receipt,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(receipt);
        cancellationToken.ThrowIfCancellationRequested();

        if (!string.Equals(request.ApplicationId, ApplicationIds.Notepad, StringComparison.Ordinal)
            || !string.Equals(receipt.ApplicationId, request.ApplicationId, StringComparison.Ordinal)
            || !string.Equals(receipt.InvocationId, request.InvocationId, StringComparison.Ordinal)
            || receipt.ProcessId is not int processId
            || receipt.ProcessCreationTimeUtcTicks is not long creationTimeUtcTicks
            || string.IsNullOrWhiteSpace(receipt.ExecutablePath))
        {
            return Failed(receipt.ErrorCode ?? ApplicationOpenErrorCodes.VerificationFailed);
        }

        NotepadLaunchTarget target;
        try
        {
            target = _platform.ResolveNotepadLaunchTarget();
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException
            or System.Security.SecurityException)
        {
            return Failed(ApplicationOpenErrorCodes.ApplicationNotFound);
        }

        long? latestWindow = receipt.WindowHandle;
        for (int attempt = 0; attempt < VerificationAttempts; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            ApplicationProcessObservation? observation;
            try
            {
                using IWindowsApplicationProcess? reopened = _platform.OpenProcess(processId);
                if (reopened is null)
                {
                    return Failed(ApplicationOpenErrorCodes.VerificationFailed);
                }

                observation = reopened.Observe();
                if (observation.CreationTimeUtcTicks != creationTimeUtcTicks
                    || !NotepadIdentityPolicy.IsAllowed(observation, target)
                    || !NotepadIdentityPolicy.MatchesReceipt(observation, receipt))
                {
                    return Failed(ApplicationOpenErrorCodes.VerificationFailed);
                }

                latestWindow = observation.WindowHandle == 0
                    ? latestWindow
                    : observation.WindowHandle.ToInt64();

                // A packaged cold launch may replace its bootstrap HWND while
                // retaining the exact PID, creation time, executable and package
                // identity bound by the receipt. Observe() independently proves
                // that the current main HWND belongs to that same process, so bind
                // the converged HWND instead of requiring a transient handle.
                if (observation.WindowHandle != 0
                    && observation.WindowVisible
                    && observation.Foreground)
                {
                    return new ApplicationVerificationResult(
                        Verified: true,
                        processId,
                        observation.WindowHandle.ToInt64(),
                        ErrorCode: null);
                }

                if (observation.WindowHandle != 0
                    && observation.WindowVisible)
                {
                    reopened.RequestForeground(observation.WindowHandle);
                }
            }
            catch (ApplicationProcessExitedException)
            {
                return Failed(ApplicationOpenErrorCodes.VerificationFailed);
            }
            catch (ApplicationInventoryException)
            {
                return Failed(ApplicationOpenErrorCodes.InventoryFailed);
            }

            if (attempt + 1 < VerificationAttempts)
            {
                await _platform.DelayAsync(VerificationDelay, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return new ApplicationVerificationResult(
            Verified: false,
            processId,
            latestWindow,
            ApplicationOpenErrorCodes.VerificationFailed);
    }

    private static ApplicationVerificationResult Failed(string errorCode) =>
        new(
            Verified: false,
            ProcessId: null,
            WindowHandle: null,
            errorCode);
}
