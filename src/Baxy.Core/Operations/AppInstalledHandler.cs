using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Core.Operations;

internal sealed class AppInstalledHandler(IApplicationInventoryProvider provider) : IOperationHandler
{
    private readonly IApplicationInventoryProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("app.installed");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        string name = invocation.Arguments.GetProperty("name").GetString()!;
        ApplicationInstalledResult observed = await _provider.IsInstalledAsync(
            name, cancellationToken).ConfigureAwait(false);
        if (!observed.Verified || observed.ErrorCode is not null)
        {
            return OperationOutcome.Failure(observed.ErrorCode ?? "app_inventory_not_verified");
        }

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requestedName", observed.RequestedName);
            if (observed.DisplayName is null) writer.WriteNull("displayName");
            else writer.WriteString("displayName", observed.DisplayName);
            if (observed.InstalledVersion is null) writer.WriteNull("installedVersion");
            else writer.WriteString("installedVersion", observed.InstalledVersion);
            writer.WriteBoolean("installed", observed.Installed);
            writer.WriteString(
                "authority",
                observed.InstalledVersion is null
                    ? "windows_start_catalog_snapshot"
                    : "windows_start_catalog_and_uninstall_registry_snapshot");
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}

internal sealed class ApplicationWindowStatusHandler(IApplicationInventoryProvider provider)
    : IOperationHandler
{
    private readonly IApplicationInventoryProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("window.application.status");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        string name = invocation.Arguments.GetProperty("name").GetString()!;
        ApplicationWindowStatusResult observed = await _provider.GetWindowStatusAsync(
            name, cancellationToken).ConfigureAwait(false);
        if (!observed.Verified || observed.ErrorCode is not null)
        {
            return OperationOutcome.Failure(observed.ErrorCode ?? "app_window_status_not_verified");
        }

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requestedName", observed.RequestedName);
            if (observed.DisplayName is null) writer.WriteNull("displayName");
            else writer.WriteString("displayName", observed.DisplayName);
            writer.WriteBoolean("installed", observed.Installed);
            writer.WriteBoolean("hasVisibleWindow", observed.HasVisibleWindow);
            writer.WriteNumber("visibleWindowCount", observed.VisibleWindowCount);
            writer.WriteString("authority", "windows_start_catalog_and_visible_window_snapshot");
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}
