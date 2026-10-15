using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The Bluetooth list from Plug and Play, behind WindowsDeviceControlAdapter's WinRT list when that one runs out of time
/// (SlowWinRtBluetoothInventoryYieldsToTheBoundedFallback). Nothing else: its canned pair, print and scan failures and its
/// copy of the peripheral list replaced the real failures and ids of WindowsDeviceControlAdapter (BAXY Renew audit
/// 2026-10-15).
/// </summary>
internal sealed class WindowsInventoryAdapter : IExternalOperationAdapter
{
    private static readonly TimeSpan BluetoothInventoryTimeout = TimeSpan.FromSeconds(4);
    private const string BluetoothScript =
        "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
        + "Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3 -Compress";

    private readonly IExternalProcessRunner _runner;

    internal WindowsInventoryAdapter()
        : this(new ExternalProcessRunner())
    {
    }

    internal WindowsInventoryAdapter(IExternalProcessRunner runner) =>
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));

    public bool CanHandle(string operation) => operation is "bluetooth.device.list";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        try
        {
            return operation == "bluetooth.device.list"
                ? await BluetoothListAsync(operation, cancellationToken).ConfigureAwait(false)
                : ExternalJson.Failure(operation, "external_operation_not_supported");
        }
        catch (TimeoutException)
        {
            return ExternalJson.Failure(operation, "bluetooth_inventory_timeout");
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or JsonException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return ExternalJson.Failure(operation, "windows_inventory_adapter_failed");
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> BluetoothListAsync(
        string operation,
        CancellationToken cancellationToken)
    {
        ExternalProcessResult process = await _runner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-Command", BluetoothScript],
            BluetoothInventoryTimeout,
            cancellationToken).ConfigureAwait(false);
        if (process.ExitCode != 0)
        {
            return ExternalJson.Failure(operation, "bluetooth_inventory_failed");
        }

        using JsonDocument source = ParseArrayOrSingleton(process.Output);
        JsonElement[] devices = source.RootElement.ValueKind == JsonValueKind.Array
            ? source.RootElement.EnumerateArray().Select(item => item.Clone()).ToArray()
            : source.RootElement.ValueKind == JsonValueKind.Object
                ? [source.RootElement.Clone()]
                : [];
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("count", devices.Length);
            writer.WriteStartArray("devices");
            foreach (JsonElement device in devices)
            {
                string instance = StringProperty(device, "InstanceId");
                writer.WriteStartObject();
                writer.WriteString("deviceId", OpaqueId("bluetooth", instance));
                writer.WriteString("name", StringProperty(device, "FriendlyName"));
                writer.WriteString("status", StringProperty(device, "Status"));
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "windows_pnp_bluetooth_inventory");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static JsonDocument ParseArrayOrSingleton(string text) =>
        string.IsNullOrWhiteSpace(text) ? JsonDocument.Parse("[]") : JsonDocument.Parse(text);

    private static string StringProperty(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty : string.Empty;

    private static string OpaqueId(string prefix, string value) =>
        prefix + "_" + Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)))[..24];
}
