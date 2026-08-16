namespace Baxy.Providers.Windows.Applications;

public sealed class WindowsApplicationOpenProvider : IApplicationOpenProvider
{
    private const string DisplayName = "Bloc de notas";

    private readonly IApplicationLauncher _launcher;
    private readonly IApplicationOpenVerifier _verifier;

    public WindowsApplicationOpenProvider()
        : this(GetDefaultStateDirectory())
    {
    }

    public WindowsApplicationOpenProvider(string stateDirectory)
        : this(
            new WindowsApplicationLauncher(stateDirectory),
            new WindowsApplicationOpenVerifier())
    {
    }

    public WindowsApplicationOpenProvider(
        IApplicationLauncher launcher,
        IApplicationOpenVerifier verifier)
    {
        _launcher = launcher ?? throw new ArgumentNullException(nameof(launcher));
        _verifier = verifier ?? throw new ArgumentNullException(nameof(verifier));
    }

    public async ValueTask<ApplicationOpenResult> OpenAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        ApplicationLaunchReceipt receipt = await _launcher.LaunchAsync(
            request,
            cancellationToken).ConfigureAwait(false);

        bool effectObserved = receipt.LaunchIssued || receipt.ReusedExisting;
        if (receipt.ErrorCode is not null)
        {
            return new ApplicationOpenResult(
                Succeeded: effectObserved,
                Verified: false,
                DisplayName,
                AlreadyRunning: receipt.ReusedExisting,
                receipt.ProcessId,
                receipt.WindowHandle,
                receipt.ErrorCode,
                receipt);
        }

        ApplicationVerificationResult verification = await _verifier.VerifyAsync(
            request,
            receipt,
            cancellationToken).ConfigureAwait(false);

        return new ApplicationOpenResult(
            Succeeded: effectObserved,
            verification.Verified,
            DisplayName,
            AlreadyRunning: receipt.ReusedExisting,
            verification.ProcessId ?? receipt.ProcessId,
            verification.WindowHandle ?? receipt.WindowHandle,
            verification.ErrorCode,
            receipt);
    }

    private static string GetDefaultStateDirectory()
    {
        string localApplicationData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(localApplicationData, "BAXY", "app-open-state");
    }
}
