using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

internal sealed class AppOpenHandler(
    IApplicationOpenProvider provider, LaunchProvenance? provenance = null, IApplicationPlaceOpener? places = null)
    : IOperationHandler
{
    private readonly IApplicationOpenProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));
    private readonly LaunchProvenance _provenance = provenance ?? LaunchProvenance.Shared;
    private readonly IApplicationPlaceOpener _places = places ?? new ShellApplicationPlaceOpener();

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

        // Estabilización, encargo C: a place is opened only by the address its application's data declare
        // (ApplicationPlaces); a place, a value or an application the data do not declare opens nothing.
        string? placeAddress = null;
        if (arguments.Place is not null || arguments.PlaceValue is not null)
        {
            placeAddress = ApplicationPlaces.Address(arguments.AppId, arguments.Place, arguments.PlaceValue);
            if (placeAddress is null)
            {
                return OperationOutcome.Failure("invalid_arguments");
            }
        }

        // v3 r22 revisión: the moment before the opening. A process created before it was not launched by this
        // opening, whatever the provider's reuse flag says (a process already running with no visible window, a
        // window that appears inside a process the person was already using), and never counts as BAXY's.
        // v3 r22 revisión 2: the person's own input into what this opening launches is watched from before it.
        _provenance.PrepareLaunch();
        long openingStartedTicks = DateTime.UtcNow.Ticks;
        ApplicationOpenResult providerResult = await _provider.OpenAsync(
            new ApplicationOpenRequest(
                arguments.AppId,
                invocation.InvocationId,
                arguments.Foreground == true,
                arguments.ForControl == true,
                NewDocument: arguments.NewDocument == true),
            cancellationToken).ConfigureAwait(false);

        if (!providerResult.Succeeded || !providerResult.Verified)
        {
            string errorCode = NormalizeErrorCode(providerResult.ErrorCode, providerResult.Verified);
            return OperationOutcome.Failure(
                errorCode,
                result: Candidates(providerResult.Candidates),
                effectMayHaveOccurred: providerResult.Succeeded);
        }

        // cu-v3-documento-nuevo: a new document asked for is told done only when the opening saw it made.
        if (!HasConsistentSuccessEvidence(invocation, arguments, providerResult)
            || (arguments.NewDocument == true && !providerResult.NewDocument))
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        // v3 r22 uso real (t3-c18): a process this verified opening launched (not one already running) is noted with
        // its creation time and the window the opening verified; its window closes without asking while BAXY has
        // not written into any window (WindowsWindowControlProvider.HoldsNoDocument).
        if (!providerResult.AlreadyRunning
            && LaunchedByThisOpening(providerResult.Receipt.ProcessCreationTimeUtcTicks, openingStartedTicks))
        {
            _provenance.NoteLaunched(
                providerResult.ProcessId.GetValueOrDefault(),
                providerResult.Receipt.ProcessCreationTimeUtcTicks.GetValueOrDefault(),
                providerResult.WindowHandle.GetValueOrDefault());
        }

        // The application is open and verified; its place's address goes to the handler it registered. Whether its
        // window arrived is the mission's check on the window.
        PlaceOpening? place = placeAddress is null ? null
            : _places.Open(placeAddress, arguments.Foreground == true, providerResult.WindowHandle.GetValueOrDefault());
        if (place is { Opened: false })
        {
            return OperationOutcome.Failure("launch_failed", effectMayHaveOccurred: true);
        }

        var result = new OpenApplicationResult(
            arguments.AppId,
            providerResult.DisplayName,
            providerResult.AlreadyRunning,
            providerResult.ProcessId.GetValueOrDefault(),
            providerResult.WindowHandle.GetValueOrDefault(),
            providerResult.WindowsActivation,
            (providerResult.WindowsActivation && providerResult.FrontRestored) || place?.FrontRestored == true,
            providerResult.NewDocument,
            providerResult.ShownWithoutFocus,
            PlaceOpened: place is not null,
            FrontChanged: place?.FrontChanged == true);
        JsonElement serialized = JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.OpenApplicationResult);
        return OperationOutcome.Success(serialized);
    }

    // Auditoría D1: the installed names closest to one that matched none, said with the failure (nothing was opened).
    private static JsonElement? Candidates(IReadOnlyList<string>? names)
    {
        if (names is not { Count: > 0 })
            return null;
        var buffer = new System.Buffers.ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteStartArray("candidates");
            foreach (string name in names)
                writer.WriteStringValue(name);
            writer.WriteEndArray();
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    // A process creation time is stamped by the kernel's system clock, which advances in ticks of up to 15.6 ms and
    // so may read a little behind DateTime.UtcNow (precise); a process created after the mark may carry a stamp up to
    // one clock tick earlier. Anything older was already running before the opening began.
    private static readonly long CreationClockGranularityTicks = TimeSpan.FromMilliseconds(16).Ticks;

    internal static bool LaunchedByThisOpening(long? processCreationTimeUtcTicks, long openingStartedTicks) =>
        processCreationTimeUtcTicks is long created
        && created >= openingStartedTicks - CreationClockGranularityTicks;

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
            "new_document_not_created" => "new_document_not_created",
            _ => "application_open_failed",
        };
    }

}
