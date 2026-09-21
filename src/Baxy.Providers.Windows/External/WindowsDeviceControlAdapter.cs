using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Windows.Devices.Bluetooth;
using Windows.Devices.Enumeration;
using Windows.Devices.Radios;

namespace Baxy.Providers.Windows.External;

internal sealed partial class WindowsDeviceControlAdapter : IExternalOperationAdapter
{
    private static readonly TimeSpan DefaultBluetoothInventoryTimeout =
        TimeSpan.FromSeconds(4);
    private const string PeripheralListScript = """
        $kind=[string]$args[0]
        if($kind -notin @('all','printer','scanner','usb','mouse','keyboard')){throw 'peripheral_kind_invalid'}
        $p=@();$s=@();$u=@();$m=@();$k=@()
        if($kind -in @('all','printer')){$p=@(Get-Printer -ErrorAction SilentlyContinue|Select-Object Name,PrinterStatus)}
        if($kind -in @('all','scanner')){try{$d=New-Object -ComObject WIA.DeviceManager;foreach($i in $d.DeviceInfos){if($i.Type -eq 1){$s+=@([pscustomobject]@{Name=[string]$i.Properties.Item('Name').Value;DeviceID=[string]$i.DeviceID;Status='available'})}}}catch{}}
        if($kind -in @('all','usb')){$u=@(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue|Where-Object {$_.InstanceId -like 'USB*'}|Select-Object FriendlyName,Status,InstanceId)}
        function Get-BaxyInputDevices([string]$className) {
          @(
            Get-PnpDevice -PresentOnly -Class $className -ErrorAction SilentlyContinue|ForEach-Object {
              $props=@(Get-PnpDeviceProperty -InstanceId $_.InstanceId -ErrorAction SilentlyContinue)
              $parentId=[string](($props|Where-Object KeyName -eq 'DEVPKEY_Device_Parent'|Select-Object -First 1).Data)
              $parentProps=if($parentId){@(Get-PnpDeviceProperty -InstanceId $parentId -ErrorAction SilentlyContinue)}else{@()}
              $busDescription=[string](($parentProps|Where-Object KeyName -eq 'DEVPKEY_Device_BusReportedDeviceDesc'|Select-Object -First 1).Data)
              $parentDescription=[string](($parentProps|Where-Object KeyName -eq 'DEVPKEY_Device_DeviceDesc'|Select-Object -First 1).Data)
              $parentModel='';if($parentId -match '^[^\\]+\\([^\\]+)\\'){$parentModel=[string]$Matches[1]}
              $name=[string]$_.FriendlyName
              if(-not [string]::IsNullOrWhiteSpace($busDescription)){$name=$busDescription}
              elseif(-not [string]::IsNullOrWhiteSpace($parentModel)){
                $name=$parentModel
                if(-not [string]::IsNullOrWhiteSpace($parentDescription)){$name+=' ('+$parentDescription+')'}
              }
              [pscustomobject]@{FriendlyName=$name;Status=[string]$_.Status;InstanceId=[string]$_.InstanceId}
            }
          )
        }
        if($kind -in @('all','mouse')){$m=@(Get-BaxyInputDevices 'Mouse')}
        if($kind -in @('all','keyboard')){$k=@(Get-BaxyInputDevices 'Keyboard')}
        [pscustomobject]@{printers=$p;scanners=$s;usb=$u;mice=$m;keyboards=$k}|ConvertTo-Json -Depth 5 -Compress
        """;
    private const string ConnectedInputListScript = """
        $ErrorActionPreference='Stop'
        $class=[string]$args[0]
        if($class -notin @('Mouse','Keyboard')){throw 'input_class_invalid'}
        $text=(& pnputil.exe /enum-devices /class $class /connected /relations|Out-String)
        $devices=@()
        foreach($block in @($text -split '(?:\r?\n){2,}')){
          $ids=@()
          foreach($line in @($block -split '\r?\n')){
            if($line -match '^\s*[^:]+:\s*(\S.*)$'){
              $candidate=[string]$Matches[1].Trim()
              if($candidate -match '^[^\\\s]+\\[^\\]+\\.+$'){$ids+=@($candidate)}
            }
          }
          if($ids.Count -eq 0){continue}
          $instance=[string]$ids[0]
          $parent=if($ids.Count -gt 1){[string]$ids[$ids.Count-1]}else{$instance}
          $registry='Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\'+$parent
          $properties=Get-ItemProperty -LiteralPath $registry -ErrorAction SilentlyContinue
          $description=[string]$properties.DeviceDesc
          if($description.Contains(';')){$description=[string]($description -split ';')[-1]}
          $segments=@($parent -split '\\')
          $model=if($segments.Count -gt 1){[string]$segments[1]}else{''}
          $name=if($description){$description}elseif($model){$model}else{$class}
          if($segments.Count -gt 0 -and $segments[0] -eq 'ACPI' -and $model -and $description){
            $name=$model+' ('+$description+')'
          }
          $devices+=@([pscustomobject]@{FriendlyName=$name;Status='present';InstanceId=$instance})
        }
        $mice=@();$keyboards=@()
        if($class -eq 'Mouse'){$mice=$devices}else{$keyboards=$devices}
        [pscustomobject]@{printers=@();scanners=@();usb=@();mice=$mice;keyboards=$keyboards}|ConvertTo-Json -Depth 5 -Compress
        """;
    private const string PrintScript = """
        $ErrorActionPreference='Stop';$i=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))|ConvertFrom-Json
        $before=@(Get-PrintJob -PrinterName ([string]$i.printer) -ErrorAction SilentlyContinue|ForEach-Object {$_.ID})
        $effect=$false
        try {
          $p=Start-Process -FilePath ([string]$i.path) -Verb PrintTo -ArgumentList ('"'+[string]$i.printer+'"') -PassThru;$effect=$true
          $deadline=(Get-Date).AddSeconds(30)
          do {Start-Sleep -Milliseconds 500;$job=Get-PrintJob -PrinterName ([string]$i.printer) -ErrorAction SilentlyContinue|Where-Object {$before -notcontains $_.ID}|Select-Object -First 1} while($null -eq $job -and (Get-Date) -lt $deadline)
          [pscustomobject]@{ok=($null -ne $job);effectObserved=$effect;jobId=if($job){[string]$job.ID}else{''};status=if($job){[string]$job.JobStatus}else{''}}|ConvertTo-Json -Compress
        } catch {[pscustomobject]@{ok=$false;effectObserved=$effect;error='print_failed'}|ConvertTo-Json -Compress;exit 2}
        """;
    private const string ScanScript = """
        $ErrorActionPreference='Stop';$i=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))|ConvertFrom-Json;$effect=$false
        try {
          $manager=New-Object -ComObject WIA.DeviceManager;$info=$null
          foreach($candidate in $manager.DeviceInfos){if([string]$candidate.DeviceID -ceq [string]$i.deviceId){$info=$candidate;break}}
          if($null -eq $info){throw 'scanner_not_found'}
          $device=$info.Connect();$item=$device.Items.Item(1);$effect=$true
          $image=$item.Transfer('{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}');$image.SaveFile([string]$i.path)
          $file=Get-Item -LiteralPath ([string]$i.path)
          [pscustomobject]@{ok=($file.Length -gt 0);effectObserved=$true;length=$file.Length}|ConvertTo-Json -Compress
        } catch {[pscustomobject]@{ok=$false;effectObserved=$effect;error='scan_failed'}|ConvertTo-Json -Compress;exit 2}
        """;
    private const string WifiProfilesScript = """
        $text=netsh wlan show profiles
        $profiles=@();foreach($line in $text){if($line -match '^\s*(?:All User Profile|Perfil de todos los usuarios)\s*:\s*(.+?)\s*$'){$profiles+=@($Matches[1])}}
        [pscustomobject]@{profiles=$profiles}|ConvertTo-Json -Compress
        """;
    private const string WifiStatusScript = """
        $text=netsh wlan show interfaces
        $connected=$false;$profile=''
        foreach($line in $text){if($line -match '^\s*(?:State|Estado)\s*:\s*(connected|conectado)\s*$'){$connected=$true};if($line -match '^\s*(?:Profile|Perfil)\s*:\s*(.+?)\s*$'){$profile=$Matches[1]}}
        [pscustomobject]@{connected=$connected;profile=$profile}|ConvertTo-Json -Compress
        """;
    private const string BrightnessScript = """
        $ErrorActionPreference='Stop';$value=[byte]$args[0];$effect=$false
        try {$methods=Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods;$current=Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness
          if($null -eq $methods -or $null -eq $current){throw 'brightness_not_supported'}
          foreach($method in $methods){Invoke-CimMethod -InputObject $method -MethodName WmiSetBrightness -Arguments @{Timeout=1;Brightness=$value}|Out-Null};$effect=$true;Start-Sleep -Milliseconds 300
          $after=@(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness|ForEach-Object {[int]$_.CurrentBrightness})
          [pscustomobject]@{ok=($after.Count -gt 0 -and @($after|Where-Object {$_ -ne $value}).Count -eq 0);effectObserved=$true;values=$after}|ConvertTo-Json -Compress
        } catch {[pscustomobject]@{ok=$false;effectObserved=$effect;error='brightness_failed'}|ConvertTo-Json -Compress;exit 2}
        """;
    private const string BrightnessAdjustScript = """
        $ErrorActionPreference='Stop';$delta=[int]$args[0];$effect=$false
        try {
          $methods=@(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods)
          $current=@(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness)
          if($methods.Count -eq 0 -or $current.Count -eq 0){throw 'brightness_not_supported'}
          $expected=@{};$baseline=@()
          foreach($item in $current){
            $before=[int]$item.CurrentBrightness;$target=[Math]::Max(0,[Math]::Min(100,$before+$delta))
            $baseline+=@($before);$expected[[string]$item.InstanceName]=$target
            $method=$methods|Where-Object {[string]$_.InstanceName -ceq [string]$item.InstanceName}|Select-Object -First 1
            if($null -eq $method){throw 'brightness_method_not_found'}
            Invoke-CimMethod -InputObject $method -MethodName WmiSetBrightness -Arguments @{Timeout=1;Brightness=[byte]$target}|Out-Null
          }
          $effect=$true;Start-Sleep -Milliseconds 300
          $after=@(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness)
          $values=@();$ok=$after.Count -eq $current.Count
          foreach($item in $after){$value=[int]$item.CurrentBrightness;$values+=@($value);if(-not $expected.ContainsKey([string]$item.InstanceName) -or $expected[[string]$item.InstanceName] -ne $value){$ok=$false}}
          [pscustomobject]@{ok=$ok;effectObserved=$effect;baselineValues=$baseline;values=$values}|ConvertTo-Json -Compress
        } catch {[pscustomobject]@{ok=$false;effectObserved=$effect;error='brightness_adjust_failed'}|ConvertTo-Json -Compress;exit 2}
        """;
    private const string BrightnessStatusScript = """
        $ErrorActionPreference='Stop'
        try {
          function Read-BaxyBrightness {
            @(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop |
              ForEach-Object {[pscustomobject]@{instanceName=[string]$_.InstanceName;value=[int]$_.CurrentBrightness}} |
              Sort-Object instanceName)
          }
          $first=@(Read-BaxyBrightness)
          Start-Sleep -Milliseconds 120
          $second=@(Read-BaxyBrightness)
          $coherent=$first.Count -gt 0 -and $first.Count -eq $second.Count
          if($coherent){
            for($i=0;$i -lt $first.Count;$i++){
              if($first[$i].instanceName -cne $second[$i].instanceName -or $first[$i].value -ne $second[$i].value){$coherent=$false;break}
            }
          }
          [pscustomobject]@{ok=$coherent;monitors=$second}|ConvertTo-Json -Depth 4 -Compress
        } catch {[pscustomobject]@{ok=$false;error='brightness_status_failed'}|ConvertTo-Json -Compress;exit 2}
        """;
    private const string DoNotDisturbScript = """
        $ErrorActionPreference='Stop';$desired=[int]$args[0];$effect=$false
        try {
          Start-Process 'ms-settings:notifications'
          Add-Type -AssemblyName UIAutomationClient
          $root=[System.Windows.Automation.AutomationElement]::RootElement
          $condition=New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
            'SystemSettings_Notifications_QuietHours_MuteNotification_Enabled_ToggleSwitch')
          $launchProbe=[Diagnostics.Stopwatch]::StartNew()
          $toggle=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)
          if($null -eq $toggle){
            $remaining=[Math]::Max(0,900-[int]$launchProbe.ElapsedMilliseconds)
            if($remaining -gt 0){Start-Sleep -Milliseconds $remaining}
            for($attempt=0;$attempt -lt 20 -and $null -eq $toggle;$attempt++){
              $toggle=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)
              if($null -eq $toggle){Start-Sleep -Milliseconds 250}
            }
          }
          if($null -eq $toggle){throw 'do_not_disturb_toggle_not_found'}
          $pattern=$toggle.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
          $before=[int]$pattern.Current.ToggleState
          $after=$before
          if($before -ne $desired){
            $pattern.Toggle();$effect=$true
            $toggleProbe=[Diagnostics.Stopwatch]::StartNew()
            $after=[int]$pattern.Current.ToggleState
            if($after -ne $desired){
              $remaining=[Math]::Max(0,400-[int]$toggleProbe.ElapsedMilliseconds)
              if($remaining -gt 0){Start-Sleep -Milliseconds $remaining}
              $after=[int]$pattern.Current.ToggleState
            }
          }
          [pscustomobject]@{ok=($after -eq $desired);effectObserved=$effect;before=$before;value=$after}|ConvertTo-Json -Compress
        } catch {[pscustomobject]@{ok=$false;effectObserved=$effect;error='do_not_disturb_failed'}|ConvertTo-Json -Compress;exit 2}
        """;

    private readonly string _scanRoot;
    private readonly string _documentsRoot;
    private readonly IExternalProcessRunner _runner;
    private readonly IBluetoothDeviceInventory _bluetoothInventory;
    private readonly TimeSpan _bluetoothInventoryTimeout;
    private readonly Func<TimeSpan, CancellationToken, ValueTask> _delay;
    private readonly ConcurrentDictionary<string, string> _bluetooth = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, PeripheralIdentity> _peripherals = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, string> _wifi = new(StringComparer.Ordinal);

    internal WindowsDeviceControlAdapter(string dataRoot, string documentsRoot)
        : this(Path.Combine(dataRoot, "scans"), documentsRoot, new ExternalProcessRunner())
    {
    }

    internal WindowsDeviceControlAdapter(
        string scanRoot,
        string documentsRoot,
        IExternalProcessRunner runner,
        Func<TimeSpan, CancellationToken, ValueTask>? delay = null)
        : this(
            scanRoot,
            documentsRoot,
            runner,
            new WindowsBluetoothDeviceInventory(),
            DefaultBluetoothInventoryTimeout,
            delay)
    {
    }

    internal WindowsDeviceControlAdapter(
        string scanRoot,
        string documentsRoot,
        IExternalProcessRunner runner,
        IBluetoothDeviceInventory bluetoothInventory)
        : this(
            scanRoot,
            documentsRoot,
            runner,
            bluetoothInventory,
            DefaultBluetoothInventoryTimeout,
            delay: null)
    {
    }

    internal WindowsDeviceControlAdapter(
        string scanRoot,
        string documentsRoot,
        IExternalProcessRunner runner,
        IBluetoothDeviceInventory bluetoothInventory,
        TimeSpan bluetoothInventoryTimeout,
        Func<TimeSpan, CancellationToken, ValueTask>? delay = null)
    {
        if (bluetoothInventoryTimeout <= TimeSpan.Zero
            || bluetoothInventoryTimeout > TimeSpan.FromSeconds(30))
        {
            throw new ArgumentOutOfRangeException(nameof(bluetoothInventoryTimeout));
        }

        _scanRoot = Path.GetFullPath(scanRoot);
        _documentsRoot = Path.GetFullPath(documentsRoot);
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _bluetoothInventory = bluetoothInventory
            ?? throw new ArgumentNullException(nameof(bluetoothInventory));
        _bluetoothInventoryTimeout = bluetoothInventoryTimeout;
        _delay = delay ?? DelayAsync;
    }

    public bool CanHandle(string operation) => operation is
        "bluetooth.device.list" or "bluetooth.device.pair"
        or "bluetooth.radio.set" or "bluetooth.radio.status"
        or "display.status" or "software.python.status" or "software.python.package.status" or "storage.removable.list" or "client.channel.locate" or "calculator.expression.evaluate"
        or "peripheral.list" or "peripheral.print" or "peripheral.scan"
        or "wifi.profile.list" or "wifi.radio.set" or "wifi.radio.status" or "wifi.scan" or "wifi.connect" or "wifi.connect.named" or "wifi.disconnect"
        or "wifi.ensure.connected" or "wifi.status"
        or "system.settings.adjust" or "system.settings.status" or "system.settings.set";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return operation switch
            {
                "bluetooth.device.list" => await BluetoothListAsync(operation, cancellationToken),
                "bluetooth.device.pair" => await BluetoothPairAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                "bluetooth.radio.set" => await BluetoothRadioSetAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                "bluetooth.radio.status" => await BluetoothRadioStatusAsync(operation),
                "display.status" => DisplayStatus(operation),
                "software.python.status" => PythonStatus(operation),
                "storage.removable.list" => RemovableStorageList(operation),
                "client.channel.locate" => await ClientChannelLocateAsync(operation, arguments, cancellationToken),
                "software.python.package.status" => await PythonPackageStatusAsync(operation, arguments, cancellationToken),
                "calculator.expression.evaluate" => await CalculatorEvaluateAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                "peripheral.list" => await PeripheralListAsync(operation, arguments, cancellationToken),
                "peripheral.print" => await PrintAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                "peripheral.scan" => await ScanAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                "wifi.profile.list" => await WifiProfilesAsync(operation, cancellationToken),
                "wifi.connect" => await WifiConnectAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                "wifi.connect.named" => await WifiConnectNamedAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                "wifi.disconnect" => await WifiDisconnectAsync(
                    operation, effectBoundary, cancellationToken),
                "wifi.ensure.connected" => await WifiEnsureConnectedAsync(operation, cancellationToken),
                "wifi.status" => await WifiConnectionStatusAsync(operation, cancellationToken),
                "wifi.scan" => await WifiScanAsync(operation, cancellationToken),
                "wifi.radio.set" => await WifiRadioSetAsync(operation, arguments, effectBoundary, cancellationToken),
                "wifi.radio.status" => await WifiRadioStatusAsync(operation),
                "system.settings.adjust" => await SettingAdjustAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                "system.settings.status" => await SettingStatusAsync(operation, arguments, cancellationToken),
                "system.settings.set" => await SettingAsync(
                    operation, arguments, effectBoundary, cancellationToken),
                _ => ExternalJson.Failure(operation, "external_operation_not_supported"),
            };
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "windows_device_adapter_failed");
        }
        catch (TimeoutException) when (operation == "bluetooth.device.list")
        {
            return ExternalJson.Failure(operation, "bluetooth_winrt_inventory_timeout");
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or InvalidDataException or JsonException
            or TimeoutException)
        {
            return effectBoundary.Failure(operation, "windows_device_adapter_failed");
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> BluetoothListAsync(
        string operation,
        CancellationToken cancellationToken)
    {
        using var inventoryCancellation =
            CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        Task<IReadOnlyList<BluetoothDeviceSnapshot>> inventory = _bluetoothInventory
            .ListAsync(inventoryCancellation.Token)
            .AsTask();
        IReadOnlyList<BluetoothDeviceSnapshot> devices;
        try
        {
            devices = await inventory
                .WaitAsync(_bluetoothInventoryTimeout, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            inventoryCancellation.Cancel();
            throw;
        }
        cancellationToken.ThrowIfCancellationRequested();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteNumber("count", devices.Count);
            writer.WriteStartArray("devices");
            foreach (BluetoothDeviceSnapshot item in devices.OrderBy(
                item => item.Name, StringComparer.CurrentCultureIgnoreCase))
            {
                string id = Opaque("bluetooth", item.NativeId);
                _bluetooth[id] = item.NativeId;
                writer.WriteStartObject(); writer.WriteString("deviceId", id); writer.WriteString("name", item.Name);
                writer.WriteBoolean("paired", item.IsPaired); writer.WriteBoolean("canPair", item.CanPair);
                writer.WriteEndObject();
            }
            writer.WriteEndArray(); writer.WriteString("authority", "windows_device_enumeration"); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> BluetoothPairAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string id = ExternalJson.RequiredString(arguments, "deviceId");
        if (!_bluetooth.TryGetValue(id, out string? nativeId))
            return ExternalJson.Failure(operation, "bluetooth_identity_expired");
        DeviceInformation item = await DeviceInformation.CreateFromIdAsync(nativeId);
        if (item.Pairing.IsPaired)
            return ExternalJson.Success(operation, BluetoothPairResult(id, item.Name), false);
        if (!item.Pairing.CanPair) return ExternalJson.Failure(operation, "bluetooth_device_cannot_pair");
        effectBoundary.Cross(cancellationToken);
        DevicePairingResult paired = await item.Pairing.PairAsync(DevicePairingProtectionLevel.Default);
        cancellationToken.ThrowIfCancellationRequested();
        DeviceInformation after = await DeviceInformation.CreateFromIdAsync(nativeId);
        if (paired.Status is not (DevicePairingResultStatus.Paired or DevicePairingResultStatus.AlreadyPaired)
            || !after.Pairing.IsPaired)
            return effectBoundary.Failure(operation, "bluetooth_pairing_not_verified", true);
        return ExternalJson.Success(operation, BluetoothPairResult(id, after.Name), true);
    }

    private static JsonElement BluetoothPairResult(string id, string name) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteString("deviceId", id);
        writer.WriteString("name", name); writer.WriteBoolean("paired", true);
        writer.WriteString("authority", "windows_device_pairing_postread"); writer.WriteEndObject();
    });

    // NETWORK1737 «qué redes wifi hay» → «sí, prendelo»: the Wi-Fi radio is
    // switched through the same official Radio API as Bluetooth, with the
    // person's confirmation, and the state is read back; a read-only status
    // answers «¿el wifi está prendido?» without touching it.
    private static async ValueTask<ExternalCapabilityReceipt> WifiRadioSetAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (!arguments.TryGetProperty("state", out JsonElement stateElement)
            || stateElement.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return ExternalJson.Failure(operation, "wifi_radio_state_invalid");
        }
        bool requested = stateElement.GetBoolean();
        RadioAccessStatus access = await Radio.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
        {
            return ExternalJson.Failure(operation, "wifi_radio_access_denied");
        }
        Radio[] radios = (await Radio.GetRadiosAsync())
            .Where(radio => radio.Kind == RadioKind.WiFi)
            .ToArray();
        if (radios.Length == 0)
        {
            return ExternalJson.Failure(operation, "wifi_radio_not_found");
        }
        RadioState desired = requested ? RadioState.On : RadioState.Off;
        bool effectObserved = false;
        foreach (Radio radio in radios)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (radio.State == desired)
            {
                continue;
            }
            effectBoundary.Cross(cancellationToken);
            RadioAccessStatus changed = await radio.SetStateAsync(desired);
            effectObserved = true;
            if (changed != RadioAccessStatus.Allowed)
            {
                return effectBoundary.Failure(operation, "wifi_radio_change_rejected", effectObserved);
            }
        }
        Radio[] observed = (await Radio.GetRadiosAsync())
            .Where(radio => radio.Kind == RadioKind.WiFi)
            .ToArray();
        if (observed.Length == 0 || observed.Any(radio => radio.State != desired))
        {
            return effectBoundary.Failure(operation, "wifi_radio_postread_failed", effectObserved);
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("state", requested);
            writer.WriteBoolean("changed", effectObserved);
            writer.WriteNumber("radioCount", observed.Length);
            writer.WriteString("authority", "windows_radio_api_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved);
    }

    // REOPEN1957 H0107 «poneme el modo avión»: el modo avión de Windows es todas
    // las radios apagadas. La API de radios apaga y enciende cada una y la
    // postlectura las vuelve a leer; la lectura de estado dice si están todas
    // apagadas. Un driver que restaure enciende las que estaban encendidas.
    private static readonly RadioKind[] AirplaneRadioKinds = [RadioKind.WiFi, RadioKind.Bluetooth, RadioKind.MobileBroadband];

    private static async ValueTask<ExternalCapabilityReceipt> AirplaneModeSetAsync(
        string operation,
        int value,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (value is not (0 or 1))
            return ExternalJson.FailureBeforeEffect(operation, "airplane_mode_value_invalid");
        RadioAccessStatus access = await Radio.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
            return ExternalJson.FailureBeforeEffect(operation, "airplane_mode_radio_access_denied");
        Radio[] radios = (await Radio.GetRadiosAsync())
            .Where(radio => AirplaneRadioKinds.Contains(radio.Kind))
            .ToArray();
        if (radios.Length == 0)
            return ExternalJson.FailureBeforeEffect(operation, "airplane_mode_radios_not_found");
        RadioState desired = value == 1 ? RadioState.Off : RadioState.On;
        var before = radios.ToDictionary(radio => radio.Name + "|" + radio.Kind, radio => radio.State == RadioState.On);
        bool effectObserved = false;
        foreach (Radio radio in radios)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (radio.State == desired || (desired == RadioState.On && radio.State == RadioState.Disabled))
                continue;
            effectBoundary.Cross(cancellationToken);
            RadioAccessStatus changed = await radio.SetStateAsync(desired);
            effectObserved = true;
            if (changed != RadioAccessStatus.Allowed)
                return effectBoundary.Failure(operation, "airplane_mode_change_rejected", effectObserved);
        }

        Radio[] observed = (await Radio.GetRadiosAsync())
            .Where(radio => AirplaneRadioKinds.Contains(radio.Kind))
            .ToArray();
        bool allOff = observed.All(radio => radio.State != RadioState.On);
        bool reached = value == 1 ? allOff : observed.All(radio => radio.State is RadioState.On or RadioState.Disabled);
        if (!reached)
            return effectBoundary.Failure(operation, "airplane_mode_postread_failed", effectObserved);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", "airplane_mode");
            writer.WriteNumber("value", value);
            writer.WriteBoolean("airplaneMode", allOff);
            writer.WriteBoolean("changed", effectObserved);
            writer.WriteStartArray("radios");
            foreach (Radio radio in observed)
            {
                writer.WriteStartObject();
                writer.WriteString("kind", radio.Kind.ToString());
                writer.WriteString("name", radio.Name);
                writer.WriteString("state", radio.State.ToString());
                writer.WriteBoolean("wasOn", before.GetValueOrDefault(radio.Name + "|" + radio.Kind));
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            writer.WriteString("authority", "windows_radio_api_all_radios_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved);
    }

    private static async ValueTask<ExternalCapabilityReceipt> AirplaneModeStatusAsync(string operation)
    {
        RadioAccessStatus access = await Radio.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
            return ExternalJson.Failure(operation, "airplane_mode_radio_access_denied");
        Radio[] radios = (await Radio.GetRadiosAsync())
            .Where(radio => AirplaneRadioKinds.Contains(radio.Kind))
            .ToArray();
        if (radios.Length == 0)
            return ExternalJson.Failure(operation, "airplane_mode_radios_not_found");
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", "airplane_mode");
            writer.WriteBoolean("airplaneMode", radios.All(radio => radio.State != RadioState.On));
            writer.WriteNumber("radioCount", radios.Length);
            writer.WriteStartArray("radios");
            foreach (Radio radio in radios)
            {
                writer.WriteStartObject();
                writer.WriteString("kind", radio.Kind.ToString());
                writer.WriteString("name", radio.Name);
                writer.WriteString("state", radio.State.ToString());
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            writer.WriteString("authority", "windows_radio_api_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static async ValueTask<ExternalCapabilityReceipt> WifiRadioStatusAsync(string operation)
    {
        RadioAccessStatus access = await Radio.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
        {
            return ExternalJson.Failure(operation, "wifi_radio_access_denied");
        }
        Radio[] radios = (await Radio.GetRadiosAsync())
            .Where(radio => radio.Kind == RadioKind.WiFi)
            .ToArray();
        if (radios.Length == 0)
        {
            return ExternalJson.Failure(operation, "wifi_radio_not_found");
        }
        bool on = radios.Any(radio => radio.State == RadioState.On);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("radioOn", on);
            writer.WriteNumber("radioCount", radios.Length);
            writer.WriteString("authority", "windows_radio_api_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static async ValueTask<ExternalCapabilityReceipt> BluetoothRadioSetAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (!arguments.TryGetProperty("state", out JsonElement stateElement)
            || stateElement.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return ExternalJson.Failure(operation, "bluetooth_radio_state_invalid");
        }
        bool requested = stateElement.GetBoolean();
        RadioAccessStatus access = await Radio.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
        {
            return ExternalJson.Failure(operation, "bluetooth_radio_access_denied");
        }
        Radio[] radios = (await Radio.GetRadiosAsync())
            .Where(radio => radio.Kind == RadioKind.Bluetooth)
            .ToArray();
        if (radios.Length == 0)
        {
            return ExternalJson.Failure(operation, "bluetooth_radio_not_found");
        }
        RadioState desired = requested ? RadioState.On : RadioState.Off;
        bool effectObserved = false;
        foreach (Radio radio in radios)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (radio.State == desired)
            {
                continue;
            }
            effectBoundary.Cross(cancellationToken);
            RadioAccessStatus changed = await radio.SetStateAsync(desired);
            effectObserved = true;
            if (changed != RadioAccessStatus.Allowed)
            {
                return effectBoundary.Failure(
                    operation,
                    "bluetooth_radio_change_rejected",
                    effectObserved);
            }
        }
        Radio[] observed = (await Radio.GetRadiosAsync())
            .Where(radio => radio.Kind == RadioKind.Bluetooth)
            .ToArray();
        if (observed.Length == 0 || observed.Any(radio => radio.State != desired))
        {
            return effectBoundary.Failure(
                operation,
                "bluetooth_radio_postread_failed",
                effectObserved);
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("state", requested);
            writer.WriteBoolean("changed", effectObserved);
            writer.WriteNumber("radioCount", observed.Length);
            writer.WriteString("authority", "windows_radio_api_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved);
    }

    // NETWORK1457 «tengo el bluetooth encendido», «y el bluetooth?»: the radio
    // state was only observable as the post-read of a change; a read-only
    // read answers the question without touching the radio.
    private static async ValueTask<ExternalCapabilityReceipt> BluetoothRadioStatusAsync(string operation)
    {
        RadioAccessStatus access = await Radio.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
        {
            return ExternalJson.Failure(operation, "bluetooth_radio_access_denied");
        }
        Radio[] radios = (await Radio.GetRadiosAsync())
            .Where(radio => radio.Kind == RadioKind.Bluetooth)
            .ToArray();
        if (radios.Length == 0)
        {
            return ExternalJson.Failure(operation, "bluetooth_radio_not_found");
        }
        bool on = radios.Any(radio => radio.State == RadioState.On);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("radioOn", on);
            writer.WriteNumber("radioCount", radios.Length);
            writer.WriteNumber("radiosOn", radios.Count(radio => radio.State == RadioState.On));
            writer.WriteString("authority", "windows_radio_api_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // SYSTEM1459 «qué resolución tengo», «cuántos monitores tengo», «qué Hz tiene el
    // monitor»: the desktop's attached display devices and their current mode,
    // read through the Win32 display API without changing anything.
    // SYSTEM1697 H0307 «dime la versión de Python instalada»: the installs a
    // Python distributor registered under Software\Python (PEP 514), read from
    // the registry only — no interpreter is started, nothing is executed.
    // UI1725 «multiplicá 6 por 7 en la calc»: the expression is typed into the
    // Windows Calculator that is already open — brought to the foreground and
    // verified there, otherwise nothing is typed — and the display is read
    // back through UI Automation (CalculatorResults / CalculatorExpression).
    private const string CalculatorScript = """
        $ErrorActionPreference='Stop';$expr=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))
        Add-Type -AssemblyName UIAutomationClient;Add-Type -AssemblyName UIAutomationTypes;Add-Type -AssemblyName System.Windows.Forms
        $sig='using System;using System.Runtime.InteropServices;public static class BaxyCalcWin{[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();}'
        if(-not ([System.Management.Automation.PSTypeName]'BaxyCalcWin').Type){Add-Type -TypeDefinition $sig}
        $root=[System.Windows.Automation.AutomationElement]::RootElement
        $cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'ApplicationFrameWindow')
        $calc=$null;foreach($f in $root.FindAll([System.Windows.Automation.TreeScope]::Children,$cond)){if($f.Current.Name -match '^(Calculadora|Calculator)$'){$calc=$f;break}}
        if($null -eq $calc){[pscustomobject]@{ok=$false;error='calculator_window_not_found'}|ConvertTo-Json -Compress;exit 2}
        $h=[IntPtr]$calc.Current.NativeWindowHandle;[void][BaxyCalcWin]::SetForegroundWindow($h);Start-Sleep -Milliseconds 300
        if([BaxyCalcWin]::GetForegroundWindow() -ne $h){[pscustomobject]@{ok=$false;error='calculator_not_foreground'}|ConvertTo-Json -Compress;exit 3}
        $keys=($expr -replace '[^0-9+\-*/().]','')
        if($keys.Length -eq 0){[pscustomobject]@{ok=$false;error='calculator_expression_invalid'}|ConvertTo-Json -Compress;exit 4}
        [System.Windows.Forms.SendKeys]::SendWait('{ESC}');Start-Sleep -Milliseconds 150
        foreach($ch in $keys.ToCharArray()){$k=switch($ch){'+'{'{+}'} '('{'{(}'} ')'{'{)}'} default{[string]$ch}};[System.Windows.Forms.SendKeys]::SendWait($k);Start-Sleep -Milliseconds 40}
        [System.Windows.Forms.SendKeys]::SendWait('=');Start-Sleep -Milliseconds 400
        $idCond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'CalculatorResults')
        $display=$calc.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$idCond)
        $exprCond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'CalculatorExpression')
        $shown=$calc.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$exprCond)
        if($null -eq $display){[pscustomobject]@{ok=$false;error='calculator_display_not_read'}|ConvertTo-Json -Compress;exit 5}
        $name=[string]$display.Current.Name;$exprName=if($shown){[string]$shown.Current.Name}else{''}
        $value=($name -replace '^[^0-9\-]*','').Trim()
        [pscustomobject]@{ok=$true;typed=$keys;displayName=$name;expressionName=$exprName;value=$value}|ConvertTo-Json -Compress
        """;

    private static readonly Regex CalculatorExpression = new(
        @"^\s*\d{1,12}(?:[.,]\d{1,6})?(?:\s*[-+*/×÷xX]\s*\d{1,12}(?:[.,]\d{1,6})?){1,8}\s*$",
        RegexOptions.CultureInvariant);

    private async ValueTask<ExternalCapabilityReceipt> CalculatorEvaluateAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        string expression = ExternalJson.RequiredString(arguments, "expression").Trim();
        if (!CalculatorExpression.IsMatch(expression))
        {
            return ExternalJson.Failure(operation, "calculator_expression_invalid");
        }
        string normalized = expression
            .Replace("×", "*", StringComparison.Ordinal)
            .Replace("÷", "/", StringComparison.Ordinal)
            .Replace("x", "*", StringComparison.OrdinalIgnoreCase)
            .Replace(",", ".", StringComparison.Ordinal)
            .Replace(" ", string.Empty, StringComparison.Ordinal);
        effectBoundary.Cross(token);
        ExternalProcessResult process = await RunPowerShellAsync(CalculatorScript, [Encode(normalized)], token);
        using JsonDocument document = ParseLastJson(process.Output);
        JsonElement root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object)
        {
            return ExternalJson.Failure(operation, "calculator_display_not_read", true);
        }
        if (!Bool(root, "ok"))
        {
            string code = root.TryGetProperty("error", out JsonElement error) && error.ValueKind == JsonValueKind.String
                ? error.GetString() ?? "calculator_display_not_read"
                : "calculator_display_not_read";
            return ExternalJson.Failure(operation, code, code is "calculator_display_not_read");
        }
        string value = root.TryGetProperty("value", out JsonElement valueElement) && valueElement.ValueKind == JsonValueKind.String
            ? valueElement.GetString() ?? string.Empty
            : string.Empty;
        if (string.IsNullOrWhiteSpace(value))
        {
            return ExternalJson.Failure(operation, "calculator_display_not_read", true);
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("expression", normalized);
            writer.WriteString("shownExpression", root.TryGetProperty("expressionName", out JsonElement shown) && shown.ValueKind == JsonValueKind.String ? shown.GetString() ?? string.Empty : string.Empty);
            writer.WriteString("display", root.TryGetProperty("displayName", out JsonElement display) && display.ValueKind == JsonValueKind.String ? display.GetString() ?? string.Empty : string.Empty);
            writer.WriteString("value", value);
            writer.WriteString("authority", "windows_calculator_uia_display");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    private static List<(string Company, string Tag, string Version, string DisplayName, string? Executable, string Scope)> EnumerateRegisteredPythons()
    {
        var installs = new List<(string Company, string Tag, string Version, string DisplayName, string? Executable, string Scope)>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach ((Microsoft.Win32.RegistryKey hive, string scope) in new[]
                 {
                     (Microsoft.Win32.Registry.CurrentUser, "user"),
                     (Microsoft.Win32.Registry.LocalMachine, "machine"),
                 })
        {
            foreach (string root in new[] { @"Software\Python", @"Software\WOW6432Node\Python" })
            {
                try
                {
                    using Microsoft.Win32.RegistryKey? python = hive.OpenSubKey(root, writable: false);
                    if (python is null)
                    {
                        continue;
                    }
                    foreach (string company in python.GetSubKeyNames())
                    {
                        using Microsoft.Win32.RegistryKey? companyKey = python.OpenSubKey(company, writable: false);
                        if (companyKey is null)
                        {
                            continue;
                        }
                        foreach (string tag in companyKey.GetSubKeyNames())
                        {
                            using Microsoft.Win32.RegistryKey? tagKey = companyKey.OpenSubKey(tag, writable: false);
                            if (tagKey is null)
                            {
                                continue;
                            }
                            string version = (tagKey.GetValue("Version") as string ?? tagKey.GetValue("SysVersion") as string ?? tag).Trim();
                            string displayName = (tagKey.GetValue("DisplayName") as string ?? $"{company} {tag}").Trim();
                            string? executable = null;
                            using (Microsoft.Win32.RegistryKey? installPath = tagKey.OpenSubKey("InstallPath", writable: false))
                            {
                                string? path = installPath?.GetValue("ExecutablePath") as string;
                                if (!string.IsNullOrWhiteSpace(path) && File.Exists(path))
                                {
                                    executable = Path.GetFullPath(path);
                                }
                            }
                            string identity = executable ?? $"{scope}|{company}|{tag}";
                            if (seen.Add(identity))
                            {
                                installs.Add((company, tag, version, displayName, executable, scope));
                            }
                        }
                    }
                }
                catch (Exception exception) when (exception is System.Security.SecurityException
                    or UnauthorizedAccessException or IOException)
                {
                    continue;
                }
            }
        }
        installs.Sort((left, right) => string.CompareOrdinal(right.Version, left.Version));
        return installs;
    }

    private static ExternalCapabilityReceipt PythonStatus(string operation)
    {
        List<(string Company, string Tag, string Version, string DisplayName, string? Executable, string Scope)> installs = EnumerateRegisteredPythons();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("pythonCount", installs.Count);
            writer.WriteStartArray("pythons");
            foreach ((string company, string tag, string version, string displayName, string? executable, string scope) in installs)
            {
                writer.WriteStartObject();
                writer.WriteString("company", company);
                writer.WriteString("tag", tag);
                writer.WriteString("pythonVersion", version);
                writer.WriteString("displayName", displayName);
                writer.WriteBoolean("executableFound", executable is not null);
                writer.WriteString("scope", scope);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "windows_registry_pep514_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // PIP1817 «instala requests con pip»: whether a package is installed is read
    // with pip show in every registered Python; nothing is installed or changed.
    private const string PipShowScript = """
        $ErrorActionPreference='Continue';$exe=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]));$pkg=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[1]))
        $out = & $exe -m pip show $pkg 2>&1 | Out-String
        [pscustomobject]@{ok=$true;exit=$LASTEXITCODE;output=$out}|ConvertTo-Json -Compress
        """;

    private static readonly Regex PythonPackageName = new(
        @"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,99})$",
        RegexOptions.CultureInvariant);

    private static string NormalizePythonPackage(string name) =>
        name.Replace('_', '-').Replace('.', '-').ToLowerInvariant();

    private async ValueTask<ExternalCapabilityReceipt> PythonPackageStatusAsync(
        string operation,
        JsonElement arguments,
        CancellationToken token)
    {
        string package = ExternalJson.RequiredString(arguments, "package").Trim();
        if (!PythonPackageName.IsMatch(package))
        {
            return ExternalJson.Failure(operation, "python_package_name_invalid");
        }
        List<(string Company, string Tag, string Version, string DisplayName, string? Executable, string Scope)> installs = EnumerateRegisteredPythons();
        var rows = new List<(string DisplayName, string Version, bool PipAvailable, bool Installed, string? PackageVersion)>();
        foreach ((string _, string _, string version, string displayName, string? executable, string _) in installs)
        {
            if (executable is null)
            {
                rows.Add((displayName, version, false, false, null));
                continue;
            }
            ExternalProcessResult process = await RunPowerShellAsync(PipShowScript, [Encode(executable), Encode(package)], token);
            string output = process.Output ?? string.Empty;
            int exit = -1;
            if (output.Contains('{', StringComparison.Ordinal))
            {
                try
                {
                    using JsonDocument document = ParseLastJson(output);
                    JsonElement root = document.RootElement;
                    if (root.ValueKind == JsonValueKind.Object)
                    {
                        output = root.TryGetProperty("output", out JsonElement text) && text.ValueKind == JsonValueKind.String ? text.GetString() ?? string.Empty : string.Empty;
                        exit = root.TryGetProperty("exit", out JsonElement code) && code.ValueKind == JsonValueKind.Number ? code.GetInt32() : -1;
                    }
                }
                catch (JsonException)
                {
                    exit = -1;
                }
            }
            bool pipAvailable = !output.Contains("No module named pip", StringComparison.OrdinalIgnoreCase);
            Match name = Regex.Match(output, @"(?im)^Name:\s*(\S+)\s*$");
            Match packageVersion = Regex.Match(output, @"(?im)^Version:\s*(\S+)\s*$");
            bool installed = pipAvailable && exit == 0 && name.Success
                && string.Equals(NormalizePythonPackage(name.Groups[1].Value), NormalizePythonPackage(package), StringComparison.Ordinal);
            rows.Add((displayName, version, pipAvailable, installed, installed && packageVersion.Success ? packageVersion.Groups[1].Value : null));
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("package", package);
            writer.WriteNumber("pythonCount", rows.Count);
            writer.WriteNumber("installedCount", rows.Count(row => row.Installed));
            writer.WriteStartArray("pythons");
            foreach ((string displayName, string version, bool pipAvailable, bool installed, string? packageVersion) in rows)
            {
                writer.WriteStartObject();
                writer.WriteString("displayName", displayName);
                writer.WriteString("pythonVersion", version);
                writer.WriteBoolean("pipAvailable", pipAvailable);
                writer.WriteBoolean("installed", installed);
                if (packageVersion is not null)
                {
                    writer.WriteString("packageVersion", packageVersion);
                }
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "python_pip_show_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // USB1823 «hace un backup de mis documentos a un pendrive»: the removable
    // drives connected right now, read through DriveInfo; nothing is copied.
    private static ExternalCapabilityReceipt RemovableStorageList(string operation)
    {
        var drives = new List<(string Letter, string Label, string Format, double FreeGiB, double TotalGiB)>();
        foreach (DriveInfo drive in DriveInfo.GetDrives())
        {
            try
            {
                if (drive.DriveType != DriveType.Removable || !drive.IsReady)
                {
                    continue;
                }
                string letter = drive.Name.TrimEnd('\\', '/');
                double free = Math.Round(drive.AvailableFreeSpace / 1073741824d, 1);
                double total = Math.Round(drive.TotalSize / 1073741824d, 1);
                drives.Add((letter, drive.VolumeLabel ?? string.Empty, drive.DriveFormat ?? string.Empty, free, total));
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                continue;
            }
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("driveCount", drives.Count);
            writer.WriteStartArray("drives");
            foreach ((string letter, string label, string format, double free, double total) in drives)
            {
                writer.WriteStartObject();
                writer.WriteString("letter", letter);
                writer.WriteString("label", label);
                writer.WriteString("format", format);
                writer.WriteNumber("freeGiB", free);
                writer.WriteNumber("totalGiB", total);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "windows_driveinfo_removable_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // DISCORD1839 «ve a Cotele en Discord»: the channel is looked up in the
    // client's quick switcher (Ctrl+K), its matches read by UI Automation and
    // the switcher closed with Escape; nothing is joined or opened.
    private const string ClientChannelLocateScript = """
        $ErrorActionPreference='Stop';$label=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))
        Add-Type -AssemblyName UIAutomationClient;Add-Type -AssemblyName UIAutomationTypes;Add-Type -AssemblyName System.Windows.Forms
        $sig='using System;using System.Runtime.InteropServices;public static class BaxyClientWin{[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);}'
        if(-not ([System.Management.Automation.PSTypeName]'BaxyClientWin').Type){Add-Type -TypeDefinition $sig}
        $root=[System.Windows.Automation.AutomationElement]::RootElement
        $cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'Chrome_WidgetWin_1')
        $w=$null;foreach($c in $root.FindAll([System.Windows.Automation.TreeScope]::Children,$cond)){if($c.Current.Name -match 'Discord'){$w=$c;break}}
        if($null -eq $w){[pscustomobject]@{ok=$false;error='client_window_not_found'}|ConvertTo-Json -Compress;exit 2}
        $h=[IntPtr]$w.Current.NativeWindowHandle;[void][BaxyClientWin]::ShowWindow($h,9)
        $escaped=[regex]::Replace($label,'([+^%~(){}\[\]])','{$1}');$needle=$label.ToLowerInvariant()
        function Read-Items {param($win,$nd) $r=@();foreach($e in $win.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)){if($e.Current.ControlType.ProgrammaticName -eq 'ControlType.ListItem'){$n=$e.Current.Name;if($n -and $n.ToLowerInvariant().Contains($nd)){$r+=$n.Substring(0,[Math]::Min(160,$n.Length))}}};,$r}
        # The product and its console compete for the foreground while this runs; a lost focus can drop the
        # keystrokes. Retry the whole focus+switcher+type+read sequence, re-asserting the foreground each round
        # and confirming it held, until the switcher shows matches; nothing is joined or opened.
        $items=@();$foreground=$false
        for($round=0;$round -lt 5 -and $items.Count -eq 0;$round++){
          [void][BaxyClientWin]::SetForegroundWindow($h);Start-Sleep -Milliseconds 500
          if([BaxyClientWin]::GetForegroundWindow() -ne $h){Start-Sleep -Milliseconds 400;continue}
          $foreground=$true
          [System.Windows.Forms.SendKeys]::SendWait('{ESC}');Start-Sleep -Milliseconds 250
          [void][BaxyClientWin]::SetForegroundWindow($h);Start-Sleep -Milliseconds 150
          [System.Windows.Forms.SendKeys]::SendWait('^k');Start-Sleep -Milliseconds 1400
          if([BaxyClientWin]::GetForegroundWindow() -ne $h){[System.Windows.Forms.SendKeys]::SendWait('{ESC}');continue}
          [System.Windows.Forms.SendKeys]::SendWait($escaped);Start-Sleep -Milliseconds 900
          for($poll=0;$poll -lt 10 -and $items.Count -eq 0;$poll++){$items=Read-Items $w $needle;if($items.Count -gt 0){break};Start-Sleep -Milliseconds 500}
          [System.Windows.Forms.SendKeys]::SendWait('{ESC}');Start-Sleep -Milliseconds 300
        }
        if(-not $foreground){[pscustomobject]@{ok=$false;error='client_not_foreground'}|ConvertTo-Json -Compress;exit 3}
        [pscustomobject]@{ok=$true;window=$w.Current.Name;items=@($items)}|ConvertTo-Json -Compress
        """;

    private static readonly Regex ClientChannelName = new(
        @"^[\p{L}\p{N} ._'!?#&-]{1,120}$",
        RegexOptions.CultureInvariant);

    private async ValueTask<ExternalCapabilityReceipt> ClientChannelLocateAsync(
        string operation,
        JsonElement arguments,
        CancellationToken token)
    {
        string client = ExternalJson.RequiredString(arguments, "client").Trim();
        string name = ExternalJson.RequiredString(arguments, "name").Trim();
        if (client != "discord")
        {
            return ExternalJson.Failure(operation, "client_not_supported");
        }
        if (!ClientChannelName.IsMatch(name))
        {
            return ExternalJson.Failure(operation, "channel_name_invalid");
        }
        ExternalProcessResult process = await RunPowerShellAsync(ClientChannelLocateScript, [Encode(name)], token);
        using JsonDocument document = ParseLastJson(process.Output);
        JsonElement root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object)
        {
            return ExternalJson.Failure(operation, "client_quick_switcher_not_read", true);
        }
        if (!Bool(root, "ok"))
        {
            string code = root.TryGetProperty("error", out JsonElement error) && error.ValueKind == JsonValueKind.String
                ? error.GetString() ?? "client_quick_switcher_not_read"
                : "client_quick_switcher_not_read";
            return ExternalJson.Failure(operation, code, code == "client_quick_switcher_not_read");
        }
        var items = new List<string>();
        if (root.TryGetProperty("items", out JsonElement itemsElement) && itemsElement.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in itemsElement.EnumerateArray())
            {
                if (item.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(item.GetString()))
                {
                    items.Add(item.GetString()!);
                }
            }
        }
        string channelName = string.Empty, channelKind = string.Empty, server = string.Empty;
        if (items.Count > 0)
        {
            string[] parts = items[0].Split(", ", StringSplitOptions.TrimEntries);
            channelName = parts[0];
            string kind = parts.Length > 1 ? parts[1].ToLowerInvariant() : string.Empty;
            channelKind = kind.Contains("voz", StringComparison.Ordinal) || kind.Contains("voice", StringComparison.Ordinal) ? "voice"
                : kind.Contains("texto", StringComparison.Ordinal) || kind.Contains("text", StringComparison.Ordinal) ? "text"
                : kind.Length > 0 ? kind : "unknown";
            server = parts.Length > 2 ? parts[2] : string.Empty;
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("client", client);
            writer.WriteString("query", name);
            writer.WriteBoolean("found", items.Count > 0);
            writer.WriteNumber("matchCount", items.Count);
            writer.WriteString("channelName", channelName);
            writer.WriteString("channelKind", channelKind);
            writer.WriteString("server", server);
            writer.WriteBoolean("joined", false);
            writer.WriteString("authority", "client_quick_switcher_uia_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static ExternalCapabilityReceipt DisplayStatus(string operation)
    {
        var monitors = new List<(string Name, bool Primary, uint Width, uint Height, uint Hertz)>();
        for (uint index = 0; index < 32; index++)
        {
            DisplayDevice device = default;
            device.Size = (uint)Marshal.SizeOf<DisplayDevice>();
            if (!EnumDisplayDevicesW(null, index, ref device, 0))
            {
                break;
            }
            const uint attachedToDesktop = 0x1;
            const uint primaryDevice = 0x4;
            if ((device.StateFlags & attachedToDesktop) == 0)
            {
                continue;
            }
            string name;
            unsafe
            {
                name = new string(device.DeviceName).TrimEnd('\0');
            }
            DeviceMode mode = default;
            mode.Size = (ushort)Marshal.SizeOf<DeviceMode>();
            const int currentSettings = -1;
            if (!EnumDisplaySettingsW(name, currentSettings, ref mode))
            {
                continue;
            }
            monitors.Add((name, (device.StateFlags & primaryDevice) != 0, mode.PelsWidth, mode.PelsHeight, mode.DisplayFrequency));
        }
        if (monitors.Count == 0)
        {
            return ExternalJson.Failure(operation, "display_devices_not_found");
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("monitorCount", monitors.Count);
            writer.WriteStartArray("monitors");
            foreach ((string name, bool primary, uint width, uint height, uint hertz) in monitors)
            {
                writer.WriteStartObject();
                writer.WriteString("name", name);
                writer.WriteBoolean("primary", primary);
                writer.WriteNumber("width", width);
                writer.WriteNumber("height", height);
                writer.WriteNumber("refreshHz", hertz);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "windows_display_devices_api_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    private unsafe struct DisplayDevice
    {
        public uint Size;
        public fixed char DeviceName[32];
        public fixed char DeviceString[128];
        public uint StateFlags;
        public fixed char DeviceId[128];
        public fixed char DeviceKey[128];
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    private unsafe struct DeviceMode
    {
        public fixed char DeviceName[32];
        public ushort SpecVersion;
        public ushort DriverVersion;
        public ushort Size;
        public ushort DriverExtra;
        public uint Fields;
        public int PositionX;
        public int PositionY;
        public uint DisplayOrientation;
        public uint DisplayFixedOutput;
        public short Color;
        public short Duplex;
        public short YResolution;
        public short TtOption;
        public short Collate;
        public fixed char FormName[32];
        public ushort LogPixels;
        public uint BitsPerPel;
        public uint PelsWidth;
        public uint PelsHeight;
        public uint DisplayFlags;
        public uint DisplayFrequency;
        public uint IcmMethod;
        public uint IcmIntent;
        public uint MediaType;
        public uint DitherType;
        public uint Reserved1;
        public uint Reserved2;
        public uint PanningWidth;
        public uint PanningHeight;
    }

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumDisplayDevicesW(string? device, uint deviceIndex, ref DisplayDevice displayDevice, uint flags);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumDisplaySettingsW(string deviceName, int modeIndex, ref DeviceMode deviceMode);

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
        bool inputOnly = requestedKind is "mouse" or "keyboard";
        ExternalProcessResult process = inputOnly
            ? await RunPowerShellAsync(
                ConnectedInputListScript,
                [requestedKind == "mouse" ? "Mouse" : "Keyboard"],
                cancellationToken)
            : await RunPowerShellAsync(
                PeripheralListScript,
                [requestedKind],
                cancellationToken);
        using JsonDocument source = JsonDocument.Parse(process.Output);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteStartArray("devices");
            if (requestedKind is "all" or "printer")
                WritePeripherals(writer, source.RootElement, "printers", "printer", "Name", "Name", "PrinterStatus");
            if (requestedKind is "all" or "scanner")
                WritePeripherals(writer, source.RootElement, "scanners", "scanner", "Name", "DeviceID", "Status");
            if (requestedKind is "all" or "usb")
                WritePeripherals(writer, source.RootElement, "usb", "usb", "FriendlyName", "InstanceId", "Status");
            if (requestedKind is "all" or "mouse")
                WritePeripherals(writer, source.RootElement, "mice", "mouse", "FriendlyName", "InstanceId", "Status");
            if (requestedKind is "all" or "keyboard")
                WritePeripherals(writer, source.RootElement, "keyboards", "keyboard", "FriendlyName", "InstanceId", "Status");
            writer.WriteEndArray(); writer.WriteString("requestedKind", requestedKind);
            writer.WriteString(
                "authority",
                inputOnly
                    ? "windows_pnputil_connected_parent_registry"
                    : "windows_print_wia_usb_hid_inventory");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> PrintAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string deviceId = ExternalJson.RequiredString(arguments, "deviceId");
        string documentId = ExternalJson.RequiredString(arguments, "documentId");
        if (!_peripherals.TryGetValue(deviceId, out PeripheralIdentity? printer) || printer.Kind != "printer")
            return ExternalJson.Failure(operation, "printer_identity_expired");
        string? path = ResolveDocument(documentId);
        if (path is null) return ExternalJson.Failure(operation, "print_document_not_resolved");
        string payload = JsonPayload((writer) => { writer.WriteString("printer", printer.NativeId); writer.WriteString("path", path); });
        effectBoundary.Cross(cancellationToken);
        ExternalProcessResult process = await RunPowerShellAsync(PrintScript, [Encode(payload)], cancellationToken);
        using JsonDocument response = ParseLastJson(process.Output);
        bool effect = Bool(response.RootElement, "effectObserved");
        if (!Bool(response.RootElement, "ok"))
            return effectBoundary.Failure(operation, "print_job_not_verified", effect);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteString("deviceId", deviceId);
            writer.WriteString("documentId", documentId); writer.WriteString("jobId", "print_" + response.RootElement.GetProperty("jobId").GetString());
            writer.WriteString("status", response.RootElement.GetProperty("status").GetString());
            writer.WriteString("authority", "windows_print_spooler_postread"); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, true);
    }

    private async ValueTask<ExternalCapabilityReceipt> ScanAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string deviceId = ExternalJson.RequiredString(arguments, "deviceId");
        if (!_peripherals.TryGetValue(deviceId, out PeripheralIdentity? scanner) || scanner.Kind != "scanner")
            return ExternalJson.Failure(operation, "scanner_identity_expired");
        effectBoundary.Cross(cancellationToken);
        Directory.CreateDirectory(_scanRoot); string scanId = "scan_" + Guid.NewGuid().ToString("N");
        string path = Path.Combine(_scanRoot, scanId + ".bmp");
        string payload = JsonPayload(writer => { writer.WriteString("deviceId", scanner.NativeId); writer.WriteString("path", path); });
        ExternalProcessResult process = await RunPowerShellAsync(ScanScript, [Encode(payload)], cancellationToken);
        using JsonDocument response = ParseLastJson(process.Output); bool effect = Bool(response.RootElement, "effectObserved");
        if (!Bool(response.RootElement, "ok") || !File.Exists(path))
            return effectBoundary.Failure(operation, "scan_capture_not_verified", effect);
        byte[] bytes = await File.ReadAllBytesAsync(path, cancellationToken);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteString("deviceId", deviceId);
            writer.WriteString("captureId", scanId); writer.WriteNumber("length", bytes.Length);
            writer.WriteString("sha256", Convert.ToHexStringLower(SHA256.HashData(bytes)));
            writer.WriteString("authority", "wia_transfer_postread"); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, true);
    }

    private async ValueTask<ExternalCapabilityReceipt> WifiProfilesAsync(string operation, CancellationToken token)
    {
        ExternalProcessResult process = await RunPowerShellAsync(WifiProfilesScript, [], token);
        using JsonDocument source = JsonDocument.Parse(process.Output);
        string[] profiles = source.RootElement.TryGetProperty("profiles", out JsonElement values)
            ? values.ValueKind switch
            {
                JsonValueKind.Array => values
                    .EnumerateArray()
                    .Select(static item => item.GetString() ?? string.Empty)
                    .Where(static item => item.Length > 0)
                    .ToArray(),
                JsonValueKind.String => [values.GetString() ?? string.Empty],
                _ => [],
            }
            : [];
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteStartArray("profiles");
            foreach (string profile in profiles)
            {
                string id = Opaque("wifi", profile);
                _wifi[id] = profile;
                writer.WriteStartObject();
                writer.WriteString("profileId", id);
                writer.WriteString("label", profile);
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            writer.WriteString("authority", "netsh_wlan_profile_snapshot");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, false);
    }

    private async ValueTask<ExternalCapabilityReceipt> WifiConnectAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        string id = ExternalJson.RequiredString(arguments, "profileId");
        if (!_wifi.TryGetValue(id, out string? profile))
        {
            return ExternalJson.Failure(operation, "wifi_profile_identity_expired");
        }

        return await ConnectWifiProfileAsync(operation, id, profile, effectBoundary, token);
    }

    private async ValueTask<ExternalCapabilityReceipt> WifiConnectNamedAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        string requested = ExternalJson.RequiredString(arguments, "profileName");
        string? place = arguments.TryGetProperty("place", out JsonElement placeValue)
            && placeValue.ValueKind == JsonValueKind.String
            ? placeValue.GetString()
            : null;
        ExternalProcessResult process = await RunPowerShellAsync(WifiProfilesScript, [], token);
        using JsonDocument source = JsonDocument.Parse(process.Output);
        string[] profiles = source.RootElement.TryGetProperty("profiles", out JsonElement values)
            ? values.ValueKind switch
            {
                JsonValueKind.Array => values
                    .EnumerateArray()
                    .Select(static item => item.GetString() ?? string.Empty)
                    .Where(static item => item.Length > 0)
                    .ToArray(),
                JsonValueKind.String => [values.GetString() ?? string.Empty],
                _ => [],
            }
            : [];
        string folded = FoldProfile(requested);
        string[] ordinal = profiles
            .Where(profile =>
                string.Equals(profile, requested, StringComparison.Ordinal))
            .ToArray();
        string[] exact = profiles
            .Where(profile => FoldProfile(profile) == folded)
            .ToArray();
        string[] matches = ordinal.Length > 0
            ? ordinal
            : exact.Length > 0
                ? exact
                : profiles.Where(profile =>
                {
                    string candidate = FoldProfile(profile);
                    return folded.Length >= 3
                        && (candidate.Contains(folded, StringComparison.Ordinal)
                            || folded.Contains(candidate, StringComparison.Ordinal));
                }).ToArray();
        bool byPlace = false;
        if (matches.Length == 0 && place is not null)
        {
            // REOPEN1957 H0170/H0376: «casa» names a place, not a profile. The
            // profile the person associated with it earlier is the one.
            string? remembered = ReadWifiPlace(place);
            if (remembered is not null)
            {
                matches = profiles.Where(profile => string.Equals(profile, remembered, StringComparison.Ordinal)).ToArray();
                byPlace = matches.Length == 1;
            }

            if (matches.Length == 0)
            {
                return ExternalJson.Failure(operation, "wifi_place_unknown");
            }
        }

        if (matches.Length == 0)
        {
            return ExternalJson.Failure(operation, "wifi_profile_not_found");
        }

        if (matches.Length != 1)
        {
            return ExternalJson.Failure(operation, "wifi_profile_name_ambiguous");
        }

        string profile = matches[0];
        string id = Opaque("wifi", profile);
        _wifi[id] = profile;
        ExternalCapabilityReceipt receipt = await ConnectWifiProfileAsync(operation, id, profile, effectBoundary, token, place);
        if (receipt.Verified && place is not null && !byPlace)
        {
            WriteWifiPlace(place, profile);
        }

        return receipt;
    }

    private string WifiPlacesPath => Path.Combine(_scanRoot, "wifi-places.v1.json");

    private string? ReadWifiPlace(string place)
    {
        try
        {
            if (!File.Exists(WifiPlacesPath))
            {
                return null;
            }

            using JsonDocument document = JsonDocument.Parse(File.ReadAllBytes(WifiPlacesPath));
            return document.RootElement.ValueKind == JsonValueKind.Object
                && document.RootElement.TryGetProperty(place, out JsonElement value)
                && value.ValueKind == JsonValueKind.String
                ? value.GetString()
                : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    private void WriteWifiPlace(string place, string profile)
    {
        var places = new SortedDictionary<string, string>(StringComparer.Ordinal);
        try
        {
            if (File.Exists(WifiPlacesPath))
            {
                using JsonDocument document = JsonDocument.Parse(File.ReadAllBytes(WifiPlacesPath));
                if (document.RootElement.ValueKind == JsonValueKind.Object)
                {
                    foreach (JsonProperty property in document.RootElement.EnumerateObject())
                    {
                        if (property.Value.ValueKind == JsonValueKind.String)
                        {
                            places[property.Name] = property.Value.GetString() ?? string.Empty;
                        }
                    }
                }
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            places.Clear();
        }

        places[place] = profile;
        Directory.CreateDirectory(_scanRoot);
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            foreach ((string key, string value) in places)
            {
                writer.WriteString(key, value);
            }

            writer.WriteEndObject();
        }

        File.WriteAllBytes(WifiPlacesPath, stream.ToArray());
    }

    private async ValueTask<ExternalCapabilityReceipt> ConnectWifiProfileAsync(
        string operation,
        string id,
        string profile,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token,
        string? place = null)
    {
        effectBoundary.Cross(token);
        ExternalProcessResult dispatch = await _runner.RunAsync(
            "netsh.exe",
            ["wlan", "connect", "name=" + profile],
            TimeSpan.FromSeconds(15),
            token);
        if (dispatch.ExitCode != 0)
        {
            return effectBoundary.Failure(operation, "wifi_connect_dispatch_rejected");
        }

        for (int observation = 0; observation <= 30; observation++)
        {
            using JsonDocument status = await WifiStatusAsync(token);
            if (Bool(status.RootElement, "connected")
                && string.Equals(
                    status.RootElement.GetProperty("profile").GetString(),
                    profile,
                    StringComparison.OrdinalIgnoreCase))
            {
                return ExternalJson.Success(operation, WifiResult(id, true, place), true);
            }

            if (observation < 30)
            {
                await _delay(TimeSpan.FromMilliseconds(500), token);
            }
        }

        return ExternalJson.Failure(operation, "wifi_connect_not_verified", true);
    }

    private async ValueTask<ExternalCapabilityReceipt> WifiDisconnectAsync(
        string operation,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        effectBoundary.Cross(token);
        ExternalProcessResult dispatch = await _runner.RunAsync(
            "netsh.exe",
            ["wlan", "disconnect"],
            TimeSpan.FromSeconds(15),
            token);
        if (dispatch.ExitCode != 0)
        {
            return effectBoundary.Failure(operation, "wifi_disconnect_dispatch_rejected");
        }

        for (int observation = 0; observation <= 20; observation++)
        {
            using JsonDocument status = await WifiStatusAsync(token);
            if (!Bool(status.RootElement, "connected"))
            {
                return ExternalJson.Success(
                    operation,
                    WifiResult(null, false),
                    true);
            }

            if (observation < 20)
            {
                await _delay(TimeSpan.FromMilliseconds(300), token);
            }
        }

        return ExternalJson.Failure(operation, "wifi_disconnect_not_verified", true);
    }

    private static ValueTask DelayAsync(
        TimeSpan delay,
        CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    private async ValueTask<ExternalCapabilityReceipt> WifiEnsureConnectedAsync(
        string operation,
        CancellationToken token)
    {
        using JsonDocument status = await WifiStatusAsync(token);
        if (!Bool(status.RootElement, "connected"))
            return ExternalJson.Failure(operation, "wifi_saved_profile_required");
        string profile = status.RootElement.TryGetProperty("profile", out JsonElement value)
            ? value.GetString() ?? string.Empty
            : string.Empty;
        if (string.IsNullOrWhiteSpace(profile))
            return ExternalJson.Failure(operation, "wifi_connected_profile_not_observed");
        string id = Opaque("wifi", profile);
        _wifi[id] = profile;
        return ExternalJson.Success(operation, WifiResult(id, true), false);
    }

    // NETWORK1729 «qué redes wifi hay»: the networks the adapter sees right now.
    // A powered-down radio is a typed state (wifi_interface_off), never a scan.
    private const string WifiScanScript = """
        $text=@(netsh wlan show networks mode=bssid);$joined=($text -join "`n")
        if($joined -match '(?i)apagada|powered down|is not running|no se está ejecutando|no está en ejecución'){[pscustomobject]@{ok=$false;error='wifi_interface_off'}|ConvertTo-Json -Compress;exit 0}
        if($joined -match '(?i)no hay ninguna interfaz|there is no wireless interface|no wireless interface'){[pscustomobject]@{ok=$false;error='wifi_interface_unavailable'}|ConvertTo-Json -Compress;exit 0}
        $networks=@();$current=$null
        foreach($line in $text){
          if($line -match '^\s*SSID\s+\d+\s*:\s*(.*?)\s*$'){if($current){$networks+=$current};$current=[ordered]@{ssid=$Matches[1];authentication='';signalPercent=$null};continue}
          if($null -eq $current){continue}
          if($line -match '^\s*(?:Authentication|Autenticación)\s*:\s*(.+?)\s*$' -and -not $current.authentication){$current.authentication=$Matches[1];continue}
          if($line -match '^\s*(?:Signal|Señal)\s*:\s*(\d+)\s*%' -and $null -eq $current.signalPercent){$current.signalPercent=[int]$Matches[1];continue}
        }
        if($current){$networks+=$current}
        [pscustomobject]@{ok=$true;networks=@($networks|ForEach-Object {[pscustomobject]$_})}|ConvertTo-Json -Compress -Depth 4
        """;

    private async ValueTask<ExternalCapabilityReceipt> WifiScanAsync(
        string operation,
        CancellationToken token)
    {
        ExternalProcessResult process = await RunPowerShellAsync(WifiScanScript, [], token);
        using JsonDocument document = ParseLastJson(process.Output);
        JsonElement root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object)
        {
            return ExternalJson.Failure(operation, "wifi_scan_not_read");
        }
        if (!Bool(root, "ok"))
        {
            string code = String(root, "error");
            return ExternalJson.Failure(operation, string.IsNullOrWhiteSpace(code) ? "wifi_scan_not_read" : code);
        }
        var networks = new List<(string Ssid, string Authentication, int? Signal)>();
        if (root.TryGetProperty("networks", out JsonElement list) && list.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in list.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object) continue;
                string ssid = String(item, "ssid");
                int? signal = item.TryGetProperty("signalPercent", out JsonElement signalElement)
                    && signalElement.ValueKind == JsonValueKind.Number
                    && signalElement.TryGetInt32(out int parsed)
                        ? parsed
                        : null;
                networks.Add((ssid, String(item, "authentication"), signal));
                if (networks.Count >= 50) break;
            }
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("networkCount", networks.Count);
            writer.WriteStartArray("networks");
            foreach ((string ssid, string authentication, int? signal) in networks)
            {
                writer.WriteStartObject();
                writer.WriteString("ssid", string.IsNullOrWhiteSpace(ssid) ? "(oculta)" : ssid);
                writer.WriteBoolean("hidden", string.IsNullOrWhiteSpace(ssid));
                writer.WriteString("authentication", authentication);
                if (signal is int value) writer.WriteNumber("signalPercent", value); else writer.WriteNull("signalPercent");
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "netsh_wlan_show_networks_bssid");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> WifiConnectionStatusAsync(
        string operation,
        CancellationToken token)
    {
        using JsonDocument first = await WifiStatusAsync(token);
        using JsonDocument second = await WifiStatusAsync(token);
        bool firstConnected = Bool(first.RootElement, "connected");
        bool secondConnected = Bool(second.RootElement, "connected");
        string firstProfile = first.RootElement.TryGetProperty("profile", out JsonElement firstValue)
            ? firstValue.GetString() ?? string.Empty
            : string.Empty;
        string secondProfile = second.RootElement.TryGetProperty("profile", out JsonElement secondValue)
            ? secondValue.GetString() ?? string.Empty
            : string.Empty;
        if (firstConnected != secondConnected
            || !string.Equals(firstProfile, secondProfile, StringComparison.Ordinal))
        {
            return ExternalJson.Failure(operation, "wifi_status_changed_during_read");
        }
        if (secondConnected && string.IsNullOrWhiteSpace(secondProfile))
            return ExternalJson.Failure(operation, "wifi_connected_profile_not_observed");
        string? id = null;
        if (secondConnected)
        {
            id = Opaque("wifi", secondProfile);
            _wifi[id] = secondProfile;
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("connected", secondConnected);
            if (id is null) writer.WriteNull("profileId");
            else writer.WriteString("profileId", id);
            writer.WriteString("authority", "netsh_wlan_status_secondread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, false);
    }

    private async ValueTask<ExternalCapabilityReceipt> SettingAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        string setting = ExternalJson.RequiredString(arguments, "setting");
        int value = ExternalJson.OptionalInt(arguments, "value", -1);
        if (setting == "airplane_mode")
        {
            return await AirplaneModeSetAsync(operation, value, effectBoundary, token).ConfigureAwait(false);
        }

        if (setting == "do_not_disturb")
        {
            if (value is not (0 or 1))
            {
                return ExternalJson.Failure(
                    operation,
                    "do_not_disturb_value_invalid");
            }

            effectBoundary.Cross(token);
            ExternalProcessResult quietProcess = await RunPowerShellAsync(
                DoNotDisturbScript,
                [value.ToString(System.Globalization.CultureInfo.InvariantCulture)],
                token);
            using JsonDocument quietResponse = ParseLastJson(quietProcess.Output);
            bool quietEffect = Bool(quietResponse.RootElement, "effectObserved");
            if (!Bool(quietResponse.RootElement, "ok"))
            {
                return effectBoundary.Failure(
                    operation,
                    "do_not_disturb_postread_failed",
                    quietEffect);
            }

            JsonElement quietResult = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("setting", setting);
                writer.WriteNumber("value", value);
                writer.WriteNumber(
                    "before",
                    quietResponse.RootElement.GetProperty("before").GetInt32());
                writer.WriteString(
                    "authority",
                    "windows_uia_notifications_toggle_postread");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, quietResult, quietEffect);
        }

        if (setting != "brightness")
        {
            return ExternalJson.Failure(
                operation,
                "night_light_public_api_unavailable");
        }

        if (value is < 0 or > 100)
        {
            return ExternalJson.Failure(operation, "brightness_value_invalid");
        }

        effectBoundary.Cross(token);
        ExternalProcessResult process = await RunPowerShellAsync(
            BrightnessScript,
            [value.ToString(System.Globalization.CultureInfo.InvariantCulture)],
            token);
        using JsonDocument response = ParseLastJson(process.Output);
        bool effect = Bool(response.RootElement, "effectObserved");
        if (!Bool(response.RootElement, "ok"))
        {
            return effectBoundary.Failure(
                operation,
                "brightness_postread_failed",
                effect);
        }

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", setting);
            writer.WriteNumber("value", value);
            writer.WriteString("authority", "wmi_monitor_brightness_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, true);
    }

    private async ValueTask<ExternalCapabilityReceipt> SettingAdjustAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        string setting = ExternalJson.RequiredString(arguments, "setting");
        string direction = ExternalJson.RequiredString(arguments, "direction");
        int amount = ExternalJson.OptionalInt(arguments, "amount", -1);
        if (setting != "brightness"
            || direction is not ("up" or "down")
            || amount is < 1 or > 100)
        {
            return ExternalJson.Failure(
                operation,
                "brightness_adjustment_invalid");
        }

        int delta = direction == "up" ? amount : -amount;
        effectBoundary.Cross(token);
        ExternalProcessResult process = await RunPowerShellAsync(
            BrightnessAdjustScript,
            [delta.ToString(System.Globalization.CultureInfo.InvariantCulture)],
            token);
        using JsonDocument response = ParseLastJson(process.Output);
        bool effect = Bool(response.RootElement, "effectObserved");
        if (!Bool(response.RootElement, "ok"))
        {
            return effectBoundary.Failure(
                operation,
                "brightness_adjustment_postread_failed",
                effect);
        }

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", setting);
            writer.WriteString("direction", direction);
            writer.WriteNumber("amount", amount);
            writer.WritePropertyName("baselineValues");
            response.RootElement.GetProperty("baselineValues").WriteTo(writer);
            writer.WritePropertyName("values");
            response.RootElement.GetProperty("values").WriteTo(writer);
            writer.WriteString(
                "authority",
                "wmi_monitor_brightness_relative_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effect);
    }

    private async ValueTask<ExternalCapabilityReceipt> SettingStatusAsync(
        string operation, JsonElement arguments, CancellationToken token)
    {
        string setting = ExternalJson.RequiredString(arguments, "setting");
        if (setting == "airplane_mode")
            return await AirplaneModeStatusAsync(operation).ConfigureAwait(false);
        if (setting != "brightness")
            return ExternalJson.Failure(operation, "brightness_status_invalid");
        ExternalProcessResult process = await RunPowerShellAsync(
            BrightnessStatusScript, [], token);
        using JsonDocument response = ParseLastJson(process.Output);
        if (!Bool(response.RootElement, "ok")
            || !response.RootElement.TryGetProperty("monitors", out JsonElement monitors))
            return ExternalJson.Failure(operation, "brightness_status_verification_failed");
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", setting);
            writer.WritePropertyName("monitors");
            monitors.WriteTo(writer);
            writer.WriteString("authority", "wmi_monitor_brightness_secondread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, false);
    }

    private void WritePeripherals(
        Utf8JsonWriter writer,
        JsonElement root,
        string property,
        string kind,
        string nameField,
        string identityField,
        string statusField)
    {
        if (!root.TryGetProperty(property, out JsonElement values))
        {
            return;
        }

        IEnumerable<JsonElement> items = values.ValueKind switch
        {
            JsonValueKind.Array => values.EnumerateArray(),
            JsonValueKind.Object => [values],
            _ => [],
        };
        foreach (JsonElement item in items)
        {
            string name = String(item, nameField);
            string native = String(item, identityField);
            if (native.Length == 0)
            {
                continue;
            }

            string id = Opaque(kind, native);
            _peripherals[id] = new(kind, native, name);
            writer.WriteStartObject();
            writer.WriteString("deviceId", id);
            writer.WriteString("kind", kind);
            writer.WriteString("name", name);
            writer.WriteString("status", String(item, statusField));
            writer.WriteEndObject();
        }
    }

    private string? ResolveDocument(string id) =>
        Directory.Exists(_documentsRoot)
            ? Directory
                .EnumerateFiles(_documentsRoot, "*.*")
                .Where(static path =>
                    Path.GetExtension(path) is ".docx" or ".xlsx" or ".pdf")
                .SingleOrDefault(path =>
                    Opaque(
                        "document",
                        Path.GetFullPath(path).ToUpperInvariant()) == id)
            : null;

    private async ValueTask<JsonDocument> WifiStatusAsync(
        CancellationToken token)
    {
        ExternalProcessResult process = await RunPowerShellAsync(
            WifiStatusScript,
            [],
            token);
        return JsonDocument.Parse(process.Output);
    }

    private async ValueTask<ExternalProcessResult> RunPowerShellAsync(
        string script,
        IReadOnlyList<string> arguments,
        CancellationToken token)
    {
        var processArguments = new List<string>
        {
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "& {\n" + script + "\n}",
        };
        processArguments.AddRange(arguments);
        return await _runner.RunAsync(
            "powershell.exe",
            processArguments,
            TimeSpan.FromSeconds(60),
            token);
    }

    private static JsonElement WifiResult(string? id, bool connected, string? place = null) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            if (place is not null)
            {
                // The place word is the person's; the SSID stays out of the result.
                writer.WriteString("place", place);
            }

            if (id is null)
            {
                writer.WriteNull("profileId");
            }
            else
            {
                writer.WriteString("profileId", id);
            }

            writer.WriteBoolean("connected", connected);
            writer.WriteString("authority", "netsh_wlan_postread");
            writer.WriteEndObject();
        });

    private static string JsonPayload(Action<Utf8JsonWriter> write) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            write(writer);
            writer.WriteEndObject();
        }).GetRawText();

    private static string Encode(string value) =>
        Convert.ToBase64String(Encoding.UTF8.GetBytes(value));

    private static JsonDocument ParseLastJson(string value) =>
        JsonDocument.Parse(
            value.Split(
                    ['\r', '\n'],
                    StringSplitOptions.RemoveEmptyEntries)
                .LastOrDefault() ?? "{}");

    private static bool Bool(JsonElement root, string name) =>
        root.TryGetProperty(name, out JsonElement value)
        && value.ValueKind == JsonValueKind.True;

    private static string String(JsonElement root, string name) =>
        root.TryGetProperty(name, out JsonElement value)
        && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    private static string FoldProfile(string value) =>
        new(
            value
                .Normalize(NormalizationForm.FormD)
                .Where(character =>
                    System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                    != System.Globalization.UnicodeCategory.NonSpacingMark)
                .Select(char.ToLowerInvariant)
                .Where(character =>
                    char.IsLetterOrDigit(character)
                    || char.IsWhiteSpace(character)
                    || character is '-' or '.')
                .ToArray());

    private static string Opaque(string prefix, string value) =>
        prefix
        + "_"
        + Convert.ToHexStringLower(
            SHA256.HashData(Encoding.UTF8.GetBytes(value)))[..24];

    private sealed record PeripheralIdentity(
        string Kind,
        string NativeId,
        string Name);
}

internal sealed record BluetoothDeviceSnapshot(
    string NativeId,
    string Name,
    bool IsPaired,
    bool CanPair);

internal interface IBluetoothDeviceInventory
{
    ValueTask<IReadOnlyList<BluetoothDeviceSnapshot>> ListAsync(
        CancellationToken cancellationToken);
}

internal sealed class WindowsBluetoothDeviceInventory : IBluetoothDeviceInventory
{
    public async ValueTask<IReadOnlyList<BluetoothDeviceSnapshot>> ListAsync(
        CancellationToken cancellationToken)
    {
        var devices = new Dictionary<string, BluetoothDeviceSnapshot>(StringComparer.Ordinal);
        foreach (string selector in new[]
        {
            BluetoothDevice.GetDeviceSelector(),
            BluetoothDevice.GetDeviceSelectorFromPairingState(false),
            BluetoothLEDevice.GetDeviceSelector(),
            BluetoothLEDevice.GetDeviceSelectorFromPairingState(false),
        })
        {
            DeviceInformationCollection found = await DeviceInformation
                .FindAllAsync(selector)
                .AsTask(cancellationToken)
                .ConfigureAwait(false);
            cancellationToken.ThrowIfCancellationRequested();
            foreach (DeviceInformation item in found)
            {
                devices[item.Id] = new BluetoothDeviceSnapshot(
                    item.Id,
                    item.Name,
                    item.Pairing.IsPaired,
                    item.Pairing.CanPair);
            }
        }

        return devices.Values.ToArray();
    }
}
