using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Windows;

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
            // Auditoría final (regla 3): the Start catalog is not every installed program, so a name
            // it does not list is said as that read, never as «not installed».
            if (observed.Installed) writer.WriteBoolean("installed", true);
            else writer.WriteBoolean("inStartCatalog", false);
            // Auditoría final: as app.open, a name that matches no installed application gets the closest names back.
            if (observed.Candidates is { Count: > 0 } candidates)
            {
                writer.WriteStartArray("candidates");
                foreach (string candidate in candidates)
                    writer.WriteStringValue(candidate);
                writer.WriteEndArray();
            }

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

internal sealed class ApplicationWindowStatusHandler(
    IApplicationInventoryProvider provider,
    LaunchProvenance? provenance = null)
    : IOperationHandler
{
    private readonly IApplicationInventoryProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));
    private readonly LaunchProvenance _provenance = provenance ?? LaunchProvenance.Shared;

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
            // Auditoría final (regla 3): a name outside the Start catalog has no windows looked at, so none are denied.
            if (observed.Installed)
            {
                writer.WriteBoolean("installed", true);
                writer.WriteBoolean("hasVisibleWindow", observed.HasVisibleWindow);
                writer.WriteNumber("visibleWindowCount", observed.VisibleWindowCount);
                // BAXY Renew al máximo, F002 («¿abriste Spotify?» sobre el Spotify que la persona ya tenía → «Sí»):
                // whether BAXY launched one of its windows in this run; left out when that cannot be told.
                if (OpenedByBaxy(observed.VisibleWindows) is bool opened)
                {
                    writer.WriteBoolean("openedByBaxy", opened);
                    // Renew al máximo (F002 en el notebook): with openedByBaxy false the answer was still «Sí, Spotify
                    // está abierto»; the provenance is said as a sentence too.
                    if (ModelAids.On(ModelAids.ProvenanceNext))
                    {
                        // Auditoría del Core (w8): «it was already open» said more than the provenance knows (the person
                        // may have opened it during the session); only BAXY's own launches are known.
                        string shown = observed.DisplayName ?? observed.RequestedName;
                        writer.WriteString("next", opened
                            ? $"BAXY opened {shown} in this session"
                            : $"{shown} is open, but BAXY did not open it in this session; who opened it, and when, is "
                                + "not known");
                    }
                }
            }
            else writer.WriteBoolean("inStartCatalog", false);
            writer.WriteString("authority", "windows_start_catalog_and_visible_window_snapshot");
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }

    // True when BAXY launched any of the windows, false when it launched none of them, null with no window or when one
    // of them cannot be told.
    private bool? OpenedByBaxy(
        IReadOnlyList<(long WindowHandle, int ProcessId, long ProcessCreationTimeUtcTicks)>? windows)
    {
        if (windows is not { Count: > 0 })
            return null;
        bool? opened = false;
        foreach ((long handle, int processId, long creation) in windows)
        {
            bool? launched = _provenance.Launched(handle, processId, creation);
            if (launched == true)
                return true;
            if (launched is null)
                opened = null;
        }

        return opened;
    }
}
