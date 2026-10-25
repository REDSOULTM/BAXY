using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.Infrastructure;
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
        # Auditoría final (regla 3): a kind whose read failed (spooler stopped, WIA or PnP unanswered) is listed in
        # unread, never as no devices of that kind.
        $p=@();$s=@();$u=@();$m=@();$k=@();$unread=@()
        if($kind -in @('all','printer')){try{$p=@(Get-Printer -ErrorAction Stop|Select-Object Name,@{n='PrinterStatus';e={[string]$_.PrinterStatus}})}catch{$unread+=@('printer')}}
        if($kind -in @('all','scanner')){try{$d=New-Object -ComObject WIA.DeviceManager;foreach($i in $d.DeviceInfos){if($i.Type -eq 1){$s+=@([pscustomobject]@{Name=[string]$i.Properties.Item('Name').Value;DeviceID=[string]$i.DeviceID;Status='available'})}}}catch{$s=@();$unread+=@('scanner')}}
        if($kind -in @('all','usb')){try{$u=@(Get-PnpDevice -PresentOnly -ErrorAction Stop|Where-Object {$_.InstanceId -like 'USB*'}|Select-Object FriendlyName,Status,InstanceId)}catch{$unread+=@('usb')}}
        function Get-BaxyPresent([string]$className) {
          try{@(Get-PnpDevice -PresentOnly -Class $className -ErrorAction Stop)}
          catch{if($_.CategoryInfo.Category -ne 'ObjectNotFound'){throw};@()}
        }
        function Get-BaxyInputDevices([string]$className) {
          @(
            Get-BaxyPresent $className|ForEach-Object {
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
        if($kind -in @('all','mouse')){try{$m=@(Get-BaxyInputDevices 'Mouse')}catch{$m=@();$unread+=@('mouse')}}
        if($kind -in @('all','keyboard')){try{$k=@(Get-BaxyInputDevices 'Keyboard')}catch{$k=@();$unread+=@('keyboard')}}
        [pscustomobject]@{printers=$p;scanners=$s;usb=$u;mice=$m;keyboards=$k;unread=@($unread)}|ConvertTo-Json -Depth 5 -Compress
        """;
    private const string ConnectedInputListScript = """
        $ErrorActionPreference='Stop'
        $class=[string]$args[0]
        if($class -notin @('Mouse','Keyboard')){throw 'input_class_invalid'}
        $text=(& pnputil.exe /enum-devices /class $class /connected /relations|Out-String)
        if($LASTEXITCODE -ne 0){throw 'pnputil_not_read'}
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
        # Ronda final 9 (regla 3): a queue not read before would take any job already there for this one.
        try {$before=@(Get-PrintJob -PrinterName ([string]$i.printer) -ErrorAction Stop|ForEach-Object {$_.ID})}
        catch {[pscustomobject]@{ok=$false;effectObserved=$false;error='print_queue_not_read'}|ConvertTo-Json -Compress;exit 2}
        $effect=$false
        try {
          $p=Start-Process -FilePath ([string]$i.path) -Verb PrintTo -ArgumentList ('"'+[string]$i.printer+'"') -PassThru;$effect=$true
          $deadline=(Get-Date).AddSeconds(30)
          # Goal FT/proveedores (revision de recibos): el trabajo nuevo que lleva el nombre del documento; otro trabajo
          # nuevo de esa impresora (de otra app) solo vale al final, y el recibo dice que no lleva su nombre.
          $name=[IO.Path]::GetFileNameWithoutExtension([string]$i.path);$job=$null;$other=$null
          do {Start-Sleep -Milliseconds 500;$new=@(Get-PrintJob -PrinterName ([string]$i.printer) -ErrorAction SilentlyContinue|Where-Object {$before -notcontains $_.ID})
            $job=$new|Where-Object {([string]$_.DocumentName).IndexOf($name,[StringComparison]::OrdinalIgnoreCase) -ge 0}|Select-Object -First 1
            if($null -eq $other){$other=$new|Select-Object -First 1}} while($null -eq $job -and (Get-Date) -lt $deadline)
          $named=($null -ne $job);if(-not $named){$job=$other}
          [pscustomobject]@{ok=($null -ne $job);effectObserved=$effect;documentNamed=$named;jobId=if($job){[string]$job.ID}else{''};status=if($job){[string]$job.JobStatus}else{''}}|ConvertTo-Json -Compress
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
    // Auditoría final (regla 3): a netsh that failed or printed no profile header is a list not read, never an empty one.
    internal const string WifiProfilesScript = """
        $text=@(netsh wlan show profiles);$code=$LASTEXITCODE
        if($code -ne 0 -or -not (($text -join "`n") -match '(?im)^\s*(?:Profiles on interface|Perfiles en la interfaz)')){[pscustomobject]@{ok=$false}|ConvertTo-Json -Compress;exit 0}
        $profiles=@();foreach($line in $text){if($line -match '^\s*(?:All User Profile|Perfil de todos los usuarios)\s*:\s*(.+?)\s*$'){$profiles+=@($Matches[1])}}
        [pscustomobject]@{ok=$true;profiles=$profiles}|ConvertTo-Json -Compress
        """;
    // Auditoría final (regla 3): a netsh that failed or printed no interface header is a status not read, never
    // «disconnected». Renew al máximo (w8): the WLAN service stopped and a computer with no Wi-Fi adapter are said as
    // such (wifi.scan's own codes; the notebook has none: «No hay ninguna interfaz inalámbrica en el sistema»), and
    // any other unread status as wifi_status_not_read, not the adapter's generic failure.
    internal const string WifiStatusScript = """
        $text=@(netsh wlan show interfaces);$code=$LASTEXITCODE;$joined=($text -join "`n")
        if($joined -match '(?i)is not running|no se está ejecutando|no está en ejecución'){[pscustomobject]@{ok=$false;error='wlan_service_not_running'}|ConvertTo-Json -Compress;exit 0}
        if($joined -match '(?i)no hay ninguna interfaz|there is no wireless interface|no wireless interface'){[pscustomobject]@{ok=$false;error='wifi_radio_not_found'}|ConvertTo-Json -Compress;exit 0}
        if($code -ne 0 -or -not ($joined -match '(?i)(?:hay|there (?:is|are))\s+\d+\s+interfa')){[pscustomobject]@{ok=$false;error='wifi_status_not_read'}|ConvertTo-Json -Compress;exit 0}
        $connected=$false;$profile=''
        foreach($line in $text){if($line -match '^\s*(?:State|Estado)\s*:\s*(connected|conectado)\s*$'){$connected=$true};if($line -match '^\s*(?:Profile|Perfil)\s*:\s*(.+?)\s*$'){$profile=$Matches[1]}}
        [pscustomobject]@{ok=$true;connected=$connected;profile=$profile}|ConvertTo-Json -Compress
        """;
    // Encargo H2 (tandas redpc t2-c03, t3-c04, t4-c04: «Intenté poner el brillo…, pero no pude confirmar si se hizo» on
    // a monitor that does not expose its brightness): WMI answers its brightness classes there with «not supported»
    // (CimException NotSupported) or with no instance. That is the computer's limit, read before anything is changed
    // (BrightnessNotSupported, said as the absent device of data «computerUse.limits.devices»), never a change tried.
    internal const string BrightnessNotSupported = "brightness_not_supported";
    private const string BrightnessInstances = """
        function Get-BaxyBrightness([string]$class){try{@(Get-CimInstance -Namespace root/WMI -ClassName $class -ErrorAction Stop)}catch{if([string]$_.Exception.NativeErrorCode -ne 'NotSupported'){throw}}}
        function Write-BaxyBrightnessAbsent{[pscustomobject]@{ok=$false;effectObserved=$false;error='brightness_not_supported'}|ConvertTo-Json -Compress}

        """;
    // Renew al máximo (w5): a set is read back every 100 ms until every monitor shows the level, for 1.5 s at most. One
    // read after a fixed 300 ms called a panel still fading towards it a failure, and made one that got there wait.
    internal const string BrightnessScript = BrightnessInstances + """
        $ErrorActionPreference='Stop';$value=[byte]$args[0];$effect=$false
        try {$methods=@(Get-BaxyBrightness WmiMonitorBrightnessMethods);$current=@(Get-BaxyBrightness WmiMonitorBrightness)
          if($methods.Count -eq 0 -or $current.Count -eq 0){Write-BaxyBrightnessAbsent;exit 2}
          $baseline=@($current|ForEach-Object {[int]$_.CurrentBrightness})
          if($baseline.Count -gt 0 -and @($baseline|Where-Object {$_ -ne $value}).Count -eq 0){
            [pscustomobject]@{ok=$true;effectObserved=$false;changed=$false;baselineValues=$baseline;values=$baseline}|ConvertTo-Json -Compress;exit 0
          }
          foreach($method in $methods){Invoke-CimMethod -InputObject $method -MethodName WmiSetBrightness -Arguments @{Timeout=1;Brightness=$value}|Out-Null};$effect=$true
          $deadline=(Get-Date).AddMilliseconds(1500)
          do{Start-Sleep -Milliseconds 100
            $after=@(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness|ForEach-Object {[int]$_.CurrentBrightness})
            $reached=($after.Count -gt 0 -and @($after|Where-Object {$_ -ne $value}).Count -eq 0)}while(-not $reached -and (Get-Date) -lt $deadline)
          [pscustomobject]@{ok=$reached;effectObserved=$true;changed=$true;baselineValues=$baseline;values=$after}|ConvertTo-Json -Compress
        } catch {[pscustomobject]@{ok=$false;effectObserved=$effect;error='brightness_failed'}|ConvertTo-Json -Compress;exit 2}
        """;
    internal const string BrightnessAdjustScript = BrightnessInstances + """
        $ErrorActionPreference='Stop';$delta=[int]$args[0];$effect=$false
        try {
          $methods=@(Get-BaxyBrightness WmiMonitorBrightnessMethods)
          $current=@(Get-BaxyBrightness WmiMonitorBrightness)
          if($methods.Count -eq 0 -or $current.Count -eq 0){Write-BaxyBrightnessAbsent;exit 2}
          $expected=@{};$baseline=@()
          foreach($item in $current){
            $before=[int]$item.CurrentBrightness;$target=[Math]::Max(0,[Math]::Min(100,$before+$delta))
            $baseline+=@($before);$expected[[string]$item.InstanceName]=$target
            $method=$methods|Where-Object {[string]$_.InstanceName -ceq [string]$item.InstanceName}|Select-Object -First 1
            if($null -eq $method){throw 'brightness_method_not_found'}
            Invoke-CimMethod -InputObject $method -MethodName WmiSetBrightness -Arguments @{Timeout=1;Brightness=[byte]$target}|Out-Null
          }
          $effect=$true;$deadline=(Get-Date).AddMilliseconds(1500)
          do{Start-Sleep -Milliseconds 100
            $after=@(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness)
            $values=@();$ok=$after.Count -eq $current.Count
            foreach($item in $after){$value=[int]$item.CurrentBrightness;$values+=@($value);if(-not $expected.ContainsKey([string]$item.InstanceName) -or $expected[[string]$item.InstanceName] -ne $value){$ok=$false}}
          }while(-not $ok -and (Get-Date) -lt $deadline)
          [pscustomobject]@{ok=$ok;effectObserved=$effect;baselineValues=$baseline;values=$values}|ConvertTo-Json -Compress
        } catch {[pscustomobject]@{ok=$false;effectObserved=$effect;error='brightness_adjust_failed'}|ConvertTo-Json -Compress;exit 2}
        """;
    internal const string BrightnessStatusScript = BrightnessInstances + """
        $ErrorActionPreference='Stop'
        try {
          function Read-BaxyBrightness {
            @(Get-BaxyBrightness WmiMonitorBrightness |
              ForEach-Object {[pscustomobject]@{instanceName=[string]$_.InstanceName;value=[int]$_.CurrentBrightness}} |
              Sort-Object instanceName)
          }
          $first=@(Read-BaxyBrightness)
          if($first.Count -eq 0){Write-BaxyBrightnessAbsent;exit 2}
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
        KeysLease = ForegroundLease.Shared;
    }

    /// <summary>
    /// v3 point 0, fix 3: the quick-switcher script brings Discord's window up and types into it by SendInput, so it
    /// runs in one helper burst of this lease (after the person's pause; the front and the cursor given back after).
    /// Null runs it directly (the test seams, whose runners are fakes).
    /// </summary>
    internal IForegroundLease? KeysLease { get; init; }

    /// <summary>
    /// Renew al máximo (rendimiento): the persistent UI Automation worker the Calculator's script runs in
    /// (<see cref="UiaWorkerScript"/>); null runs it in its own PowerShell, as before (the test seams' fake runners).
    /// </summary>
    internal IUiaWorker? Scripts { get; init; }

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
        or "display.status" or "software.python.status" or "software.python.package.status" or "storage.removable.list" or "client.channel.locate" or "client.microphone.set" or "calculator.expression.evaluate"
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
                "client.microphone.set" => await ClientMicrophoneSetAsync(
                    operation, arguments, effectBoundary, cancellationToken),
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
        catch (WifiStatusUnreadException unread)
        {
            return effectBoundary.Failure(operation, unread.Code);
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
            return IdentityUnknown(operation, "bluetooth_identity_expired", "deviceId", "paired", "bluetooth_device_list");
        BluetoothPairingState item = await ReadPairingAsync(nativeId, cancellationToken).ConfigureAwait(false);
        if (item.IsPaired)
            return ExternalJson.Switched(operation, BluetoothPairResult(id, item.Name), effectObserved: false);
        if (!item.CanPair) return ExternalJson.Failure(operation, "bluetooth_device_cannot_pair");
        effectBoundary.Cross(cancellationToken);
        // Revisión nb-q-apps2: PairAsync waits for the person to answer Windows' pairing dialog, and nobody answering
        // held the turn for good (no deadline, the turn's cancel ignored). The wait is bounded and follows the turn's
        // cancel; past the bound the pairing is not confirmed, and the dialog, if still open, may yet pair the device.
        using var pairing = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        bool paired;
        try
        {
            paired = await BluetoothPairing.PairAsync(nativeId, pairing.Token).AsTask()
                .WaitAsync(BluetoothPairTimeout, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            pairing.Cancel();
            return PairingNotConfirmed(operation, id);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            pairing.Cancel();
            throw;
        }
        cancellationToken.ThrowIfCancellationRequested();
        BluetoothPairingState after = await ReadPairingAsync(nativeId, cancellationToken).ConfigureAwait(false);
        if (!paired || !after.IsPaired)
            return effectBoundary.Failure(operation, "bluetooth_pairing_not_verified", true);
        return ExternalJson.Success(operation, BluetoothPairResult(id, after.Name), true);
    }

    /// <summary>Revisión nb-q-apps2: the device's pairing as Windows reads it (a fake in tests; nothing is paired).</summary>
    internal IBluetoothPairing BluetoothPairing { get; init; } = WindowsBluetoothPairing.Instance;

    /// <summary>Revisión nb-q-apps2: how long a pairing waits for Windows (and the person, if it shows its dialog).</summary>
    internal TimeSpan BluetoothPairTimeout { get; init; } = DefaultBluetoothPairTimeout;

    private static readonly TimeSpan DefaultBluetoothPairTimeout = TimeSpan.FromSeconds(45);

    // A read of the device is bounded as the inventory is (a WinRT call that never answers is a timeout, before any effect).
    private async Task<BluetoothPairingState> ReadPairingAsync(string nativeId, CancellationToken cancellationToken)
    {
        using var reading = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        try
        {
            return await BluetoothPairing.ReadAsync(nativeId, reading.Token).AsTask()
                .WaitAsync(_bluetoothInventoryTimeout, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            reading.Cancel();
            throw;
        }
    }

    private static ExternalCapabilityReceipt PairingNotConfirmed(string operation, string id) =>
        ExternalJson.FailureAfterEffect(operation, "bluetooth_pairing_not_confirmed") with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteString("deviceId", id);
                writer.WriteBoolean("pairingConfirmed", false);
                writer.WriteString("next", "Windows did not confirm the pairing in time (its pairing dialog may be "
                    + "waiting for an answer); if that dialog is still open the device may still pair, and "
                    + "bluetooth_device_list shows whether it is paired");
                writer.WriteEndObject();
            }),
        };

    // Renew al máximo (w5): an id no list of this Core gave (an older session's, or one made up) was a bare «expired»; with
    // the aid identity_relist it says nothing was done and which list gives the ids.
    private static ExternalCapabilityReceipt IdentityUnknown(
        string operation, string code, string argument, string done, string list) =>
        ModelAids.On(ModelAids.IdentityRelist)
            ? new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteString("next", $"this {argument} is not one {list} gave since BAXY started, and nothing was {done}; "
                    + $"{list} gives the ids to use");
                writer.WriteEndObject();
            }), code)
            : ExternalJson.Failure(operation, code);

    private static JsonElement BluetoothPairResult(string id, string name) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteString("deviceId", id);
        writer.WriteString("name", name); writer.WriteBoolean("paired", true);
        writer.WriteString("authority", "windows_device_pairing_postread"); writer.WriteEndObject();
    });

    /// <summary>Renew al máximo (w8): the radios this adapter switches and reads (the WinRT Radio API; a fake in tests).</summary>
    internal IRadioSet Radios { get; init; } = WindowsRadioSet.Instance;

    // Renew al máximo (w8): a switched radio was read once, right after SetStateAsync returned, so one still settling
    // was told «postread failed» though it got there a moment later. The radios are now read every 100 ms until they
    // show the asked state, for 2 s at most, and a failure keeps the last read as stateAfter.
    internal static readonly TimeSpan RadioPollPause = TimeSpan.FromMilliseconds(100);

    internal static readonly TimeSpan RadioPollHorizon = TimeSpan.FromSeconds(2);

    private async ValueTask<(IRadioHandle[] Observed, bool Reached)> ReadRadiosUntilAsync(
        Func<IRadioHandle, bool> kind,
        Func<IRadioHandle[], bool> reached,
        CancellationToken token)
    {
        int polls = (int)(RadioPollHorizon / RadioPollPause);
        var clock = System.Diagnostics.Stopwatch.StartNew();
        for (int poll = 0; ; poll++)
        {
            IRadioHandle[] observed = (await Radios.ListAsync()).Where(kind).ToArray();
            if (reached(observed))
                return (observed, true);
            if (poll >= polls || clock.Elapsed >= RadioPollHorizon)
                return (observed, false);
            await _delay(RadioPollPause, token);
        }
    }

    private static JsonElement RadioStateAfter(IRadioHandle[] observed) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteStartArray("radios");
        foreach (IRadioHandle radio in observed)
        {
            writer.WriteStartObject();
            writer.WriteString("kind", radio.Kind.ToString());
            writer.WriteString("name", radio.Name);
            writer.WriteString("state", radio.State.ToString());
            writer.WriteEndObject();
        }
        writer.WriteEndArray();
        writer.WriteBoolean("requestedStateReached", false);
        writer.WriteString("authority", "windows_radio_api_reread");
        writer.WriteEndObject();
    });

    // NETWORK1737 «qué redes wifi hay» → «sí, prendelo»: the Wi-Fi radio is
    // switched through the same official Radio API as Bluetooth, with the
    // person's confirmation, and the state is read back; a read-only status
    // answers «¿el wifi está prendido?» without touching it.
    private async ValueTask<ExternalCapabilityReceipt> WifiRadioSetAsync(
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
        RadioAccessStatus access = await Radios.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
        {
            return ExternalJson.Failure(operation, "wifi_radio_access_denied");
        }
        IRadioHandle[] radios = (await Radios.ListAsync())
            .Where(radio => radio.Kind == RadioKind.WiFi)
            .ToArray();
        if (radios.Length == 0)
        {
            return ExternalJson.Failure(operation, "wifi_radio_not_found");
        }
        RadioState desired = requested ? RadioState.On : RadioState.Off;
        // FT/proveedores goal (review of receipts): a radio disabled by its switch or driver (RadioState.Disabled) is
        // off: turning it off changes nothing and is not told «may have happened»; turning on radios that are all
        // disabled is said before anything is touched.
        bool Reached(IRadioHandle radio) => radio.State == desired || (!requested && radio.State == RadioState.Disabled);
        if (requested && radios.All(radio => radio.State == RadioState.Disabled))
        {
            return ExternalJson.FailureBeforeEffect(operation, "wifi_radio_disabled");
        }
        bool effectObserved = false;
        foreach (IRadioHandle radio in radios)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (Reached(radio))
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
        (IRadioHandle[] observed, bool reached) = await ReadRadiosUntilAsync(
            radio => radio.Kind == RadioKind.WiFi, read => read.Length > 0 && read.All(Reached), cancellationToken);
        if (!reached)
        {
            return ExternalJson.WithStateAfter(
                effectBoundary.Failure(operation, "wifi_radio_postread_failed", effectObserved), RadioStateAfter(observed));
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
        return ExternalJson.Switched(operation, result, effectObserved);
    }

    // REOPEN1957 H0107 «poneme el modo avión»: el modo avión de Windows es todas
    // las radios apagadas. La API de radios apaga y enciende cada una y la
    // postlectura las vuelve a leer; la lectura de estado dice si están todas
    // apagadas. Un driver que restaure enciende las que estaban encendidas.
    private static readonly RadioKind[] AirplaneRadioKinds = [RadioKind.WiFi, RadioKind.Bluetooth, RadioKind.MobileBroadband];

    private async ValueTask<ExternalCapabilityReceipt> AirplaneModeSetAsync(
        string operation,
        int value,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (value is not (0 or 1))
            return ExternalJson.FailureBeforeEffect(operation, "airplane_mode_value_invalid");
        RadioAccessStatus access = await Radios.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
            return ExternalJson.FailureBeforeEffect(operation, "airplane_mode_radio_access_denied");
        IRadioHandle[] radios = (await Radios.ListAsync())
            .Where(radio => AirplaneRadioKinds.Contains(radio.Kind))
            .ToArray();
        if (radios.Length == 0)
            return ExternalJson.FailureBeforeEffect(operation, "airplane_mode_radios_not_found");
        RadioState desired = value == 1 ? RadioState.Off : RadioState.On;
        // Ronda final 20: two radios of the same name and kind leave «wasOn» unsaid for them (never an exception).
        var before = radios.GroupBy(radio => radio.Name + "|" + radio.Kind)
            .ToDictionary(group => group.Key, group => group.Count() == 1 ? group.First().State == RadioState.On : (bool?)null);
        // AIRPLANE2043 «sacá el modo avión» with every radio already on: nothing to
        // switch cannot be observed as an effect; the honest fact is the state,
        // said before any boundary is crossed (same contract as the microphone).
        // A disabled radio is off for the airplane mode (bool allOff below), and stays out of the switching.
        if (radios.All(radio => radio.State == desired || radio.State == RadioState.Disabled))
        {
            return ExternalJson.FailureBeforeEffect(
                operation, value == 1 ? "airplane_radios_already_all_off" : "airplane_radios_already_on");
        }
        bool effectObserved = false;
        foreach (IRadioHandle radio in radios)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (radio.State == desired || radio.State == RadioState.Disabled)
                continue;
            effectBoundary.Cross(cancellationToken);
            RadioAccessStatus changed = await radio.SetStateAsync(desired);
            effectObserved = true;
            if (changed != RadioAccessStatus.Allowed)
                return effectBoundary.Failure(operation, "airplane_mode_change_rejected", effectObserved);
        }

        (IRadioHandle[] observed, bool reached) = await ReadRadiosUntilAsync(
            radio => AirplaneRadioKinds.Contains(radio.Kind),
            read => read.Length > 0 && (value == 1
                ? read.All(radio => radio.State != RadioState.On)
                : read.All(radio => radio.State is RadioState.On or RadioState.Disabled)),
            cancellationToken);
        bool allOff = observed.All(radio => radio.State != RadioState.On);
        if (!reached)
        {
            return ExternalJson.WithStateAfter(
                effectBoundary.Failure(operation, "airplane_mode_postread_failed", effectObserved),
                RadioStateAfter(observed));
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", "airplane_mode");
            writer.WriteNumber("value", value);
            // Auditoría final (regla 3): what is read is every radio's state, not Windows' own airplane switch.
            writer.WriteBoolean("allRadiosOff", allOff);
            writer.WriteBoolean("changed", effectObserved);
            writer.WriteStartArray("radios");
            foreach (IRadioHandle radio in observed)
            {
                writer.WriteStartObject();
                writer.WriteString("kind", radio.Kind.ToString());
                writer.WriteString("name", radio.Name);
                writer.WriteString("state", radio.State.ToString());
                if (before.GetValueOrDefault(radio.Name + "|" + radio.Kind) is bool wasOn)
                    writer.WriteBoolean("wasOn", wasOn);
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            writer.WriteString("authority", "windows_radio_api_all_radios_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved);
    }

    private async ValueTask<ExternalCapabilityReceipt> AirplaneModeStatusAsync(string operation)
    {
        RadioAccessStatus access = await Radios.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
            return ExternalJson.Failure(operation, "airplane_mode_radio_access_denied");
        IRadioHandle[] radios = (await Radios.ListAsync())
            .Where(radio => AirplaneRadioKinds.Contains(radio.Kind))
            .ToArray();
        if (radios.Length == 0)
            return ExternalJson.Failure(operation, "airplane_mode_radios_not_found");
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", "airplane_mode");
            writer.WriteBoolean("allRadiosOff", radios.All(radio => radio.State != RadioState.On));
            writer.WriteNumber("radioCount", radios.Length);
            writer.WriteStartArray("radios");
            foreach (IRadioHandle radio in radios)
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

    private async ValueTask<ExternalCapabilityReceipt> WifiRadioStatusAsync(string operation)
    {
        RadioAccessStatus access = await Radios.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
        {
            return ExternalJson.Failure(operation, "wifi_radio_access_denied");
        }
        IRadioHandle[] radios = (await Radios.ListAsync())
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

    private async ValueTask<ExternalCapabilityReceipt> BluetoothRadioSetAsync(
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
        RadioAccessStatus access = await Radios.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
        {
            return ExternalJson.Failure(operation, "bluetooth_radio_access_denied");
        }
        IRadioHandle[] radios = (await Radios.ListAsync())
            .Where(radio => radio.Kind == RadioKind.Bluetooth)
            .ToArray();
        if (radios.Length == 0)
        {
            return ExternalJson.Failure(operation, "bluetooth_radio_not_found");
        }
        RadioState desired = requested ? RadioState.On : RadioState.Off;
        // FT/proveedores goal (review of receipts): a radio disabled by its switch or driver (RadioState.Disabled) is
        // off: turning it off changes nothing and is not told «may have happened»; turning on radios that are all
        // disabled is said before anything is touched.
        bool Reached(IRadioHandle radio) => radio.State == desired || (!requested && radio.State == RadioState.Disabled);
        if (requested && radios.All(radio => radio.State == RadioState.Disabled))
        {
            return ExternalJson.FailureBeforeEffect(operation, "bluetooth_radio_disabled");
        }
        bool effectObserved = false;
        foreach (IRadioHandle radio in radios)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (Reached(radio))
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
        (IRadioHandle[] observed, bool reached) = await ReadRadiosUntilAsync(
            radio => radio.Kind == RadioKind.Bluetooth, read => read.Length > 0 && read.All(Reached), cancellationToken);
        if (!reached)
        {
            return ExternalJson.WithStateAfter(
                effectBoundary.Failure(operation, "bluetooth_radio_postread_failed", effectObserved),
                RadioStateAfter(observed));
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
        return ExternalJson.Switched(operation, result, effectObserved);
    }

    // NETWORK1457 «tengo el bluetooth encendido», «y el bluetooth?»: the radio
    // state was only observable as the post-read of a change; a read-only
    // read answers the question without touching the radio.
    private async ValueTask<ExternalCapabilityReceipt> BluetoothRadioStatusAsync(string operation)
    {
        RadioAccessStatus access = await Radios.RequestAccessAsync();
        if (access != RadioAccessStatus.Allowed)
        {
            return ExternalJson.Failure(operation, "bluetooth_radio_access_denied");
        }
        IRadioHandle[] radios = (await Radios.ListAsync())
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
    // UI1725 «multiplicá 6 por 7 en la calc»: the expression is pressed on the keypad of the Windows Calculator that is
    // already open (KeypadFunctions, below) and the display is read back through UI Automation (CalculatorResults /
    // CalculatorExpression).
    // Review of fable/cu-v3-pausa: SendKeys.SendWait cannot carry BAXY's input mark (BaxyInputMark.cs), so the pause
    // detector took these keys for the person's and the harness could not tell them from the person's. The quick
    // switcher's keys go with SendInput, marked, mapped through the keyboard layout (VkKeyScan) as SendKeys did; a
    // character the layout cannot type goes as a Unicode key. C# 5: the script runs in Windows PowerShell 5.1.
    private const string MarkedKeysType = """
        $markedKeys='using System;using System.Collections.Generic;using System.Runtime.InteropServices;public static class BaxyMarkedKeys{[StructLayout(LayoutKind.Sequential)] struct KeyboardInput{public ushort Vk;public ushort Scan;public uint Flags;public uint Time;public UIntPtr Extra;}[StructLayout(LayoutKind.Sequential)] struct MouseInput{public int X;public int Y;public uint Data;public uint Flags;public uint Time;public UIntPtr Extra;}[StructLayout(LayoutKind.Explicit)] struct InputUnion{[FieldOffset(0)] public MouseInput Mouse;[FieldOffset(0)] public KeyboardInput Keyboard;}[StructLayout(LayoutKind.Sequential)] struct Input{public uint Type;public InputUnion Data;}[DllImport("user32.dll",SetLastError=true)] static extern uint SendInput(uint count,Input[] inputs,int size);[DllImport("user32.dll")] static extern short VkKeyScanW(char ch);static readonly UIntPtr Mark=new UIntPtr(0x42415859u);static Input Key(ushort vk,ushort scan,uint flags){Input input=new Input();input.Type=1;input.Data.Keyboard.Vk=vk;input.Data.Keyboard.Scan=scan;input.Data.Keyboard.Flags=flags;input.Data.Keyboard.Extra=Mark;return input;}static uint Send(List<Input> inputs){return SendInput((uint)inputs.Count,inputs.ToArray(),Marshal.SizeOf(typeof(Input)));}static uint Chord(ushort vk,int modifiers){List<Input> inputs=new List<Input>();ushort[] keys={0x10,0x11,0x12};for(int bit=0;bit<3;bit++){if((modifiers&(1<<bit))!=0)inputs.Add(Key(keys[bit],0,0));}inputs.Add(Key(vk,0,0));inputs.Add(Key(vk,0,2));for(int bit=2;bit>=0;bit--){if((modifiers&(1<<bit))!=0)inputs.Add(Key(keys[bit],0,2));}return Send(inputs);}public static uint Press(ushort vk,bool control){return Chord(vk,control?2:0);}public static uint Character(char ch,bool control){short scan=VkKeyScanW(ch);if(scan==-1){List<Input> unicode=new List<Input>();unicode.Add(Key(0,ch,4));unicode.Add(Key(0,ch,6));return Send(unicode);}return Chord((ushort)(scan&0xFF),((scan>>8)&0x7)|(control?2:0));}public static uint Text(string text){uint sent=0;foreach(char ch in text){sent+=Character(ch,false);}return sent;}}'
        if(-not ([System.Management.Automation.PSTypeName]'BaxyMarkedKeys').Type){Add-Type -TypeDefinition $markedKeys}

        """;

    // Regresiones r2 M4 and molestia r2 (rama B, punto 2): the keys sent with SendInput needed the Calculator in front
    // (a burst that took the person's front) and were counted as BAXY's keystrokes. The expression is now pressed on
    // the keypad's own buttons by UI Automation's Invoke: each character is the button the keypad data names
    // (src/baxy_mind/data/keypad_keys.v1.json, embedded; Spanish and English, compared folded), no window is brought up
    // and no key is sent. The result is verified on the display: a number read there, and the expression shown ending
    // with the last operand pressed (Standard mode folds the earlier ones into a running result). Review r4: the clear
    // button is required and the display must read 0 after it (polled up to 300 ms), and without the expression line
    // only a number other than 0 proves the presses: a keypad that ignored them would show the previous result.
    internal const string KeypadFunctions = """
        function Get-KeyFolded([string]$text){
          if([string]::IsNullOrEmpty($text)){ return '' }
          $decomposed=$text.Normalize([Text.NormalizationForm]::FormD);$kept=New-Object Text.StringBuilder
          foreach($c in $decomposed.ToCharArray()){ if([Globalization.CharUnicodeInfo]::GetUnicodeCategory($c) -ne [Globalization.UnicodeCategory]::NonSpacingMark){ [void]$kept.Append($c) } }
          return (($kept.ToString().ToLowerInvariant()) -replace '\s+',' ').Trim()
        }
        # Holdout v5 V5E029: a button is also found by its AutomationId ($ids, in the same order as $names), the same in
        # every language (the Scientific keypad's xʸ and parentheses).
        function Find-KeypadButton([string[]]$names,$wanted,[string[]]$ids=@()){
          $folded=@($wanted | ForEach-Object { Get-KeyFolded ([string]$_) })
          for($i=0;$i -lt $names.Count;$i++){ if($folded -contains (Get-KeyFolded $names[$i]) -or ($i -lt $ids.Count -and $folded -contains (Get-KeyFolded $ids[$i]))){ return $i } }
          return -1
        }
        function Select-KeypadPresses([string]$keys,[string[]]$names,$map,[string[]]$ids=@()){
          $plan=New-Object System.Collections.Generic.List[int]
          foreach($ch in $keys.ToCharArray()){
            $at=Find-KeypadButton $names @($map.keys.([string]$ch)) $ids
            if($at -lt 0){ return $null }
            $plan.Add($at)
          }
          return ,$plan.ToArray()
        }
        # Holdout v5 V5E029: the keypad's mode, from its buttons' AutomationIds: the Standard one has no parenthesis, only
        # the Scientific one has π; any other (Programmer) is «other».
        function Get-KeypadMode([string[]]$ids){
          if($ids -notcontains 'openParenthesisButton'){ return 'standard' }
          if($ids -contains 'piButton'){ return 'scientific' }
          return 'other'
        }
        # Ronda final 27 (regla 3) and holdout v5 V5E029: Standard applies each operator in the order typed, Scientific
        # follows precedence and has ^ and parentheses. Another keypad presses nothing, nor does an expression that needs
        # the Scientific buttons on the Standard one: the mode is never switched here.
        function Get-ModeRefusal([string]$mode,[string]$keys){
          if($mode -eq 'other'){ return 'calculator_mode_not_supported' }
          if($mode -ne 'scientific' -and $keys -match '[\^()]'){ return 'calculator_needs_scientific_mode' }
          return ''
        }
        # Holdout v5 V5E021 («a lo que tiene la calculadora súmale 53»): an expression that starts with an operator
        # continues from the number the display shows; any other clears the display first.
        function Test-ContinuesDisplay([string]$keys){ return ($keys -match '^[-+*/^]') }
        function Test-ShowsZero([string]$value){ return ($value.Trim() -match '^-?0(?:[.,]0*)?$') }
        function Test-ShowsLastOperand([string]$shown,[string]$value,[string]$keys,$start=$null){
          if($value -notmatch '^-?\d'){ return $false }
          if($null -eq $start){ $start=@{expr='';value='0'} }
          # Holdout v5 V5E021: the display read before the presses (the 0 the clear left, or the number a continued
          # expression starts from) shown again unchanged is no proof that they were pressed.
          if($shown -eq [string]$start.expr -and $value -eq [string]$start.value){ return $false }
          if($shown.Trim().Length -eq 0){
            # Without the expression line the display is the only proof. After the clear button it showed 0: only a
            # number other than 0 says the buttons were pressed (a result of 0 is not told from a keypad that ignored them).
            return (-not (Test-ShowsZero ([string]$start.value))) -or -not (Test-ShowsZero $value)
          }
          # The last number typed, before any closing parenthesis.
          $last=([regex]::Match($keys,'(\d+(?:\.\d+)?)[^0-9]*$').Groups[1].Value -replace '[^0-9]','')
          $digits=($shown -replace '[^0-9]','')
          return ($last.Length -gt 0 -and $digits.EndsWith($last))
        }
        # Renew al máximo (rendimiento): the display after the last press was read once, after a fixed 300 ms. It is now
        # read every 50 ms within the same 300 ms and taken as soon as it shows the expression's last operand
        # (Test-ShowsLastOperand) twice in a row unchanged; otherwise the read at 300 ms is taken, as before, and the
        # caller's check decides on it. The budget runs on $elapsed (milliseconds since the first read) and the pauses on
        # $sleep: the wall clock and Start-Sleep unless given.
        function Wait-ShownResult([scriptblock]$read,[string]$keys,[int]$budget,[int]$interval,$start=$null,[scriptblock]$elapsed=$null,[scriptblock]$sleep=$null){
          $clock=[Diagnostics.Stopwatch]::StartNew();$last=$null
          if($null -eq $elapsed){ $elapsed={ $clock.ElapsedMilliseconds } }
          if($null -eq $sleep){ $sleep={ param($ms) Start-Sleep -Milliseconds $ms } }
          while($true){
            $now=& $read
            if($null -ne $last -and $now.name -eq $last.name -and $now.expr -eq $last.expr -and $now.value -eq $last.value -and (Test-ShowsLastOperand $now.expr $now.value $keys $start)){ return $now }
            $left=$budget-(& $elapsed)
            if($left -le 0){ return $now }
            $last=$now
            & $sleep ([Math]::Max(1,[Math]::Min($interval,$left)))
          }
        }

        """;

    internal const string CalculatorScript = """
        $ErrorActionPreference='Stop';$expr=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))
        $map=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[1])) | ConvertFrom-Json)
        Add-Type -AssemblyName UIAutomationClient;Add-Type -AssemblyName UIAutomationTypes

        """ + KeypadFunctions + """
        $root=[System.Windows.Automation.AutomationElement]::RootElement
        $cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'ApplicationFrameWindow')
        $calc=$null;foreach($f in $root.FindAll([System.Windows.Automation.TreeScope]::Children,$cond)){foreach($c in $f.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)){$p=Get-Process -Id $c.Current.ProcessId -ErrorAction SilentlyContinue;if($p -and [string]$p.Path -like '*\WindowsApps\Microsoft.WindowsCalculator_*'){$calc=$f;break}};if($calc){break}}
        if($null -eq $calc){[pscustomobject]@{ok=$false;error='calculator_window_not_found'}|ConvertTo-Json -Compress;exit 2}
        $keys=($expr -replace '[^0-9+\-*/.^()]','')
        if($keys.Length -eq 0){[pscustomobject]@{ok=$false;error='calculator_expression_invalid'}|ConvertTo-Json -Compress;exit 4}
        $buttonCond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Button)
        function Read-Keypad(){ $found=@($calc.FindAll([System.Windows.Automation.TreeScope]::Descendants,$buttonCond)); return @{buttons=$found;names=[string[]]@($found | ForEach-Object { [string]$_.Current.Name });ids=[string[]]@($found | ForEach-Object { [string]$_.Current.AutomationId })} }
        $keypad=Read-Keypad;$buttons=$keypad.buttons;$names=$keypad.names;$ids=$keypad.ids
        $mode=Get-KeypadMode $ids
        $refusal=Get-ModeRefusal $mode $keys
        if($refusal){[pscustomobject]@{ok=$false;error=$refusal;mode=$mode}|ConvertTo-Json -Compress;exit 9}
        $plan=Select-KeypadPresses ($keys+'=') $names $map $ids
        if($null -eq $plan){[pscustomobject]@{ok=$false;error='calculator_button_not_found'}|ConvertTo-Json -Compress;exit 6}
        function Invoke-KeypadButton($element){ $pattern=$null; if($element.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){ ([System.Windows.Automation.InvokePattern]$pattern).Invoke(); return $true }; return $false }
        # The clear button is required, and the display must show 0 after it: a keypad that ignored the presses (the window
        # suspended or minimized) would otherwise leave the previous result there, read as this expression's. Holdout v5
        # V5E029: the Scientific keypad shows «C» only while its entry is empty and «CE» in its place otherwise.
        $continued=Test-ContinuesDisplay $keys
        $clear=Find-KeypadButton $names @($map.clear) $ids
        $entry=Find-KeypadButton $names @($map.clearEntry) $ids
        if(-not $continued -and $clear -lt 0 -and $entry -lt 0){[pscustomobject]@{ok=$false;error='calculator_button_not_found'}|ConvertTo-Json -Compress;exit 6}
        $idCond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'CalculatorResults')
        $display=$calc.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$idCond)
        if($null -eq $display){[pscustomobject]@{ok=$false;error='calculator_display_not_read'}|ConvertTo-Json -Compress;exit 5}
        function Read-DisplayValue(){ return (([string]$display.Current.Name) -replace '^[^0-9\-]*','').Trim() }
        $exprCond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'CalculatorExpression')
        $read={ $shown=$calc.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$exprCond); @{name=[string]$display.Current.Name;expr=$(if($shown){[string]$shown.Current.Name}else{''});value=(Read-DisplayValue)} }
        $before=& $read
        if($continued){
          # Holdout v5 V5E021: nothing is cleared; the number shown is where the expression continues from.
          if($before.value -notmatch '^-?\d'){[pscustomobject]@{ok=$false;error='calculator_display_not_a_number';displayName=$before.name}|ConvertTo-Json -Compress;exit 10}
        } else {
          $clearButton=$null
          if($clear -lt 0){
            # CE empties the entry and brings «C» back, which is pressed next.
            if(-not (Invoke-KeypadButton $buttons[$entry])){[pscustomobject]@{ok=$false;error='calculator_button_not_invokable';pressed=0}|ConvertTo-Json -Compress;exit 7}
            for($waited=0;$null -eq $clearButton -and $waited -lt 300;$waited+=40){ Start-Sleep -Milliseconds 40; $now=Read-Keypad; $at=Find-KeypadButton $now.names @($map.clear) $now.ids; if($at -ge 0){ $clearButton=$now.buttons[$at] } }
            if($null -eq $clearButton){[pscustomobject]@{ok=$false;error='calculator_display_not_verified';pressed=1}|ConvertTo-Json -Compress;exit 8}
          } else { $clearButton=$buttons[$clear] }
          if(-not (Invoke-KeypadButton $clearButton)){[pscustomobject]@{ok=$false;error='calculator_button_not_invokable';pressed=0}|ConvertTo-Json -Compress;exit 7}
          $cleared=Read-DisplayValue
          for($waited=0;-not (Test-ShowsZero $cleared) -and $waited -lt 300;$waited+=40){ Start-Sleep -Milliseconds 40; $cleared=Read-DisplayValue }
          if(-not (Test-ShowsZero $cleared)){[pscustomobject]@{ok=$false;error='calculator_display_not_verified';clearedDisplay=$cleared}|ConvertTo-Json -Compress;exit 8}
        }
        $start=& $read
        $pressed=0
        foreach($at in $plan){ if(-not (Invoke-KeypadButton $buttons[$at])){[pscustomobject]@{ok=$false;error='calculator_button_not_invokable';pressed=$pressed}|ConvertTo-Json -Compress;exit 7}; $pressed++; Start-Sleep -Milliseconds 30 }
        $settled=Wait-ShownResult $read $keys 300 50 $start
        $name=$settled.name;$exprName=$settled.expr;$value=$settled.value
        if(-not (Test-ShowsLastOperand $exprName $value $keys $start)){[pscustomobject]@{ok=$false;error='calculator_display_not_verified';displayName=$name;expressionName=$exprName}|ConvertTo-Json -Compress;exit 8}
        # What the display showed before: the number a continued expression started from, or what the clear removed.
        $was=$(if($before.value -match '^-?\d'){$before.value}else{$before.name})
        [pscustomobject]@{ok=$true;typed=$keys;method='invoke';pressed=$pressed;displayName=$name;expressionName=$exprName;value=$value;mode=$mode;continued=[bool]$continued;before=$was}|ConvertTo-Json -Compress
        """;

    // The keypad's buttons by the characters they press (src/baxy_mind/data/keypad_keys.v1.json, embedded).
    private static readonly Lazy<string> KeypadKeys = new(() =>
    {
        using Stream stream = typeof(WindowsDeviceControlAdapter).Assembly.GetManifestResourceStream("Baxy.Providers.Windows.KeypadKeys.json")
            ?? throw new InvalidOperationException("keypad_keys_missing");
        using var reader = new StreamReader(stream, System.Text.Encoding.UTF8);
        return reader.ReadToEnd();
    });

    // What a calculator.expression.evaluate without the Calculator's window saw: a fact and an option, not an order.
    private static readonly JsonElement CalculatorNotOpen = ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteString("next", "no Calculator window is open and nothing was pressed; app_open can start the "
            + "Calculator, then this expression can be evaluated again");
        writer.WriteEndObject();
    });

    // Holdout v5 V5E021/V5E029: numbers joined by + - * / ^, each inside any parentheses opened before it and closed
    // after it (balancing groups: every «(» closed by the end); an operator first continues from the number shown.
    // Whether the keypad has ^ and the parentheses is the script's to read (only the Scientific one has them).
    private static readonly Regex CalculatorExpression = new(
        @"^[-+*/^]?(?<open>\()*\d{1,12}(?:\.\d{1,6})?(?<-open>\))*(?:[-+*/^](?<open>\()*\d{1,12}(?:\.\d{1,6})?(?<-open>\))*)*(?(open)(?!))$",
        RegexOptions.CultureInvariant);

    private const string CalculatorCharacters = "0123456789+-*/^().,";

    private static readonly Regex NumberSplit = new(@"[\d.,]\s+[\d.,]", RegexOptions.CultureInvariant);

    // What calculator_expression_invalid tells the model it accepts: a fact, nothing pressed.
    private const string CalculatorAccepted = "numbers with a decimal point or comma, joined by + - * / ^, with ( ) around "
        + "parts; ^ and ( ) only in Scientific mode; an operator first continues from the number shown";

    /// <summary>
    /// The keys an expression presses (a decimal comma is the «.» the keypad presses, spaces dropped), or null when it
    /// is not one: <paramref name="refused"/> then holds the characters that are not accepted (none when only its shape
    /// is wrong).
    /// </summary>
    internal static string? CalculatorKeys(string expression, out string refused)
    {
        refused = string.Concat(expression
            .Where(character => !char.IsWhiteSpace(character) && !CalculatorCharacters.Contains(character))
            .Distinct());
        string keys = string.Concat(expression.Where(character => !char.IsWhiteSpace(character))).Replace(',', '.');
        int operators = keys.Count(character => "+-*/^".Contains(character));
        // A space is dropped between the parts, never inside a number («1 2+3» is not 12+3).
        return refused.Length == 0 && operators is >= 1 and <= 8 && !NumberSplit.IsMatch(expression)
            && CalculatorExpression.IsMatch(keys) ? keys : null;
    }

    private async ValueTask<ExternalCapabilityReceipt> CalculatorEvaluateAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        string expression = ExternalJson.RequiredString(arguments, "expression");
        if (CalculatorKeys(expression, out string refused) is not { } normalized)
        {
            JsonElement observed = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                if (refused.Length > 0)
                {
                    writer.WriteString("refused", refused);
                }
                writer.WriteString("accepted", CalculatorAccepted);
                writer.WriteEndObject();
            });
            return new ExternalCapabilityReceipt(operation, false, false, observed, "calculator_expression_invalid");
        }
        // Review r4: the buttons are pressed by UI Automation's Invoke, which sends no key, moves no pointer and takes
        // no front, so the person's keyboard and mouse are never shared: no burst is asked for, the person's pause is
        // not waited for, and their typing in their own window does not stop the expression half pressed (v3 point 0:
        // waiting for the pause is only for an act that has no other way than real input).
        effectBoundary.Cross(token);
        // Renew al máximo (rendimiento): with the product's UI Automation worker the script runs there, already
        // loaded, not in a PowerShell started cold for it (the same script, arguments and budget).
        ExternalProcessResult process = Scripts is { } worker
            ? await UiaWorkerScript.RunAsync(
                worker, CalculatorScript, [Encode(normalized), Encode(KeypadKeys.Value)], TimeSpan.FromSeconds(60), token)
                .ConfigureAwait(false)
            : await RunPowerShellAsync(
                CalculatorScript, [Encode(normalized), Encode(KeypadKeys.Value)], token).ConfigureAwait(false);

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
            // E011 (pc-ayudas): with no Calculator window nothing was pressed; the failure says what was seen and what
            // the model may do about it (start it with app_open), and the model still chooses.
            if (code == "calculator_window_not_found" && ModelAids.On(ModelAids.CalculatorNext))
            {
                return new ExternalCapabilityReceipt(operation, false, false, CalculatorNotOpen, code);
            }
            // A button pressed before the failure (or a display that did not show the expression) may have changed the
            // Calculator; a keypad without the buttons pressed nothing.
            return ExternalJson.Failure(operation, code,
                code is "calculator_display_not_read" or "calculator_display_not_verified" or "calculator_button_not_invokable");
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
            // Holdout v5 V5E021/V5E029: the mode it was pressed in, and what the display showed before: the number a
            // continued expression started from, or what the clear removed (read, never assumed).
            if (root.TryGetProperty("mode", out JsonElement mode) && mode.ValueKind == JsonValueKind.String)
            {
                writer.WriteString("mode", mode.GetString());
            }
            if (root.TryGetProperty("before", out JsonElement before) && before.ValueKind == JsonValueKind.String)
            {
                writer.WriteString(Bool(root, "continued") ? "startedFrom" : "clearedDisplay", before.GetString());
            }
            writer.WriteString("shownExpression", root.TryGetProperty("expressionName", out JsonElement shown) && shown.ValueKind == JsonValueKind.String ? shown.GetString() ?? string.Empty : string.Empty);
            writer.WriteString("display", root.TryGetProperty("displayName", out JsonElement display) && display.ValueKind == JsonValueKind.String ? display.GetString() ?? string.Empty : string.Empty);
            writer.WriteString("value", value);
            writer.WriteString("authority", "windows_calculator_uia_display");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    // Auditoría final (regla 3): only the PEP 514 registry is read, so the count is of registered Pythons, and a key
    // that could not be read makes the read incomplete, never a Python fewer.
    private static List<(string Company, string Tag, string Version, string DisplayName, string? Executable, string Scope)> EnumerateRegisteredPythons(out bool registryReadIncomplete)
    {
        registryReadIncomplete = false;
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
                    registryReadIncomplete = true;
                }
            }
        }
        installs.Sort((left, right) => string.CompareOrdinal(right.Version, left.Version));
        return installs;
    }

    private static ExternalCapabilityReceipt PythonStatus(string operation)
    {
        List<(string Company, string Tag, string Version, string DisplayName, string? Executable, string Scope)> installs = EnumerateRegisteredPythons(out bool registryReadIncomplete);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("registeredPythonCount", installs.Count);
            if (registryReadIncomplete) writer.WriteBoolean("registryReadIncomplete", true);
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
        List<(string Company, string Tag, string Version, string DisplayName, string? Executable, string Scope)> installs = EnumerateRegisteredPythons(out bool registryReadIncomplete);
        // Auditoría final (regla 3): pip and the package are said only as pip answered; a run that failed, or no
        // executable, leaves both unread (null, omitted), never «not installed».
        var rows = new List<(string DisplayName, string Version, bool? PipAvailable, bool? Installed, string? PackageVersion)>();
        foreach ((string _, string _, string version, string displayName, string? executable, string _) in installs)
        {
            if (executable is null)
            {
                rows.Add((displayName, version, null, null, null));
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
            Match name = Regex.Match(output, @"(?im)^Name:\s*(\S+)\s*$");
            Match packageVersion = Regex.Match(output, @"(?im)^Version:\s*(\S+)\s*$");
            bool shown = exit == 0 && name.Success
                && string.Equals(NormalizePythonPackage(name.Groups[1].Value), NormalizePythonPackage(package), StringComparison.Ordinal);
            bool notFound = exit == 1 && output.Contains("Package(s) not found", StringComparison.OrdinalIgnoreCase);
            bool? pipAvailable = output.Contains("No module named pip", StringComparison.OrdinalIgnoreCase)
                ? false
                : shown || notFound ? true : null;
            bool? installed = shown ? true : notFound ? false : null;
            rows.Add((displayName, version, pipAvailable, installed, shown && packageVersion.Success ? packageVersion.Groups[1].Value : null));
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("package", package);
            writer.WriteNumber("registeredPythonCount", rows.Count);
            if (registryReadIncomplete) writer.WriteBoolean("registryReadIncomplete", true);
            writer.WriteNumber("installedCount", rows.Count(row => row.Installed == true));
            writer.WriteNumber("unreadCount", rows.Count(row => row.Installed is null));
            writer.WriteStartArray("pythons");
            foreach ((string displayName, string version, bool? pipAvailable, bool? installed, string? packageVersion) in rows)
            {
                writer.WriteStartObject();
                writer.WriteString("displayName", displayName);
                writer.WriteString("pythonVersion", version);
                if (pipAvailable is bool pip) writer.WriteBoolean("pipAvailable", pip);
                if (installed is bool seen) writer.WriteBoolean("installed", seen);
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
        // Auditoría final (regla 3): a removable drive that is there but not ready (locked by BitLocker, RAW, still
        // mounting) or whose read failed is counted and named by its letter, never left out of «the drives».
        var drives = new List<(string Letter, string Label, string Format, double FreeGiB, double TotalGiB)>();
        var notRead = new List<string>();
        foreach (DriveInfo drive in DriveInfo.GetDrives())
        {
            try
            {
                if (drive.DriveType != DriveType.Removable)
                {
                    continue;
                }
                if (!drive.IsReady)
                {
                    notRead.Add(drive.Name.TrimEnd('\\', '/'));
                    continue;
                }
                string letter = drive.Name.TrimEnd('\\', '/');
                double free = Math.Round(drive.AvailableFreeSpace / 1073741824d, 1);
                double total = Math.Round(drive.TotalSize / 1073741824d, 1);
                drives.Add((letter, drive.VolumeLabel ?? string.Empty, drive.DriveFormat ?? string.Empty, free, total));
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                notRead.Add(drive.Name.TrimEnd('\\', '/'));
            }
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("driveCount", drives.Count);
            if (notRead.Count > 0)
            {
                writer.WriteStartArray("presentNotReadable");
                foreach (string letter in notRead)
                    writer.WriteStringValue(letter);
                writer.WriteEndArray();
            }
            writer.WriteStartArray("drives");
            foreach ((string letter, string label, string format, double free, double total) in drives)
            {
                writer.WriteStartObject();
                writer.WriteString("letter", letter);
                writer.WriteString("label", label);
                writer.WriteString("format", format);
                writer.WriteNumber("freeGiB", free);
                writer.WriteNumber("totalGiB", total);
                // Holdout v4 (falsedad, units): the sizes written with their unit (ReadingUnits).
                writer.WriteString("free", Infrastructure.ReadingUnits.Size(free * 1024d * 1024d * 1024d));
                writer.WriteString("total", Infrastructure.ReadingUnits.Size(total * 1024d * 1024d * 1024d));
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
    // BAXY Renew cu (C14): Discord's own mute button («Silenciar» / «Mute», a toggle: On is muted), found in its window by
    // UI Automation (Chromium builds its tree on the first query, so it is asked again for a short while), switched only
    // when it is not as asked, and read back. Nothing else is pressed; the window is not raised.
    private const string ClientMicrophoneScript = """
        $ErrorActionPreference='Stop';$desired=[int]$args[0];$effect=$false
        try {
          Add-Type -AssemblyName UIAutomationClient
          $windows=@(Get-Process -Name Discord -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
          if($windows.Count -eq 0){[pscustomobject]@{ok=$false;effectObserved=$false;error='client_window_not_found'}|ConvertTo-Json -Compress;exit 0}
          $root=[System.Windows.Automation.AutomationElement]::FromHandle($windows[0].MainWindowHandle)
          $buttons=New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Button)
          $mute=$null
          for($attempt=0;$attempt -lt 12 -and $null -eq $mute;$attempt++){
            foreach($button in $root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$buttons)){
              $name=[string]$button.Current.Name
              $pattern=$null
              if(@('Silenciar','Mute') -contains $name -and $button.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){ $mute=$button; break }
            }
            if($null -eq $mute){Start-Sleep -Milliseconds 250}
          }
          if($null -eq $mute){[pscustomobject]@{ok=$false;effectObserved=$false;error='client_mute_button_not_found'}|ConvertTo-Json -Compress;exit 0}
          $toggle=$mute.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
          $before=[int]$toggle.Current.ToggleState
          $after=$before
          if($before -ne $desired){
            $toggle.Toggle();$effect=$true
            for($read=0;$read -lt 20;$read++){
              $after=[int]$toggle.Current.ToggleState
              if($after -eq $desired){break}
              Start-Sleep -Milliseconds 100
            }
            # The button's own click, once, when its toggle did not take (the window was behind another).
            $invoke=$null
            if($after -ne $desired -and $mute.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$invoke)){
              $invoke.Invoke()
              for($read=0;$read -lt 20;$read++){
                $after=[int]$toggle.Current.ToggleState
                if($after -eq $desired){break}
                Start-Sleep -Milliseconds 100
              }
            }
          }
          if($after -ne $desired){[pscustomobject]@{ok=$false;effectObserved=$effect;before=$before;value=$after;error='client_mute_postread_unchanged'}|ConvertTo-Json -Compress;exit 0}
          [pscustomobject]@{ok=$true;effectObserved=$effect;before=$before;value=$after}|ConvertTo-Json -Compress
        } catch {[pscustomobject]@{ok=$false;effectObserved=$effect;error='client_microphone_failed'}|ConvertTo-Json -Compress;exit 2}
        """;

    private async ValueTask<ExternalCapabilityReceipt> ClientMicrophoneSetAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        if (ExternalJson.RequiredString(arguments, "client") != "discord"
            || !arguments.TryGetProperty("muted", out JsonElement muted)
            || muted.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return ExternalJson.Failure(operation, "client_microphone_arguments_invalid");
        }

        bool wanted = muted.GetBoolean();
        effectBoundary.Cross(token);
        ExternalProcessResult process = await RunPowerShellAsync(
            ClientMicrophoneScript, [wanted ? "1" : "0"], token).ConfigureAwait(false);
        using JsonDocument response = ParseLastJson(process.Output);
        bool effect = Bool(response.RootElement, "effectObserved");
        if (!Bool(response.RootElement, "ok"))
        {
            string error = String(response.RootElement, "error") is { Length: > 0 } said
                ? said
                : "client_microphone_postread_failed";
            return effect
                ? effectBoundary.Failure(operation, error, effect)
                : ExternalJson.FailureBeforeEffect(operation, error);
        }

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("client", "discord");
            writer.WriteBoolean("muted", wanted);
            writer.WriteBoolean("mutedBefore", response.RootElement.GetProperty("before").GetInt32() == 1);
            writer.WriteString("authority", "discord_uia_mute_toggle_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Switched(operation, result, effect);
    }

    private const string ClientChannelLocateScript = """
        $ErrorActionPreference='Stop';$label=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))
        Add-Type -AssemblyName UIAutomationClient;Add-Type -AssemblyName UIAutomationTypes

        """ + MarkedKeysType + """
        $sig='using System;using System.Runtime.InteropServices;public static class BaxyClientWin{[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);[DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);}'
        if(-not ([System.Management.Automation.PSTypeName]'BaxyClientWin').Type){Add-Type -TypeDefinition $sig}
        # The client's window is the main window of the Discord process, never a window found by its title.
        $w=$null;foreach($p in @(Get-Process -Name 'Discord' -ErrorAction SilentlyContinue)){if($p.MainWindowHandle -ne [IntPtr]::Zero){$w=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle);break}}
        if($null -eq $w){[pscustomobject]@{ok=$false;error='client_window_not_found'}|ConvertTo-Json -Compress;exit 2}
        $h=[IntPtr]$w.Current.NativeWindowHandle;$clientPid=$w.Current.ProcessId;$wasMinimized=[BaxyClientWin]::IsIconic($h);if($wasMinimized){[void][BaxyClientWin]::ShowWindow($h,9)}
        # Ronda final 28 (regla 3): the dialog of the page that holds an element (Chromium exposes role=dialog as a UIA
        # Window, ax_platform_node_win.cc), read up to the page or the window itself; $null when it is in none. The
        # quick switcher is such a dialog; the server, channel and message lists and the message box are in none.
        function Dialog-Of($element) {
          if($null -eq $element -or $element.Current.ProcessId -ne $clientPid){return $null}
          $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker;$node=$walker.GetParent($element)
          for($up=0;$up -lt 60 -and $null -ne $node;$up++){
            if($node.Current.NativeWindowHandle -eq $h.ToInt32() -or $node.Current.ControlType -eq [System.Windows.Automation.ControlType]::Document){return $null}
            if($node.Current.ControlType -eq [System.Windows.Automation.ControlType]::Window){return $node}
            $node=$walker.GetParent($node)
          }
          $null
        }
        # The switcher's rows, as the switcher shows them: the list items inside the dialog that holds the focus (never
        # the conversation's own list items outside it).
        function Read-Items {
          $r=@();$dialog=Dialog-Of ([System.Windows.Automation.AutomationElement]::FocusedElement)
          if($null -eq $dialog){return ,$r}
          $row=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::ListItem)
          $found=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,$row)
          foreach($e in $found){$n=$e.Current.Name;if($n){$r+=$n.Substring(0,[Math]::Min(160,$n.Length))}}
          ,$r
        }
        # Ronda final 29 (regla 3): whether a field of the switcher's dialog holds exactly the typed name (its value read
        # through ValuePattern); a field that cannot be read says no.
        function Field-Shows([string]$text) {
          $dialog=Dialog-Of ([System.Windows.Automation.AutomationElement]::FocusedElement)
          if($null -eq $dialog){return $false}
          # Ronda final 40: Discord 1.0.9261 gives its switcher's field as a ComboBox (the notebook's live read), so an Edit
          # or a ComboBox holding the typed name both count.
          $edit=New-Object System.Windows.Automation.OrCondition(
            (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit)),
            (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::ComboBox)))
          foreach($e in $dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,$edit)){
            $vp=$null
            if($e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){
              try{if(([string]([System.Windows.Automation.ValuePattern]$vp).Current.Value).Trim() -eq $text){return $true}}catch{}
            }
          }
          $false
        }
        # The product and its console compete for the foreground while this runs; a lost focus can drop the
        # keystrokes. Retry the whole focus+switcher+type+read sequence, re-asserting the foreground each round
        # and confirming it held, until the switcher shows matches; nothing is joined or opened.
        # The script runs as a block (& { }): a function sets the flag through a table both share, never $script:.
        $items=@();$foreground=$false;$state=@{read=$false;notOpened=$false;dialogFocus=$false;sent=$false;leftOpen=$false}
        for($round=0;$round -lt 5 -and $items.Count -eq 0;$round++){
          [void][BaxyClientWin]::SetForegroundWindow($h);Start-Sleep -Milliseconds 500
          if([BaxyClientWin]::GetForegroundWindow() -ne $h){Start-Sleep -Milliseconds 400;continue}
          $foreground=$true
          # Ronda final 25-26 (regla 3): no Escape before the switcher is seen open: in Discord it marks the open channel
          # read, declines a call or cancels an edit of the person's; nor one when the front left Discord (it would reach
          # another window).
          # Ronda final 27 (regla 3): the name is typed only into the switcher seen open: after Ctrl+K a new editable
          # field of Discord's must hold the focus (with the switcher already open, Ctrl+K closes it and the focus goes
          # back to the person's message box).
          $focusBefore=[System.Windows.Automation.AutomationElement]::FocusedElement
          $idBefore=$(if($null -ne $focusBefore){[string]::Join('.',$focusBefore.GetRuntimeId())}else{''})
          # Ronda final 28 (regla 3): a focus inside a dialog may be the switcher already open (Ctrl+K would close it
          # and the name would go to the message box): no key is sent. After Ctrl+K the switcher is open only with a
          # new focus inside a dialog (the message box and the channel and message lists are in none).
          # Ronda final 29 (regla 3): once a key went out, a dialog may be the switcher this run opened late: the
          # receipt says a key was sent (sent), never a failure before any effect.
          if($null -ne (Dialog-Of $focusBefore)){$state.dialogFocus=$true;break}
          $state.sent=$true
          [void][BaxyMarkedKeys]::Character([char]'k',$true);Start-Sleep -Milliseconds 1400
          if([BaxyClientWin]::GetForegroundWindow() -ne $h){continue}
          $focusNow=[System.Windows.Automation.AutomationElement]::FocusedElement
          $newFocus=$null -ne $focusNow -and $focusNow.Current.ProcessId -eq $clientPid -and [string]::Join('.',$focusNow.GetRuntimeId()) -ne $idBefore
          $switcherOpen=$newFocus -and $null -ne (Dialog-Of $focusNow)
          if(-not $switcherOpen){$state.notOpened=$true;continue}
          # Ronda final 29 (regla 3): Discord draws the filter 0.6-2.6 s after the name (X1, measured on the notebook), so
          # the rows count as read only once the switcher's field holds the name and the rows differ from the ones shown
          # before typing; else the switcher is not read, never «no channel».
          # The rows before typing are taken once two reads agree (a slow client draws its recent rows late).
          $rowsBefore=(Read-Items) -join "`n"
          for($settle=0;$settle -lt 5;$settle++){Start-Sleep -Milliseconds 300;$again=(Read-Items) -join "`n";if($again -eq $rowsBefore){break};$rowsBefore=$again}
          [void][BaxyMarkedKeys]::Text($label);Start-Sleep -Milliseconds 900
          for($poll=0;$poll -lt 10;$poll++){
            $now=Read-Items
            if($now.Count -gt 0 -and ($now -join "`n") -ne $rowsBefore -and (Field-Shows $label)){$items=$now;$state.read=$true;break}
            Start-Sleep -Milliseconds 500
          }
          # The switcher is closed only with Discord still in front (an Escape never reaches another window). Ronda final
          # 29 (regla 3): a switcher not closed, or still holding the focus after the Escape, is said (leftOpen).
          # Ronda final 31 (regla 3): and only with the focus still inside the switcher's dialog (an Escape on Discord's
          # own view declines a call).
          $state.leftOpen=$true
          if([BaxyClientWin]::GetForegroundWindow() -eq $h -and $null -ne (Dialog-Of ([System.Windows.Automation.AutomationElement]::FocusedElement))){
            [void][BaxyMarkedKeys]::Press(0x1B,$false);Start-Sleep -Milliseconds 300
            $state.leftOpen=$null -ne (Dialog-Of ([System.Windows.Automation.AutomationElement]::FocusedElement))
          }
        }
        # Ronda final 26 (regla 3): a window the look restored from minimized goes back to minimized (SW_SHOWMINNOACTIVE),
        # read back; the receipt says how it was left.
        $leftShown=$false
        if($wasMinimized){[void][BaxyClientWin]::ShowWindow($h,7);Start-Sleep -Milliseconds 150;$leftShown=-not [BaxyClientWin]::IsIconic($h)}
        if(-not $foreground){[pscustomobject]@{ok=$false;error='client_not_foreground';restoredFromMinimized=$wasMinimized;leftShown=$leftShown;sent=$state.sent}|ConvertTo-Json -Compress;exit 3}
        if($state.dialogFocus -and -not $state.read){[pscustomobject]@{ok=$false;error=$(if($state.sent){'client_dialog_after_shortcut'}else{'client_focus_in_a_dialog'});restoredFromMinimized=$wasMinimized;leftShown=$leftShown;sent=$state.sent}|ConvertTo-Json -Compress;exit 3}
        if($state.notOpened -and -not $state.read){[pscustomobject]@{ok=$false;error='client_quick_switcher_not_opened';restoredFromMinimized=$wasMinimized;leftShown=$leftShown;sent=$state.sent}|ConvertTo-Json -Compress;exit 3}
        # Ronda final: the switcher never kept the front long enough to be read: nothing is said of its rows.
        if(-not $state.read){[pscustomobject]@{ok=$false;error='client_quick_switcher_not_read';restoredFromMinimized=$wasMinimized;leftShown=$leftShown;sent=$state.sent}|ConvertTo-Json -Compress;exit 3}
        [pscustomobject]@{ok=$true;window=$w.Current.Name;items=@($items);restoredFromMinimized=$wasMinimized;leftShown=$leftShown;leftOpen=$state.leftOpen}|ConvertTo-Json -Compress
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
        IInputBurst? burst = await LeasedInput.HelperBurstAsync(KeysLease, token).ConfigureAwait(false);
        using var restore = new BurstRestore(burst);
        if (burst?.Refusal is string refused)
        {
            return ExternalJson.FailureBeforeEffect(operation, refused);
        }

        ExternalProcessResult? watched;
        bool interrupted;
        try
        {
            (watched, interrupted) = await LeasedInput.WatchHelperAsync(
                burst, run => RunPowerShellAsync(ClientChannelLocateScript, [Encode(name)], run), token);
        }
        catch (Exception exception) when (exception is TimeoutException or IOException or InvalidDataException)
        {
            // Ronda final: the script may type Ctrl+K and the name into the client: a failure from here on may have
            // left them there.
            return ExternalJson.FailureAfterEffect(operation, "client_quick_switcher_not_read");
        }

        if (interrupted || watched is not { } process)
        {
            // The person acted while the switcher was being typed into: the script was stopped there.
            return ExternalJson.Failure(operation, LeasedInput.Interrupted, true);
        }

        JsonDocument document;
        try
        {
            document = ParseLastJson(process.Output);
        }
        catch (JsonException)
        {
            return ExternalJson.FailureAfterEffect(operation, "client_quick_switcher_not_read");
        }

        using var parsed = document;
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
            // Ronda final 27: Ctrl+K reached the client even when its switcher was not seen open (an effect possible).
            // Ronda final 29: any failure after a key was sent (sent) keeps the possible effect.
            return ExternalJson.Failure(operation, code,
                code is "client_quick_switcher_not_read" or "client_quick_switcher_not_opened"
                || Bool(root, "leftShown") || Bool(root, "sent"));
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
        // A row is the channel asked for only when its name, folded, is the name asked for; the switcher's other
        // rows go back as they were shown, so the model sees what Discord offered.
        string channelName = string.Empty, channelKind = string.Empty, server = string.Empty;
        string? exact = items.FirstOrDefault(item => string.Equals(
            WindowsDesktopMessagingAutomation.Fold(item.Split(", ", StringSplitOptions.TrimEntries)[0]),
            WindowsDesktopMessagingAutomation.Fold(name),
            StringComparison.Ordinal));
        if (exact is not null)
        {
            string[] parts = exact.Split(", ", StringSplitOptions.TrimEntries);
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
            writer.WriteBoolean("found", exact is not null);
            writer.WriteStartArray("switcherRows");
            foreach (string item in items)
            {
                writer.WriteStringValue(item);
            }
            writer.WriteEndArray();
            writer.WriteString("channelName", channelName);
            writer.WriteString("channelKind", channelKind);
            writer.WriteString("server", server);
            writer.WriteBoolean("joined", false);
            // Ronda final 26 (regla 3): Discord was minimized; it was shown for the switcher and minimized again (or, read
            // back, left shown).
            if (Bool(root, "restoredFromMinimized"))
            {
                writer.WriteBoolean("restoredFromMinimized", true);
                writer.WriteBoolean("leftShown", Bool(root, "leftShown"));
            }
            // Ronda final 29 (regla 3): BAXY did not close the switcher (the front or the focus left it) or it still held the focus.
            if (Bool(root, "leftOpen"))
            {
                writer.WriteBoolean("switcherNotClosed", true);
            }

            writer.WriteString("authority", "client_quick_switcher_uia_read");
            writer.WriteEndObject();
        });
        // A window left shown, or the switcher left open, is an effect on the person's window, said as such.
        return ExternalJson.Success(operation, result, effectObserved: Bool(root, "leftShown") || Bool(root, "leftOpen"));
    }

    private static ExternalCapabilityReceipt DisplayStatus(string operation)
    {
        var monitors = new List<(string Name, bool Primary, uint Width, uint Height, uint Hertz)>();
        int unreadMonitors = 0;
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
                // Ronda final 9 (regla 3): attached and not read is not «no monitor there».
                unreadMonitors++;
                continue;
            }
            monitors.Add((name, (device.StateFlags & primaryDevice) != 0, mode.PelsWidth, mode.PelsHeight, mode.DisplayFrequency));
        }
        if (monitors.Count == 0)
        {
            return ExternalJson.Failure(operation, unreadMonitors > 0 ? "display_settings_not_read" : "display_devices_not_found");
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("monitorCount", monitors.Count);
            if (unreadMonitors > 0) writer.WriteNumber("monitorsUnread", unreadMonitors);
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
            // Ronda final 43: mice and keyboards before the long USB list, so a view of 20 keeps them.
            if (requestedKind is "all" or "mouse")
                WritePeripherals(writer, source.RootElement, "mice", "mouse", "FriendlyName", "InstanceId", "Status");
            if (requestedKind is "all" or "keyboard")
                WritePeripherals(writer, source.RootElement, "keyboards", "keyboard", "FriendlyName", "InstanceId", "Status");
            if (requestedKind is "all" or "usb")
                WritePeripherals(writer, source.RootElement, "usb", "usb", "FriendlyName", "InstanceId", "Status");
            writer.WriteEndArray(); writer.WriteString("requestedKind", requestedKind);
            if (source.RootElement.TryGetProperty("unread", out JsonElement unread)
                && unread.ValueKind == JsonValueKind.Array && unread.GetArrayLength() > 0)
            {
                writer.WriteStartArray("unreadKinds");
                foreach (JsonElement kind in unread.EnumerateArray())
                    writer.WriteStringValue(kind.GetString());
                writer.WriteEndArray();
            }
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
            return effectBoundary.Failure(operation,
                response.RootElement.TryGetProperty("error", out JsonElement printError)
                && printError.GetString() == "print_queue_not_read" ? "print_queue_not_read" : "print_job_not_verified",
                effect);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); writer.WriteString("deviceId", deviceId);
            writer.WriteString("documentId", documentId); writer.WriteString("jobId", "print_" + response.RootElement.GetProperty("jobId").GetString());
            writer.WriteString("status", response.RootElement.GetProperty("status").GetString());
            writer.WriteBoolean("documentNamed", Bool(response.RootElement, "documentNamed"));
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

    private async ValueTask<string[]?> ReadWifiProfilesAsync(CancellationToken token)
    {
        ExternalProcessResult process = await RunQuickScriptAsync(WifiProfilesScript, [], token);
        using JsonDocument source = ParseLastJson(process.Output);
        if (source.RootElement.ValueKind != JsonValueKind.Object || !Bool(source.RootElement, "ok"))
        {
            return null;
        }
        return source.RootElement.TryGetProperty("profiles", out JsonElement values)
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
    }

    private async ValueTask<ExternalCapabilityReceipt> WifiProfilesAsync(string operation, CancellationToken token)
    {
        if (await ReadWifiProfilesAsync(token) is not { } profiles)
        {
            return ExternalJson.Failure(operation, "wifi_profiles_not_read");
        }
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
            return IdentityUnknown(operation, "wifi_profile_identity_expired", "profileId", "connected", "wifi_profile_list");
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
        if (await ReadWifiProfilesAsync(token) is not { } profiles)
        {
            return ExternalJson.Failure(operation, "wifi_profiles_not_read");
        }
        string folded = FoldProfile(requested);
        string[] ordinal = profiles
            .Where(profile =>
                string.Equals(profile, requested, StringComparison.Ordinal))
            .ToArray();
        string[] exact = profiles
            .Where(profile => FoldProfile(profile) == folded)
            .ToArray();
        // The network the model named, exactly (or folded for case and accents): a part of a name is another network
        // («MiCasa5G» is not «MiCasa»; BAXY Renew audit 2026-10-15). wifi.profile.list says which ones are saved.
        string[] matches = ordinal.Length > 0 ? ordinal : exact;
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
            // FT/proveedores goal (review of receipts): the place remembered for next time is BAXY's own note; a write
            // that fails (the file held, access denied) turned a verified connection into a failure.
            try
            {
                WriteWifiPlace(place, profile);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
            }
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
        // Ronda final: read first, as the disconnection does. Already connected to this profile is the request done
        // with nothing changed (changed:false), never a connection this call made.
        using (JsonDocument before = await WifiStatusAsync(token))
        {
            if (Bool(before.RootElement, "connected")
                && before.RootElement.TryGetProperty("profile", out JsonElement current)
                && current.ValueKind == JsonValueKind.String
                && string.Equals(current.GetString(), profile, StringComparison.OrdinalIgnoreCase))
                return ExternalJson.Switched(operation, WifiResult(id, true, place), effectObserved: false);
        }

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

        (int pauses, TimeSpan pause) = WifiPolling(TimeSpan.FromMilliseconds(500), 30);
        for (int observation = 0; observation <= pauses; observation++)
        {
            using JsonDocument? status = await TryWifiStatusAsync(token);
            if (status is not null
                && Bool(status.RootElement, "connected")
                && string.Equals(
                    status.RootElement.GetProperty("profile").GetString(),
                    profile,
                    StringComparison.OrdinalIgnoreCase))
            {
                return ExternalJson.Success(operation, WifiResult(id, true, place), true);
            }

            if (observation < pauses)
            {
                await _delay(pause, token);
            }
        }

        return ExternalJson.Failure(operation, "wifi_connect_not_verified", true);
    }

    private async ValueTask<ExternalCapabilityReceipt> WifiDisconnectAsync(
        string operation,
        ExternalEffectBoundary effectBoundary,
        CancellationToken token)
    {
        // Round A: read first. Already disconnected is the request done with nothing changed, never an observed
        // disconnection: the state already reached, which the external handler hands on as changed:false.
        using (JsonDocument before = await WifiStatusAsync(token))
        {
            if (!Bool(before.RootElement, "connected"))
                return ExternalJson.Switched(operation, WifiResult(null, false), effectObserved: false);
        }

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

        (int pauses, TimeSpan pause) = WifiPolling(TimeSpan.FromMilliseconds(300), 20);
        for (int observation = 0; observation <= pauses; observation++)
        {
            using JsonDocument? status = await TryWifiStatusAsync(token);
            if (status is not null && !Bool(status.RootElement, "connected"))
            {
                return ExternalJson.Success(
                    operation,
                    WifiResult(null, false),
                    true);
            }

            if (observation < pauses)
            {
                await _delay(pause, token);
            }
        }

        return ExternalJson.Failure(operation, "wifi_disconnect_not_verified", true);
    }

    // Renew al máximo (w5): with the worker a status read costs a netsh run, not a PowerShell started cold (400-700 ms),
    // so the connection is looked at every 100 ms within the same horizon (15 s to connect, 6 s to disconnect); without
    // it (the test seams) as before.
    private (int Pauses, TimeSpan Pause) WifiPolling(TimeSpan coldPause, int coldPauses) =>
        Scripts is null
            ? (coldPauses, coldPause)
            : ((int)(coldPause * coldPauses / WifiPollPause), WifiPollPause);

    internal static readonly TimeSpan WifiPollPause = TimeSpan.FromMilliseconds(100);

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
        $text=@(netsh wlan show networks mode=bssid);$code=$LASTEXITCODE;$joined=($text -join "`n")
        if($joined -match '(?i)apagada|powered down'){[pscustomobject]@{ok=$false;error='wifi_interface_off'}|ConvertTo-Json -Compress;exit 0}
        if($joined -match '(?i)is not running|no se está ejecutando|no está en ejecución'){[pscustomobject]@{ok=$false;error='wlan_service_not_running'}|ConvertTo-Json -Compress;exit 0}
        if($joined -match '(?i)no hay ninguna interfaz|there is no wireless interface|no wireless interface'){[pscustomobject]@{ok=$false;error='wifi_radio_not_found'}|ConvertTo-Json -Compress;exit 0}
        # Auditoría final (regla 3): the list counts only when netsh says how many it sees and the blocks read match it.
        if($code -ne 0 -or -not ($joined -match '(?i)(?:hay|there (?:are|is))\s+(\d+)\s+(?:redes?|networks?)')){[pscustomobject]@{ok=$false;error='wifi_scan_not_read'}|ConvertTo-Json -Compress;exit 0}
        $visible=[int]$Matches[1]
        $networks=@();$current=$null
        foreach($line in $text){
          if($line -match '^\s*SSID\s+\d+\s*:\s*(.*?)\s*$'){if($current){$networks+=$current};$current=[ordered]@{ssid=$Matches[1];authentication='';signalPercent=$null};continue}
          if($null -eq $current){continue}
          if($line -match '^\s*(?:Authentication|Autenticación)\s*:\s*(.+?)\s*$' -and -not $current.authentication){$current.authentication=$Matches[1];continue}
          if($line -match '^\s*(?:Signal|Señal)\s*:\s*(\d+)\s*%' -and $null -eq $current.signalPercent){$current.signalPercent=[int]$Matches[1];continue}
        }
        if($current){$networks+=$current}
        if($networks.Count -ne $visible){[pscustomobject]@{ok=$false;error='wifi_scan_not_read'}|ConvertTo-Json -Compress;exit 0}
        [pscustomobject]@{ok=$true;visible=$visible;networks=@($networks|ForEach-Object {[pscustomobject]$_})}|ConvertTo-Json -Compress -Depth 4
        """;

    private async ValueTask<ExternalCapabilityReceipt> WifiScanAsync(
        string operation,
        CancellationToken token)
    {
        ExternalProcessResult process = await RunQuickScriptAsync(WifiScanScript, [], token);
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
        if (!root.TryGetProperty("visible", out JsonElement visibleElement)
            || visibleElement.ValueKind != JsonValueKind.Number
            || !visibleElement.TryGetInt32(out int visible))
        {
            return ExternalJson.Failure(operation, "wifi_scan_not_read");
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
            // Auditoría final (regla 3): the count is the one netsh declared; a list cut at 50 says so.
            writer.WriteNumber("networkCount", visible);
            if (visible > networks.Count) writer.WriteNumber("listedCount", networks.Count);
            writer.WriteStartArray("networks");
            foreach ((string ssid, string authentication, int? signal) in networks)
            {
                writer.WriteStartObject();
                writer.WriteString("ssid", string.IsNullOrWhiteSpace(ssid) ? "(oculta)" : ssid);
                writer.WriteBoolean("hidden", string.IsNullOrWhiteSpace(ssid));
                writer.WriteString("authentication", authentication);
                if (signal is int value)
                {
                    writer.WriteNumber("signalPercent", value);
                    writer.WriteString("signal", Infrastructure.ReadingUnits.Percent(value));
                }
                else writer.WriteNull("signalPercent");
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
                // Ronda final 33 (regla 3): Settings was opened on its Notifications page and left open, even when the
                // setting already was so.
                writer.WriteBoolean("settingsWindowOpened", true);
                writer.WriteEndObject();
            });
            return ExternalJson.Switched(operation, quietResult, quietEffect);
        }

        if (setting != "brightness")
        {
            return ExternalJson.Failure(operation, "system_setting_invalid");
        }

        if (value is < 0 or > 100)
        {
            return ExternalJson.Failure(operation, "brightness_value_invalid");
        }

        effectBoundary.Cross(token);
        ExternalProcessResult process = await RunQuickScriptAsync(
            BrightnessScript,
            [value.ToString(System.Globalization.CultureInfo.InvariantCulture)],
            token);
        using JsonDocument response = ParseLastJson(process.Output);
        if (String(response.RootElement, "error") == BrightnessNotSupported)
            return ExternalJson.FailureBeforeEffect(operation, BrightnessNotSupported);
        bool effect = Bool(response.RootElement, "effectObserved");
        if (!Bool(response.RootElement, "ok"))
        {
            return ExternalJson.WithStateAfter(
                effectBoundary.Failure(operation, "brightness_postread_failed", effect),
                BrightnessStateAfter(response.RootElement, value));
        }

        // Ronda 22 (r18 t4-c04 t2: the same level asked again took 10.2 s against 3.6 s the first time): a set whose
        // read before already shows the asked level on every monitor changes nothing, so it does not wait for a
        // change that will not come; it returns at once with changed:false and the level read.
        bool changed = !response.RootElement.TryGetProperty("changed", out JsonElement changedElement)
            || changedElement.ValueKind != JsonValueKind.False;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", setting);
            writer.WriteNumber("value", value);
            writer.WriteBoolean("changed", changed);
            // Ronda 19b (r17 t3-c04): the level read before the set is part of the observation, so a final may say
            // the direction it went («bajé el brillo al 30 %») only when these readings show it.
            if (response.RootElement.TryGetProperty("baselineValues", out JsonElement baseline)
                && baseline.ValueKind == JsonValueKind.Array)
            {
                writer.WritePropertyName("baselineValues");
                baseline.WriteTo(writer);
            }

            writer.WriteString("authority", "wmi_monitor_brightness_postread");
            writer.WriteEndObject();
        });
        return changed
            ? ExternalJson.Success(operation, result, true)
            : ExternalJson.Switched(operation, result, effectObserved: false);
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
        ExternalProcessResult process = await RunQuickScriptAsync(
            BrightnessAdjustScript,
            [delta.ToString(System.Globalization.CultureInfo.InvariantCulture)],
            token);
        using JsonDocument response = ParseLastJson(process.Output);
        if (String(response.RootElement, "error") == BrightnessNotSupported)
            return ExternalJson.FailureBeforeEffect(operation, BrightnessNotSupported);
        bool effect = Bool(response.RootElement, "effectObserved");
        if (!Bool(response.RootElement, "ok"))
        {
            return ExternalJson.WithStateAfter(
                effectBoundary.Failure(operation, "brightness_adjustment_postread_failed", effect),
                BrightnessStateAfter(response.RootElement, requested: null));
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
            // Ronda final: a step at the limit (up at 100, down at 0) changes nothing, and the receipt says so.
            writer.WriteBoolean("changed", !JsonElement.DeepEquals(
                response.RootElement.GetProperty("baselineValues"), response.RootElement.GetProperty("values")));
            writer.WriteString(
                "authority",
                "wmi_monitor_brightness_relative_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effect);
    }

    // Renew al máximo (w8): a set or step whose read-back did not show the level within 1.5 s said only «postread
    // failed»; the levels the last read saw (and the ones before) go with it as stateAfter, never as a success.
    private static JsonElement? BrightnessStateAfter(JsonElement response, int? requested)
    {
        if (!response.TryGetProperty("values", out JsonElement values) || values.ValueKind != JsonValueKind.Array
            || values.GetArrayLength() == 0)
            return null;
        return ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WritePropertyName("values");
            values.WriteTo(writer);
            if (response.TryGetProperty("baselineValues", out JsonElement baseline) && baseline.ValueKind == JsonValueKind.Array)
            {
                writer.WritePropertyName("baselineValues");
                baseline.WriteTo(writer);
            }
            if (requested is int level)
                writer.WriteNumber("requestedLevel", level);
            writer.WriteBoolean("requestedStateReached", false);
            writer.WriteString("authority", "wmi_monitor_brightness_postread");
            writer.WriteEndObject();
        });
    }

    private async ValueTask<ExternalCapabilityReceipt> SettingStatusAsync(
        string operation, JsonElement arguments, CancellationToken token)
    {
        string setting = ExternalJson.RequiredString(arguments, "setting");
        if (setting == "airplane_mode")
            return await AirplaneModeStatusAsync(operation).ConfigureAwait(false);
        if (setting != "brightness")
            return ExternalJson.Failure(operation, "brightness_status_invalid");
        ExternalProcessResult process = await RunQuickScriptAsync(
            BrightnessStatusScript, [], token);
        using JsonDocument response = ParseLastJson(process.Output);
        if (String(response.RootElement, "error") == BrightnessNotSupported)
            return ExternalJson.Failure(operation, BrightnessNotSupported);
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
        ExternalProcessResult process = await RunQuickScriptAsync(
            WifiStatusScript,
            [],
            token);
        JsonDocument status = ParseLastJson(process.Output);
        if (status.RootElement.ValueKind != JsonValueKind.Object || !Bool(status.RootElement, "ok"))
        {
            string code = status.RootElement.ValueKind == JsonValueKind.Object ? String(status.RootElement, "error") : "";
            status.Dispose();
            throw new WifiStatusUnreadException(
                code is "wlan_service_not_running" or "wifi_radio_not_found" ? code : "wifi_status_not_read");
        }
        return status;
    }

    // Renew al máximo (w8): after a connect or disconnect was sent, one status netsh did not answer ended the wait with
    // the adapter's generic failure; it is now one look that saw nothing, and the wait goes on.
    private async ValueTask<JsonDocument?> TryWifiStatusAsync(CancellationToken token)
    {
        try
        {
            return await WifiStatusAsync(token);
        }
        catch (WifiStatusUnreadException)
        {
            return null;
        }
    }

    private sealed class WifiStatusUnreadException(string code) : IOException("netsh wlan show interfaces was not read.")
    {
        internal string Code { get; } = code;
    }

    private ValueTask<ExternalProcessResult> RunPowerShellAsync(
        string script,
        IReadOnlyList<string> arguments,
        CancellationToken token) =>
        _runner.RunPowerShellAsync(script, arguments, TimeSpan.FromSeconds(60), token);

    // Renew al máximo (w5): a short read or set of WMI (the brightness) or of netsh (the Wi-Fi's state, saved profiles and
    // networks in sight) runs in the product's UI Automation worker, already started, with the same script, arguments
    // and budget; a PowerShell started cold for it cost 400-700 ms on the notebook against 10-20 ms for a WMI read.
    // Without the worker (the test seams) it runs as before.
    private ValueTask<ExternalProcessResult> RunQuickScriptAsync(
        string script,
        IReadOnlyList<string> arguments,
        CancellationToken token) =>
        Scripts is { } worker
            ? UiaWorkerScript.RunAsync(worker, script, arguments, TimeSpan.FromSeconds(60), token)
            : RunPowerShellAsync(script, arguments, token);

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

internal sealed record BluetoothPairingState(string Name, bool IsPaired, bool CanPair);

/// <summary>Revisión nb-q-apps2: a Bluetooth device's pairing, read and asked of Windows (a fake in tests).</summary>
internal interface IBluetoothPairing
{
    ValueTask<BluetoothPairingState> ReadAsync(string nativeId, CancellationToken cancellationToken);

    // Whether Windows answered that the device is paired (Paired or AlreadyPaired).
    ValueTask<bool> PairAsync(string nativeId, CancellationToken cancellationToken);
}

internal sealed class WindowsBluetoothPairing : IBluetoothPairing
{
    internal static readonly WindowsBluetoothPairing Instance = new();

    public async ValueTask<BluetoothPairingState> ReadAsync(string nativeId, CancellationToken cancellationToken)
    {
        DeviceInformation item = await DeviceInformation.CreateFromIdAsync(nativeId).AsTask(cancellationToken)
            .ConfigureAwait(false);
        return new BluetoothPairingState(item.Name, item.Pairing.IsPaired, item.Pairing.CanPair);
    }

    public async ValueTask<bool> PairAsync(string nativeId, CancellationToken cancellationToken)
    {
        DeviceInformation item = await DeviceInformation.CreateFromIdAsync(nativeId).AsTask(cancellationToken)
            .ConfigureAwait(false);
        DevicePairingResult paired = await item.Pairing.PairAsync(DevicePairingProtectionLevel.Default)
            .AsTask(cancellationToken).ConfigureAwait(false);
        return paired.Status is DevicePairingResultStatus.Paired or DevicePairingResultStatus.AlreadyPaired;
    }
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
