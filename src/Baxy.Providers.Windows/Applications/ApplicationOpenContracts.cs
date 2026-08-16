namespace Baxy.Providers.Windows.Applications;

public static class ApplicationIds
{
    public const string Notepad = "windows.notepad";
    public const string Calculator = "windows.calculator";

    public static string? DisplayName(string id) => id switch
    {
        Notepad => "Bloc de notas",
        Calculator => "Calculadora",
        _ => null,
    };

    public static bool IsValidRequest(string id)
    {
        if (string.IsNullOrWhiteSpace(id) || id.Length > 256)
        {
            return false;
        }

        foreach (char character in id)
        {
            if (char.IsControl(character)
                || character == '\uFFFD'
                || character is '\\' or '/' or ':' or ';' or '|' or '&' or '>' or '<' or '$')
            {
                return false;
            }
        }

        return true;
    }
}

public static class ApplicationOpenErrorCodes
{
    public const string InvalidApplication = "invalid_application";
    public const string InvalidInvocation = "invalid_invocation";
    public const string ApplicationNotFound = "app_not_found";
    public const string ApplicationAmbiguous = "app_ambiguous";
    public const string InventoryFailed = "inventory_failed";
    public const string LaunchFailed = "launch_failed";
    public const string VerificationFailed = "verification_failed";
    public const string StateCorrupt = "state_corrupt";
    public const string StateCapacityReached = "state_capacity_reached";
    public const string StateUnavailable = "state_unavailable";
}

public record ApplicationOpenRequest(string ApplicationId, string InvocationId);

public record ApplicationLaunchReceipt(
    string InvocationId,
    string ApplicationId,
    bool LaunchIssued,
    bool ReusedExisting,
    int? ProcessId,
    long? ProcessCreationTimeUtcTicks,
    string? ExecutablePath,
    string? PackageFamilyName,
    string? PackageFullName,
    long? WindowHandle,
    string? ErrorCode);

public record ApplicationVerificationResult(
    bool Verified,
    int? ProcessId,
    long? WindowHandle,
    string? ErrorCode);

public record ApplicationOpenResult(
    bool Succeeded,
    bool Verified,
    string DisplayName,
    bool AlreadyRunning,
    int? ProcessId,
    long? WindowHandle,
    string? ErrorCode,
    ApplicationLaunchReceipt Receipt);

public interface IApplicationLauncher
{
    ValueTask<ApplicationLaunchReceipt> LaunchAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken);
}

public interface IApplicationOpenVerifier
{
    ValueTask<ApplicationVerificationResult> VerifyAsync(
        ApplicationOpenRequest request,
        ApplicationLaunchReceipt receipt,
        CancellationToken cancellationToken);
}

public interface IApplicationOpenProvider
{
    ValueTask<ApplicationOpenResult> OpenAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken);
}

public sealed record ApplicationInstalledResult(
    string RequestedName,
    string? DisplayName,
    bool Installed,
    bool Verified,
    string? ErrorCode,
    string? InstalledVersion = null);

public sealed record ApplicationWindowStatusResult(
    string RequestedName,
    string? DisplayName,
    bool Installed,
    bool HasVisibleWindow,
    int VisibleWindowCount,
    bool Verified,
    string? ErrorCode);

public interface IApplicationInventoryProvider
{
    ValueTask<ApplicationInstalledResult> IsInstalledAsync(
        string applicationName,
        CancellationToken cancellationToken);

    ValueTask<ApplicationWindowStatusResult> GetWindowStatusAsync(
        string applicationName,
        CancellationToken cancellationToken);
}

public sealed record InstalledApplicationCatalogSnapshot(
    bool Verified,
    bool Complete,
    IReadOnlyList<string> Names);

public interface IApplicationCatalogProvider
{
    ValueTask<InstalledApplicationCatalogSnapshot> GetCatalogSnapshotAsync(
        CancellationToken cancellationToken);
}

public sealed class ApplicationOpenProviderRouter(
    IApplicationOpenProvider calculator,
    IApplicationOpenProvider installedApplication) : IApplicationOpenProvider
{
    public ValueTask<ApplicationOpenResult> OpenAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken) => request.ApplicationId switch
        {
            ApplicationIds.Calculator => calculator.OpenAsync(request, cancellationToken),
            _ => installedApplication.OpenAsync(request, cancellationToken),
        };
}
