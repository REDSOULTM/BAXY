using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

internal sealed partial class WindowsInventoryAdapter : IExternalOperationAdapter
{
    private static readonly TimeSpan BluetoothInventoryTimeout = TimeSpan.FromSeconds(4);
    private static readonly TimeSpan PeripheralInventoryTimeout = TimeSpan.FromSeconds(60);
    private const string BluetoothScript =
        "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
        + "Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3 -Compress";
    private const string PeripheralScript = """
        $kind=[string]$args[0]
        if($kind -notin @('all','printer','scanner','usb','mouse','keyboard')){throw 'peripheral_kind_invalid'}
        $p=@();$s=@();$u=@();$m=@();$k=@()
        if($kind -in @('all','printer')){$p=@(Get-Printer -ErrorAction SilentlyContinue|Select-Object Name,PrinterStatus)}
        if($kind -in @('all','scanner')){try{$d=New-Object -ComObject WIA.DeviceManager;foreach($i in $d.DeviceInfos){if($i.Type -eq 1){$s+=@([pscustomobject]@{Name=[string]$i.Properties.Item('Name').Value;DeviceID=[string]$i.DeviceID;Status='available'})}}}catch{}}
        if($kind -in @('all','usb')){$u=@(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue|Where-Object {$_.InstanceId -like 'USB*'}|Select-Object FriendlyName,Status,InstanceId)}
        function Get-BaxyInputDevices([string]$className) {
          @(Get-PnpDevice -PresentOnly -Class $className -ErrorAction SilentlyContinue|ForEach-Object {
            $props=@(Get-PnpDeviceProperty -InstanceId $_.InstanceId -ErrorAction SilentlyContinue)
            $parentId=[string](($props|Where-Object KeyName -eq 'DEVPKEY_Device_Parent'|Select-Object -First 1).Data)
            $parentProps=if($parentId){@(Get-PnpDeviceProperty -InstanceId $parentId -ErrorAction SilentlyContinue)}else{@()}
            $busDescription=[string](($parentProps|Where-Object KeyName -eq 'DEVPKEY_Device_BusReportedDeviceDesc'|Select-Object -First 1).Data)
            $parentDescription=[string](($parentProps|Where-Object KeyName -eq 'DEVPKEY_Device_DeviceDesc'|Select-Object -First 1).Data)
            $parentModel='';if($parentId -match '^[^\\]+\\([^\\]+)\\'){$parentModel=[string]$Matches[1]}
            $name=[string]$_.FriendlyName
            if(-not [string]::IsNullOrWhiteSpace($busDescription)){$name=$busDescription}
            elseif(-not [string]::IsNullOrWhiteSpace($parentModel)){$name=$parentModel;if(-not [string]::IsNullOrWhiteSpace($parentDescription)){$name+=' ('+$parentDescription+')'}}
            [pscustomobject]@{FriendlyName=$name;Status=[string]$_.Status;InstanceId=[string]$_.InstanceId}
          })
        }
        if($kind -in @('all','mouse')){$m=@(Get-BaxyInputDevices 'Mouse')}
        if($kind -in @('all','keyboard')){$k=@(Get-BaxyInputDevices 'Keyboard')}
        [pscustomobject]@{printers=$p;scanners=$s;usb=$u;mice=$m;keyboards=$k}|ConvertTo-Json -Depth 5 -Compress
        """;

    private readonly IExternalProcessRunner _runner;

    internal WindowsInventoryAdapter()
        : this(new ExternalProcessRunner())
    {
    }

    internal WindowsInventoryAdapter(IExternalProcessRunner runner) =>
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));

    public bool CanHandle(string operation) => operation is
        "bluetooth.device.list" or "bluetooth.device.pair"
        or "peripheral.list" or "peripheral.print" or "peripheral.scan";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        try
        {
            return operation switch
            {
                "bluetooth.device.list" => await BluetoothListAsync(operation, cancellationToken)
                    .ConfigureAwait(false),
                "peripheral.list" => await PeripheralListAsync(operation, arguments, cancellationToken)
                    .ConfigureAwait(false),
                "bluetooth.device.pair" => ExternalJson.Failure(operation, "bluetooth_pairing_consent_ui_required"),
                "peripheral.print" => ExternalJson.Failure(operation, "print_job_physical_gate_required"),
                "peripheral.scan" => ExternalJson.Failure(operation, "scanner_physical_gate_required"),
                _ => ExternalJson.Failure(operation, "external_operation_not_supported"),
            };
        }
        catch (TimeoutException)
        {
            return ExternalJson.Failure(
                operation,
                operation switch
                {
                    "bluetooth.device.list" => "bluetooth_inventory_timeout",
                    _ => "windows_inventory_adapter_timeout",
                });
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
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> PeripheralListAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string requestedKind = arguments.TryGetProperty("kind", out JsonElement kindValue)
            && kindValue.ValueKind == JsonValueKind.String
                ? kindValue.GetString() ?? "all"
                : "all";
        if (requestedKind is not ("all" or "keyboard" or "mouse" or "printer" or "scanner" or "usb"))
        {
            return ExternalJson.Failure(operation, "peripheral_kind_invalid");
        }
        ExternalProcessResult process = await _runner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-Command", PeripheralScript, requestedKind],
            PeripheralInventoryTimeout,
            cancellationToken).ConfigureAwait(false);
        if (process.ExitCode != 0 || string.IsNullOrWhiteSpace(process.Output))
        {
            return ExternalJson.Failure(operation, "peripheral_inventory_failed");
        }

        using JsonDocument source = JsonDocument.Parse(process.Output);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteStartArray("devices");
            if (requestedKind is "all" or "printer")
                WritePeripheralArray(writer, source.RootElement, "printers", "printer", "Name", "Name", "PrinterStatus");
            if (requestedKind is "all" or "scanner")
                WritePeripheralArray(writer, source.RootElement, "scanners", "scanner", "Name", "DeviceID", "Status");
            if (requestedKind is "all" or "usb")
                WritePeripheralArray(writer, source.RootElement, "usb", "usb", "FriendlyName", "InstanceId", "Status");
            if (requestedKind is "all" or "mouse")
                WritePeripheralArray(writer, source.RootElement, "mice", "mouse", "FriendlyName", "InstanceId", "Status");
            if (requestedKind is "all" or "keyboard")
                WritePeripheralArray(writer, source.RootElement, "keyboards", "keyboard", "FriendlyName", "InstanceId", "Status");
            writer.WriteEndArray();
            writer.WriteString("requestedKind", requestedKind);
            writer.WriteString("authority", "windows_print_wia_usb_hid_inventory");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static JsonDocument ParseArrayOrSingleton(string text) =>
        string.IsNullOrWhiteSpace(text) ? JsonDocument.Parse("[]") : JsonDocument.Parse(text);

    private static void WritePeripheralArray(
        Utf8JsonWriter writer,
        JsonElement root,
        string property,
        string kind,
        string nameProperty,
        string identityProperty,
        string statusProperty)
    {
        if (!root.TryGetProperty(property, out JsonElement values))
        {
            return;
        }
        IEnumerable<JsonElement> items = values.ValueKind == JsonValueKind.Array
            ? values.EnumerateArray().Select(item => item.Clone())
            : values.ValueKind == JsonValueKind.Object ? [values] : [];
        foreach (JsonElement item in items)
        {
            string name = StringProperty(item, nameProperty);
            string identity = StringProperty(item, identityProperty);
            string status = StringProperty(item, statusProperty);
            writer.WriteStartObject();
            writer.WriteString("deviceId", OpaqueId(kind, identity));
            writer.WriteString("kind", kind);
            writer.WriteString("name", name);
            writer.WriteString("status", status);
            writer.WriteEndObject();
        }
    }

    private static string StringProperty(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty : string.Empty;

    private static string OpaqueId(string prefix, string value) =>
        prefix + "_" + Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)))[..24];
}
