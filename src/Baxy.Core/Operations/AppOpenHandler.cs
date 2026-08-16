using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Core.Operations;

internal sealed class AppOpenHandler(IApplicationOpenProvider provider) : IOperationHandler
{
    private readonly IApplicationOpenProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("app.open");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        OpenApplicationArguments arguments;
        try
        {
            arguments = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.OpenApplicationArguments)
                ?? throw new JsonException("Arguments cannot be null.");
        }
        catch (JsonException)
        {
            return OperationOutcome.Failure("invalid_arguments");
        }

        if (!ApplicationIds.IsValidRequest(arguments.AppId))
        {
            return OperationOutcome.Failure("invalid_application");
        }

        ApplicationOpenResult providerResult = await _provider.OpenAsync(
            new ApplicationOpenRequest(arguments.AppId, invocation.InvocationId),
            cancellationToken).ConfigureAwait(false);

        if (!providerResult.Succeeded || !providerResult.Verified)
        {
            string errorCode = NormalizeErrorCode(providerResult.ErrorCode, providerResult.Verified);
            return OperationOutcome.Failure(
                errorCode,
                effectMayHaveOccurred: providerResult.Succeeded);
        }

        if (!HasConsistentSuccessEvidence(invocation, arguments, providerResult))
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        var result = new OpenApplicationResult(
            arguments.AppId,
            providerResult.DisplayName,
            providerResult.AlreadyRunning,
            providerResult.ProcessId.GetValueOrDefault(),
            providerResult.WindowHandle.GetValueOrDefault());
        JsonElement serialized = JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.OpenApplicationResult);
        return OperationOutcome.Success(serialized);
    }

    private static bool HasConsistentSuccessEvidence(
        OperationInvocation invocation,
        OpenApplicationArguments arguments,
        ApplicationOpenResult result)
    {
        ApplicationLaunchReceipt? receipt = result.Receipt;
        bool hasPackageFamily = !string.IsNullOrWhiteSpace(receipt?.PackageFamilyName);
        bool hasPackageFullName = !string.IsNullOrWhiteSpace(receipt?.PackageFullName);

        return result.ErrorCode is null
            && !string.IsNullOrWhiteSpace(result.DisplayName)
            && result.DisplayName.Length <= 256
            && result.ProcessId is > 0
            && result.WindowHandle is > 0
            && receipt is not null
            && receipt.ErrorCode is null
            && string.Equals(
                receipt.InvocationId,
                invocation.InvocationId,
                StringComparison.Ordinal)
            && string.Equals(receipt.ApplicationId, arguments.AppId, StringComparison.Ordinal)
            && receipt.ProcessId == result.ProcessId
            && receipt.ProcessCreationTimeUtcTicks is > 0
            && receipt.ProcessCreationTimeUtcTicks <= DateTime.MaxValue.Ticks
            && !string.IsNullOrWhiteSpace(receipt.ExecutablePath)
            && Path.IsPathFullyQualified(receipt.ExecutablePath)
            && (receipt.WindowHandle is null || receipt.WindowHandle == result.WindowHandle)
            && receipt.LaunchIssued != receipt.ReusedExisting
            && result.AlreadyRunning == receipt.ReusedExisting
            && hasPackageFamily == hasPackageFullName;
    }

    private static string NormalizeErrorCode(string? errorCode, bool verified)
    {
        if (!verified && string.IsNullOrWhiteSpace(errorCode))
        {
            return "verification_failed";
        }

        return errorCode switch
        {
            "app_not_found" => "app_not_found",
            "app_ambiguous" => "app_ambiguous",
            "invalid_application" => "invalid_application",
            "invalid_invocation" => "invalid_invocation",
            "inventory_failed" => "inventory_failed",
            "launch_failed" => "launch_failed",
            "state_capacity_reached" => "state_capacity_reached",
            "state_corrupt" => "state_corrupt",
            "state_unavailable" => "state_unavailable",
            "verification_failed" => "verification_failed",
            _ => "application_open_failed",
        };
    }

}
